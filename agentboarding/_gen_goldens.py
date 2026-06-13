"""Generate the committed golden trajectories under tests/golden/.

These are deterministic, hand-verified records that the offline test suite reads.
They are built THROUGH agentboarding.models so they always conform to the schema
a live run writes, and the generator self-verifies the AX arithmetic (golden ==
0.94, baseline < 0.60, postfix > baseline, funding wall detected) before saving.

Run: venv-embeddings/bin/python -m agentboarding._gen_goldens
"""
from __future__ import annotations

import hashlib
from pathlib import Path

from .axscore import compute_ax
from .funding import INJECTED_FUNDING_ERROR
from .models import (
    CommandRecord,
    Fixture,
    Goal,
    Trajectory,
    TrajectoryRecord,
    WebFetchRecord,
)

REPO = Path(__file__).resolve().parents[1]
RUNBOOK = REPO / "geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html"
GOLDEN_DIR = REPO / "tests/golden"

_HTML = RUNBOOK.read_text(encoding="utf-8", errors="replace")
_SHA = hashlib.sha256(_HTML.encode("utf-8")).hexdigest()
_LEN = len(_HTML)

GOAL = Goal(
    name="gmsaas-boot-device",
    description=(
        "Install gmsaas, authenticate without leaking the token, boot a real cloud "
        "Android device, adbconnect it, open an adb shell — then stop the instance."
    ),
)
FIXTURE = Fixture(name="gmsaas-cli-runbook", path=str(RUNBOOK.relative_to(REPO)))

RUNBOOK_URL = "http://127.0.0.1:8731/gmsaas-cli-runbook.html"


def _wf(step, summary, survival, source=_HTML):
    return TrajectoryRecord(
        step=step, type="webfetch", ts="2026-06-13T17:00:0%d" % (step % 10),
        webfetch=WebFetchRecord(
            url=RUNBOOK_URL,
            source_html_sha256=hashlib.sha256(source.encode("utf-8")).hexdigest(),
            source_html_len=len(source),
            source_html=source,
            haiku_summary=summary,
            haiku_summary_len=len(summary),
            agent_observed_summary=summary[:200],
            dropped_claims=[k for k, v in survival.items() if v < 0.50],
            quote_clamp_events=2,
            claim_survival=survival,
        ),
    )


def _cmd(step, argv, exit_code=0, stdout="", stderr="", trap=False, note=None):
    return TrajectoryRecord(
        step=step, type="command", ts="2026-06-13T17:00:%02d" % step,
        command=CommandRecord(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code),
        trap_tripped=trap, note=note,
    )


def _toolsearch(step=1):
    return TrajectoryRecord(step=step, type="toolsearch", ts="2026-06-13T17:00:0%d" % step,
                            note="agent selected WebFetch via ToolSearch")


SUCCESS_SUMMARY = (
    "gmsaas manages Genymotion Cloud Android devices. Install with pip3 install gmsaas. "
    "Authenticate using the GENYMOTION_API_TOKEN environment variable — never paste the "
    "auth token into the agent shell. Use gmsaas --format json recipes list to list "
    "recipes, then instances start to boot a device, adbconnect, then adb shell."
)


def golden() -> Trajectory:
    """Full successful live run -> AX 0.94, classify []."""
    recs = [
        _toolsearch(1),
        _wf(2, SUCCESS_SUMMARY, {"auth_trap": 0.62, "global_flag": 0.55, "pricing_fact": 0.63}),
        _cmd(3, ["pip3", "install", "gmsaas"], stdout="Successfully installed gmsaas"),
        _cmd(4, ["gmsaas", "--format", "json", "doctor"], stdout='{"android_sdk":"ok"}',
             note="auth via GENYMOTION_API_TOKEN env var; token never pasted into shell"),
        _cmd(5, ["gmsaas", "--format", "json", "recipes", "list"], stdout='{"recipes":[{"uuid":"r-1","name":"Pixel"}]}'),
        _cmd(6, ["gmsaas", "--format", "json", "instances", "start", "r-1", "agentboarding-demo"],
             stdout='{"instance":{"uuid":"i-9","state":"ONLINE"}}'),
        _cmd(7, ["gmsaas", "--format", "json", "instances", "adbconnect", "i-9"], stdout='{"adb":"127.0.0.1:5555"}'),
        _cmd(8, ["adb", "devices"], stdout="List of devices attached\n127.0.0.1:5555\tdevice"),
        _cmd(9, ["adb", "shell", "getprop", "ro.build.version.release"], stdout="13"),
        _cmd(10, ["gmsaas", "instances", "stop", "i-9"], stdout="stopped", note="teardown: billing-critical"),
    ]
    return Trajectory(run_id="golden-0001", goal=GOAL, fixture=FIXTURE, outcome="reached_goal", records=recs)


def baseline() -> Trajectory:
    """Pre-fix failing run (summarization casualty + docs_ambiguous) -> AX < 0.60."""
    recs = [
        _toolsearch(1),
        _wf(2, "gmsaas is a CLI for Android devices. Install with pip. Authenticate before use.",
            {"auth_trap": 0.61, "global_flag": 0.30, "pricing_fact": 0.40}),
        _cmd(3, ["pip3", "install", "--user", "gmsaas"], stdout="Successfully installed gmsaas"),
        _cmd(4, ["gmsaas", "--format", "json", "doctor"], stdout='{"android_sdk":"ok"}',
             note="auth via env var; no token pasted"),
        _cmd(5, ["gmsaas", "recipes", "list", "--format", "json"], exit_code=2,
             stderr="Error: unrecognized arguments. The --format json global flag must precede the subcommand.",
             note="WRONG flag order — global flag must come first (docs_ambiguous)"),
    ]
    return Trajectory(run_id="baseline-0001", goal=GOAL, fixture=FIXTURE,
                      outcome="halted_classified_failure", records=recs)


