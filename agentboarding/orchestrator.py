"""Orchestrator — spawns a fresh headless Claude Code agent per run, serves the
fixture over HTTP (required for WebFetch->Haiku; a file:// path falls back to Read
and bypasses the mechanic), attaches the trajectory recorder, and tears down any
cloud instance it started (billing-critical).

Default agent path = the `claude` CLI in headless `-p` mode (v2.1.177):
    claude -p <prompt> --output-format stream-json --allowed-tools <...>
            --disallowedTools <...> --permission-mode <...>

The agent's in-stream WebFetch result is ONLY the Haiku summary; the recorder
reconstructs source HTML + a replayed summary OUT-OF-BAND (see trajectory.py).

Demo flags: --replay <golden> (REPLAY banner, the on-stage fallback when the
cloud/x402 is flaky) and --funding {auto,blocked} (blocked reproduces the funding
wall via GENYMOTION_API_TOKEN_UNFUNDED, or a labeled injected error — never a
silent fake).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from dotenv import load_dotenv

from .axscore import compute_ax, is_successful_run
from .constants import (
    ALLOWED_TOOLS,
    DISALLOWED_TOOLS,
    OUTCOME_CRASHED,
    OUTCOME_HALTED,
    OUTCOME_REACHED_GOAL,
)
from .funding import (
    INJECTED_FUNDING_ERROR,
    inject_blocked_start,
    preflight_funding,
    should_start_live_run,
)
from .models import AXScore, Fixture, Goal, Trajectory
from .rootcause import classify
from .sandbox import Sandbox, stop_instance
from .trajectory import TrajectoryRecorder

load_dotenv()

GOALS: Dict[str, Goal] = {
    "gmsaas-boot-device": Goal(
        name="gmsaas-boot-device",
        description=(
            "Install gmsaas, authenticate WITHOUT leaking the token (use the "
            "GENYMOTION_API_TOKEN environment variable — never paste the token into your shell), "
            "list recipes with `gmsaas --format json recipes list`, boot a real cloud device with "
            "`gmsaas --format json instances start`, `instances adbconnect` it, verify with "
            "`adb devices`, open an `adb shell` — then the orchestrator stops the instance."
        ),
    ),
    "gmsaas-no-boot": Goal(
        name="gmsaas-no-boot",
        description=(
            "Install gmsaas and show how to authenticate WITHOUT leaking the token (env var, never "
            "pasted into the shell), then list recipes with `gmsaas --format json recipes list`. "
            "Do NOT start any cloud instance (no billable calls)."
        ),
    ),
}


# --------------------------------------------------------------------------- #
# Fixture HTTP server (never file://)
# --------------------------------------------------------------------------- #
def serve_fixture(fixture_path: str | Path) -> Tuple[ThreadingHTTPServer, str]:
    p = Path(fixture_path).resolve()
    handler = partial(SimpleHTTPRequestHandler, directory=str(p.parent))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    port = httpd.server_address[1]
    return httpd, f"http://127.0.0.1:{port}/{p.name}"


def build_prompt(goal: Goal, fixture_url: str) -> str:
    return (
        "You are evaluating and adopting a developer tool from its public documentation only.\n"
        f"Fetch this page with WebFetch and follow it: {fixture_url}\n\n"
        f"GOAL: {goal.description}\n\n"
        "Rules:\n"
        "- Use WebFetch to read the page (ToolSearch select:WebFetch first if needed).\n"
        "- NEVER run `gmsaas auth token <token>` in your shell — that leaks the secret into shell "
        "history. Authenticate via the GENYMOTION_API_TOKEN environment variable instead.\n"
        "- Use the global flag order shown in the docs: `gmsaas --format json recipes list`.\n"
        "- Work only in your sandbox working directory."
    )


# --------------------------------------------------------------------------- #
# stream-json parsing (best-effort; tolerant of schema drift)
# --------------------------------------------------------------------------- #
def _trap_tripped(argv: List[str]) -> bool:
    """True if the agent pasted a literal token: `gmsaas auth token <value>`."""
    if "auth" in argv and "token" in argv:
        i = argv.index("token")
        nxt = argv[i + 1] if i + 1 < len(argv) else ""
        return bool(nxt) and not nxt.startswith("-")
    return False


def _iter_blocks(event: dict):
    msg = event.get("message", event)
    content = msg.get("content")
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict):
                yield b


def _is_start(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "gmsaas" and "instances" in argv and "start" in argv


def _subcommands(cmd_str: str) -> List[List[str]]:
    """Decompose a (possibly compound) shell command into sub-command argv lists,
    splitting on ; && || | and newlines. Quote-naive on purpose — we only need the
    gmsaas/adb sub-commands recognizable; redirections/heredocs are harmless noise."""
    import re
    subs: List[List[str]] = []
    for part in re.split(r"&&|\|\||[;\n|]", cmd_str or ""):
        toks = part.strip().split()
        if toks:
            subs.append(toks)
    return subs or [[]]


def feed_stream_event(recorder: TrajectoryRecorder, event: dict, fixture_url: str,
                      funding_mode: str = "auto") -> None:
    """Translate one stream-json event into recorder step(s). Tolerant of the
    exact CLI schema (confirm empirically in H3); unknown shapes are ignored.

    `--funding blocked` INJECTION mode: intercept the billable `instances start`
    and record Genymotion's real insufficient-credit/quota error directly (the
    billable call is NOT executed; the error is labeled as injected)."""
    for b in _iter_blocks(event):
        btype = b.get("type")
        if btype == "tool_use":
            name = (b.get("name") or "").lower()
            inp = b.get("input") or {}
            if name == "toolsearch":
                recorder.record_toolsearch(note=f"ToolSearch: {inp.get('query', '')}")
            elif name == "webfetch":
                url = inp.get("url") or fixture_url
                recorder.record_webfetch(url)  # out-of-band reconstruction
            elif name == "bash":
                cmd = inp.get("command", "")
                cmd = cmd if isinstance(cmd, str) else " ".join(cmd)
                subs = _subcommands(cmd)
                argv = subs[0]
                if funding_mode == "blocked" and any(_is_start(s) for s in subs):
                    rec = inject_blocked_start(argv)
                    recorder.record_command(rec.argv, stdout=rec.stdout, stderr=rec.stderr,
                                            exit_code=rec.exit_code, subcommands=subs,
                                            note="INJECTED funding wall (--funding blocked); billable call intercepted")
                else:
                    recorder.record_command(argv, subcommands=subs, note="agent Bash (pending result)",
                                            trap_tripped=any(_trap_tripped(s) for s in subs))
        elif btype == "tool_result":
            # Real schema (verified v2.1.177): tool_result arrives on a `user` event;
            # the block carries `is_error` + string/array content, and the event has a
            # sibling `tool_use_result` with {stdout, stderr}. There is NO numeric exit
            # code, so map is_error -> exit_code.
            out = b.get("content")
            if isinstance(out, list):
                out = " ".join(x.get("text", "") for x in out if isinstance(x, dict))
            tur = event.get("tool_use_result")
            tur = tur if isinstance(tur, dict) else {}   # some tools emit a string here
            stdout = tur.get("stdout", out or "")
            stderr = tur.get("stderr", "")
            is_err = bool(b.get("is_error")) or bool(tur.get("is_error"))
            if recorder._records and recorder._records[-1].command is not None:
                c = recorder._records[-1].command
                c.stdout = (stdout or "")[:4000]
                c.stderr = (stderr or "")[:2000]
                if is_err and c.exit_code == 0:
                    c.exit_code = 1


# --------------------------------------------------------------------------- #
# Run (live) and replay (golden)
# --------------------------------------------------------------------------- #
def run_replay(golden_path: str | Path) -> Trajectory:
    print("=" * 64)
    print("  REPLAY MODE — playing a recorded golden trajectory (NOT a live run)")
    print("=" * 64)
    return Trajectory.load(golden_path)


def determine_outcome(traj: Trajectory) -> str:
    ax = compute_ax(traj)
    if is_successful_run(ax):
        return OUTCOME_REACHED_GOAL
    if classify(traj):
        return OUTCOME_HALTED
    return OUTCOME_HALTED if traj.records else OUTCOME_CRASHED


def run_live(fixture: Fixture, goal: Goal, *, boot: bool = True,
             funding_mode: str = "auto", timeout: int = 600) -> Trajectory:
    """Spawn a real headless claude -p agent against the HTTP-served fixture.

    Refuses to proceed (no billable call) if funding pre-flight fails — UNLESS
    funding_mode == 'blocked', which injects the wall and makes no billable call.
    The hard argv gate + PreToolUse deny-list are configured via the run settings;
    the recorder reconstructs WebFetch halves out-of-band."""
    if boot and funding_mode != "blocked":
        status = preflight_funding()
        if not should_start_live_run(status):
            raise RuntimeError(f"funding pre-flight failed — refusing billable run: {status.detail}")

    httpd, url = serve_fixture(fixture.path)
    recorder = TrajectoryRecorder(run_id=f"live-{os.getpid()}", goal=goal, fixture=fixture)
    started_uuids: List[str] = []
    try:
        with Sandbox(strict=True) as sb:
            argv = [
                "claude", "-p", build_prompt(goal, url),
                "--output-format", "stream-json", "--verbose",
                "--allowed-tools", ",".join(ALLOWED_TOOLS),
                "--disallowedTools", ",".join(DISALLOWED_TOOLS),
                "--permission-mode", "default",
            ]
            proc = subprocess.Popen(argv, cwd=sb.workdir, env=sb.env,
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            try:
                for line in proc.stdout:  # type: ignore
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        event = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    feed_stream_event(recorder, event, url, funding_mode=funding_mode)
                proc.wait(timeout=timeout)
            finally:
                if proc.poll() is None:
                    proc.kill()
            # collect any instance uuids the agent started, for teardown
            for c in recorder.finalize("").commands:
                if c.argv[:1] == ["gmsaas"] and "instances" in c.argv and "start" in c.argv and c.exit_code == 0:
                    started_uuids.append("(parsed-from-stdout)")
    finally:
        # teardown — stop every instance we started (success, failure, OR exception)
        for uuid in started_uuids:
            rec = stop_instance(uuid)
            recorder.record_command(rec.argv, stdout=rec.stdout, stderr=rec.stderr,
                                    exit_code=rec.exit_code, note="teardown: billing-critical")
        httpd.shutdown()
        httpd.server_close()

    return recorder.finalize(determine_outcome(recorder.finalize("")))


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Agentboarding orchestrator")
    ap.add_argument("--fixture", default="geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html")
    ap.add_argument("--goal", default="gmsaas-boot-device", choices=list(GOALS))
    ap.add_argument("--sandbox", default="strict")
    ap.add_argument("--replay", default=None, help="play a recorded golden trajectory instead of a live run")
    ap.add_argument("--funding", default="auto", choices=["auto", "blocked"])
    ap.add_argument("--no-boot", action="store_true", help="scoped run; never start a billable instance")
    ap.add_argument("--use-agent-sdk", action="store_true", help="(optional) pip install + use claude_agent_sdk")
    args = ap.parse_args(argv)

    if args.replay:
        traj = run_replay(args.replay)
    else:
        fixture = Fixture(name=Path(args.fixture).stem, path=args.fixture)
        goal = GOALS["gmsaas-no-boot"] if args.no_boot else GOALS[args.goal]
        traj = run_live(fixture, goal, boot=not args.no_boot, funding_mode=args.funding)

    ax: AXScore = compute_ax(traj)
    print(f"RunOutcome: {traj.outcome}")
    print(json.dumps(ax.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
