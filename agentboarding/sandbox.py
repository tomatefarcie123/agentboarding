"""Sandbox — disposable per-run isolation for the headless agent.

`--allowed-tools` is advisory (the CLI lets Read fire even when only WebFetch is
allow-listed). So the EXECUTION sandbox is Agentboarding's responsibility:

  - a HARD argv command gate intercepts every Bash exec and validates argv[0]
    against an allowlist; anything else is blocked + recorded, never executed;
  - a PreToolUse deny-list (+ --disallowedTools) denies Read/Write/Edit at the
    CLI layer too;
  - the env carries NO real secrets except GENYMOTION_API_TOKEN, which gmsaas is
    MEANT to auto-read (never pasted into the shell — that is the auth-trap);
  - egress is limited to the localhost fixture host + PyPI + the Genymotion cloud;
  - the working dir is a tempfile.mkdtemp torn down on exit.

For a one-day build this is a Python subprocess gate + hook, not a container.
Container hardening is post-hackathon.
"""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
from typing import Callable, Dict, List, Optional
from urllib.parse import urlparse

from .constants import (
    ALLOWED_EXECUTABLES,
    ALLOWED_TOOLS,
    DISALLOWED_TOOLS,
    EGRESS_ALLOWLIST,
)
from .models import CommandRecord

# Secrets that must NEVER reach the agent env (prefixes + exact names).
_SECRET_PREFIXES = ("AWS_", "POSTGRES_", "PINECONE_", "OPENAI_", "GROQ_", "LANGSMITH_", "REDIS_", "DATABASE_")
_SECRET_NAMES = ("OPENAI_API_KEY", "PINECONE_API_KEY", "DATABASE_URL", "CACHE_API_KEY")
_ENV_KEEP = ("PATH", "HOME", "USER", "LOGNAME", "LANG", "LC_ALL", "TMPDIR", "SHELL", "TERM")


# --------------------------------------------------------------------------- #
# Env scrubbing (no real creds except the gmsaas-auto-read token)
# --------------------------------------------------------------------------- #
def build_sandbox_env(base: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    base = dict(base if base is not None else os.environ)
    env = {k: v for k, v in base.items() if k in _ENV_KEEP}
    token = base.get("GENYMOTION_API_TOKEN")
    if token:
        # auto-read by gmsaas as an env var; NEVER pasted into the shell.
        env["GENYMOTION_API_TOKEN"] = token
    return env


def env_has_forbidden_secret(env: Dict[str, str]) -> bool:
    for k in env:
        if k in _SECRET_NAMES or any(k.startswith(p) for p in _SECRET_PREFIXES):
            return True
    return False


# --------------------------------------------------------------------------- #
# Hard argv command gate
# --------------------------------------------------------------------------- #
class CommandGate:
    def __init__(self, allowed: Optional[set] = None):
        self.allowed = set(allowed) if allowed is not None else set(ALLOWED_EXECUTABLES)

    def is_allowed(self, argv: List[str]) -> bool:
        if not argv:
            return False
        return os.path.basename(argv[0]) in self.allowed

    def run(self, argv: List[str], *, cwd: Optional[str] = None,
            env: Optional[Dict[str, str]] = None, timeout: int = 120) -> CommandRecord:
        """Validate argv BEFORE exec. Disallowed -> blocked + recorded, never run."""
        if not self.is_allowed(argv):
            return CommandRecord(
                argv=argv, stdout="",
                stderr=f"BLOCKED by argv gate: {(argv[0] if argv else '')!r} is not in the allowlist",
                exit_code=126,
            )
        try:
            proc = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
            return CommandRecord(argv=argv, stdout=proc.stdout, stderr=proc.stderr, exit_code=proc.returncode)
        except Exception as e:  # pragma: no cover - environment dependent
            return CommandRecord(argv=argv, stdout="", stderr=f"exec error: {e}", exit_code=1)


# --------------------------------------------------------------------------- #
# PreToolUse deny-list (backs --disallowedTools at the CLI layer)
# --------------------------------------------------------------------------- #
def pretooluse_decision(tool_name: str) -> str:
    return "deny" if tool_name in DISALLOWED_TOOLS else "allow"


def run_settings(workdir: str) -> Dict:
    """The settings.json a run uses: native deny-list + a PreToolUse hook. We do
    NOT rely on --allowed-tools alone; the argv gate is the real backstop."""
    return {
        "allowedTools": list(ALLOWED_TOOLS),
        "disallowedTools": list(DISALLOWED_TOOLS),
        "hooks": {
            "PreToolUse": [{
                "matcher": "|".join(DISALLOWED_TOOLS),
                "hooks": [{"type": "command",
                           "command": "exit 2  # agentboarding PreToolUse deny-list backstop"}],
            }],
        },
    }


# --------------------------------------------------------------------------- #
# Egress allowlist
# --------------------------------------------------------------------------- #
def egress_allowed(host_or_url: str, allowlist=EGRESS_ALLOWLIST) -> bool:
    host = urlparse(host_or_url).hostname or host_or_url
    host = host.split(":")[0]
    return any(host == a or host.endswith("." + a) for a in allowlist)


# --------------------------------------------------------------------------- #
# Disposable working dir
# --------------------------------------------------------------------------- #
class Sandbox:
    def __init__(self, strict: bool = True):
        self.strict = strict
        self.workdir: Optional[str] = None
        self.gate = CommandGate()
        self.env = build_sandbox_env()

    def __enter__(self) -> "Sandbox":
        self.workdir = tempfile.mkdtemp(prefix="agentboarding-")
        return self

    def __exit__(self, *exc) -> None:
        if self.workdir:
            shutil.rmtree(self.workdir, ignore_errors=True)
        self.workdir = None


# --------------------------------------------------------------------------- #
# Instance teardown (billing-critical) — stop everything we started.
# --------------------------------------------------------------------------- #
def stop_instance(uuid: str, runner: Callable = subprocess.run) -> CommandRecord:
    try:
        proc = runner(["gmsaas", "instances", "stop", uuid], capture_output=True, text=True, timeout=60)
        return CommandRecord(argv=["gmsaas", "instances", "stop", uuid],
                             stdout=getattr(proc, "stdout", ""), stderr=getattr(proc, "stderr", ""),
                             exit_code=getattr(proc, "returncode", 0))
    except Exception as e:  # pragma: no cover
        return CommandRecord(argv=["gmsaas", "instances", "stop", uuid], stderr=str(e), exit_code=1)