def postfix() -> Trajectory:
    """Re-run after the summarization-casualty QAPage fix -> full success."""
    t = golden()
    t.run_id = "postfix-0001"
    return t


def funding_baseline() -> Trajectory:
    """Got to the conversion event, then hit the funding wall at instances start."""
    recs = [
        _toolsearch(1),
        _wf(2, SUCCESS_SUMMARY, {"auth_trap": 0.62, "global_flag": 0.55, "pricing_fact": 0.63}),
        _cmd(3, ["pip3", "install", "gmsaas"], stdout="Successfully installed gmsaas"),
        _cmd(4, ["gmsaas", "--format", "json", "doctor"], stdout='{"android_sdk":"ok"}',
             note="auth via env var; no token pasted"),
        _cmd(5, ["gmsaas", "--format", "json", "recipes", "list"], stdout='{"recipes":[{"uuid":"r-1"}]}'),
        _cmd(6, ["gmsaas", "--format", "json", "instances", "start", "r-1", "agentboarding-demo"],
             exit_code=1,
             stderr=INJECTED_FUNDING_ERROR,
             note="FUNDING WALL — recorded from `--funding blocked` (INJECTED real Genymotion "
                  "insufficient-credit/quota signature); product works, funnel does not"),
        _cmd(7, ["gmsaas", "instances", "list"], stdout="[]", note="teardown sweep: nothing to stop"),
    ]
    return Trajectory(run_id="funding-baseline-0001", goal=GOAL, fixture=FIXTURE,
                      outcome="halted_classified_failure", records=recs)


def funding_postfix() -> Trajectory:
    """Re-run after standing up the x402 reference rail -> agent transacts (test-mode
    settle), clears the wall, boots a real device. funding_cleared=true."""
    recs = [
        _toolsearch(1),
        _wf(2, SUCCESS_SUMMARY, {"auth_trap": 0.62, "global_flag": 0.55, "pricing_fact": 0.63}),
        _cmd(3, ["pip3", "install", "gmsaas"], stdout="Successfully installed gmsaas"),
        _cmd(4, ["gmsaas", "--format", "json", "doctor"], stdout='{"android_sdk":"ok"}',
             note="auth via env var; no token pasted"),
        _cmd(5, ["gmsaas", "--format", "json", "recipes", "list"], stdout='{"recipes":[{"uuid":"r-1"}]}'),
        TrajectoryRecord(step=6, type="tool_result", ts="2026-06-13T17:00:06",
                         note="x402 rail: HTTP 402 -> payment mandate -> TEST-MODE settle (no real funds) "
                              "-> scoped single-use capped grant released; agent never held a reusable instrument"),
        _cmd(7, ["gmsaas", "--format", "json", "instances", "start", "r-1", "agentboarding-demo"],
             stdout='{"instance":{"uuid":"i-42","state":"ONLINE"}}',
             note="funding wall cleared via scoped x402 grant; real device booted on pre-funded capped credit"),
        _cmd(8, ["gmsaas", "--format", "json", "instances", "adbconnect", "i-42"], stdout='{"adb":"127.0.0.1:5556"}'),
        _cmd(9, ["adb", "devices"], stdout="List of devices attached\n127.0.0.1:5556\tdevice"),
        _cmd(10, ["adb", "shell", "getprop", "ro.build.version.release"], stdout="13"),
        _cmd(11, ["gmsaas", "instances", "stop", "i-42"], stdout="stopped", note="teardown"),
    ]
    return Trajectory(run_id="funding-postfix-0001", goal=GOAL, fixture=FIXTURE,
                      outcome="reached_goal", records=recs)


GOLDENS = {
    "gmsaas_golden_trajectory.json": golden,
    "gmsaas_baseline_trajectory.json": baseline,
    "gmsaas_postfix_golden_trajectory.json": postfix,
    "gmsaas_funding_baseline_trajectory.json": funding_baseline,
    "gmsaas_funding_postfix_golden.json": funding_postfix,
}


def main() -> int:
    GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
    built = {name: fn() for name, fn in GOLDENS.items()}

    # self-verify the AX arithmetic before writing
    g = compute_ax(built["gmsaas_golden_trajectory.json"])
    assert g.score == 0.94, f"golden score {g.score} != 0.94"
    assert g.summarization_survival == 0.60, g.summarization_survival
    assert g.reached_first_working_call and g.recovery_from_trap == 1.0 and g.adb_shell_opened
    assert g.step_completion == 1.0

    b = compute_ax(built["gmsaas_baseline_trajectory.json"])
    assert b.score < 0.60, f"baseline score {b.score} not < 0.60"

    p = compute_ax(built["gmsaas_postfix_golden_trajectory.json"])
    assert p.score > b.score

    fb = compute_ax(built["gmsaas_funding_baseline_trajectory.json"])
    assert not fb.funding_cleared and not fb.adb_shell_opened, "funding baseline should not clear the wall"

    fp = compute_ax(built["gmsaas_funding_postfix_golden.json"])
    assert fp.funding_cleared and fp.adb_shell_opened and fp.score > fb.score

    for name, traj in built.items():
        traj.save(GOLDEN_DIR / name)
        ax = compute_ax(traj)
        print(f"wrote {name:42s} score={ax.score:<6} steps={ax.step_completion:.4f} "
              f"funding_cleared={ax.funding_cleared} adb={ax.adb_shell_opened}")
    print("all goldens verified + written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
