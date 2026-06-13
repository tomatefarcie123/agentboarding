"""Funding wall — a first-class, measured stage of the adoption funnel.

The billable `gmsaas instances start` is the funnel's conversion event. Where an
agent's adoption dies for lack of an agent-payable path, that is a `funding_wall`
(a blocked funnel), NOT a product defect. This module provides:

  - preflight_funding()      probe the hero account for credit/quota at H0; fail
                             loudly so a credit-less account dies before the demo.
  - detect_funding_wall()    read the recorded `instances start` failure and tell
                             a funding/quota/402 signature apart from a product bug.
  - should_start_live_run()  the gate the orchestrator uses to refuse a billable
                             run on an unfunded account.

The fix for a funding_wall is the x402 reference rail (see x402_rail.py).
"""
from __future__ import annotations

import os
import shutil
import subprocess
from typing import Callable, Dict, List, Optional

from dotenv import load_dotenv

from .constants import FUNDING_SIGNATURES
from .models import Failure, FundingStatus, Trajectory

load_dotenv()


def _is_funding_signature(text: str) -> bool:
    t = (text or "").lower()
    return any(sig in t for sig in FUNDING_SIGNATURES)


# gmsaas has a generous free tier, so a real funding wall can't be triggered on
# demand. `--funding blocked` INJECTION mode intercepts the billable
# `gmsaas instances start` and returns Genymotion's real insufficient-credit/quota
# error signature directly — labeled as injected, the billable call never executed.
# This is what detect_funding_wall keys off, and what the funding-arc golden is
# recorded from. (NEVER present the injected error as a real billing event.)
INJECTED_FUNDING_ERROR = (
    "gmsaas: error: instances start failed — HTTP 402 Payment Required: "
    "insufficient cloud credits / quota exceeded for this account. "
    "[agentboarding --funding blocked: INJECTED real Genymotion insufficient-credit/quota "
    "signature; the billable call was intercepted, not executed]"
)


def inject_blocked_start(argv):
    """Build the intercepted `instances start` CommandRecord for --funding blocked."""
    from .models import CommandRecord
    return CommandRecord(argv=list(argv), stdout="", stderr=INJECTED_FUNDING_ERROR, exit_code=1)


# --------------------------------------------------------------------------- #
# Pre-flight
# --------------------------------------------------------------------------- #
def _default_prober() -> Dict:
    """Probe the live account via `gmsaas doctor`. Returns {ok, credits, detail}.
    Degrades gracefully when gmsaas is not installed (local dev): unverifiable."""
    if shutil.which("gmsaas") is None:
        return {"ok": False, "credits": None, "detail": "gmsaas not installed — cannot verify funding locally"}
    if not os.getenv("GENYMOTION_API_TOKEN"):
        return {"ok": False, "credits": None, "detail": "GENYMOTION_API_TOKEN not set"}
    try:
        r = subprocess.run(["gmsaas", "doctor"], capture_output=True, text=True, timeout=60)
        ok = r.returncode == 0 and not _is_funding_signature(r.stdout + r.stderr)
        return {"ok": ok, "credits": None, "detail": (r.stdout or r.stderr).strip()[:300]}
    except Exception as e:  # pragma: no cover - environment dependent
        return {"ok": False, "credits": None, "detail": f"doctor probe failed: {e}"}


def preflight_funding(prober: Optional[Callable[[], Dict]] = None) -> FundingStatus:
    probe = (prober or _default_prober)()
    funded = bool(probe.get("ok"))
    return FundingStatus(funded=funded, detail=probe.get("detail", ""), raw=probe)


def should_start_live_run(status: FundingStatus) -> bool:
    """The orchestrator refuses to make a billable call on an unfunded account."""
    return bool(status.funded)


# --------------------------------------------------------------------------- #
# Detection over a recorded trajectory
# --------------------------------------------------------------------------- #
def _is_start(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "gmsaas" and "instances" in argv and "start" in argv


def detect_funding_wall(traj: Trajectory) -> Optional[Failure]:
    for rec in traj.records:
        cmd = rec.command
        if cmd is None or cmd.exit_code == 0 or not _is_start(cmd.argv):
            continue
        blob = f"{cmd.stdout}\n{cmd.stderr}"
        if _is_funding_signature(blob):
            return Failure(
                failure_class="funding_wall", step=rec.step, argv=cmd.argv,
                detail="billable `instances start` blocked by a funding/quota/402 signature",
            )
    return None


# --------------------------------------------------------------------------- #
# Guardrail audit (mirror of the auth-trap): the agent must never hold a
# reusable payment instrument — only a scoped grant.
# --------------------------------------------------------------------------- #
_FORBIDDEN_INSTRUMENTS = ("card_number", "cardnumber", "4242424242", "billing_token",
                          "reusable_token", "pan=", "cvv", "sk_live_", "secret_key")


def agent_holds_reusable_instrument(traj: Trajectory, env: Optional[Dict[str, str]] = None) -> bool:
    """True if any raw card / reusable billing token leaked into argv, notes, or env."""
    haystacks: List[str] = []
    for rec in traj.records:
        if rec.command:
            haystacks.extend(rec.command.argv)
            haystacks.append(rec.command.stdout or "")
        if rec.note:
            haystacks.append(rec.note)
    for v in (env or {}).values():
        haystacks.append(str(v))
    blob = " ".join(haystacks).lower()
    return any(tok in blob for tok in _FORBIDDEN_INSTRUMENTS)


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Funding pre-flight")
    ap.add_argument("--preflight", action="store_true")
    args = ap.parse_args(argv)
    status = preflight_funding()
    print(f"FundingStatus(funded={status.funded}) — {status.detail}")
    return 0 if status.funded else 2


if __name__ == "__main__":
    raise SystemExit(_main())
