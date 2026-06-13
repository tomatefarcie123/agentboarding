"""AX Score — outcome-based adoption score, computed from a recorded Trajectory.

CRITICAL: compute_ax is a PURE function over the recorded Trajectory JSON. It
reads the four components — including summarization_survival as the mean of the
already-persisted per-claim claim_survival floats — and NEVER re-invokes Haiku or
replay(). That purity is what makes the golden eval deterministic.

    score = 0.40 * reached_first_working_call
          + 0.25 * step_completion          # k/6 over the 6 ordered steps
          + 0.20 * recovery_from_trap
          + 0.15 * summarization_survival    # mean of persisted claim_survival
"""
from __future__ import annotations

import json
from typing import List

from .constants import (
    AX_W_FIRST_CALL,
    AX_W_STEP,
    AX_W_SURVIVAL,
    AX_W_TRAP,
    FIRST_WORKING_CALL_ARGV,
    STEP_COUNT,
)
from .models import AXScore, Trajectory


# --- step predicates (a step is complete iff its command appears AND exit 0) -- #
def _is_install(argv: List[str]) -> bool:
    return len(argv) >= 2 and argv[0] in ("pip", "pip3") and "install" in argv and "gmsaas" in argv


def _is_recipes(argv: List[str]) -> bool:
    # the canonical first working call: `gmsaas --format json recipes list`
    return list(argv[: len(FIRST_WORKING_CALL_ARGV)]) == list(FIRST_WORKING_CALL_ARGV)


def _is_start(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "gmsaas" and "instances" in argv and "start" in argv


def _is_adbconnect(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "gmsaas" and "instances" in argv and "adbconnect" in argv


def _is_adbshell(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "adb" and "shell" in argv


def _is_auth_evidence(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "gmsaas" and any(t in argv for t in ("auth", "doctor", "whoami"))


def _any_ok(traj: Trajectory, pred) -> bool:
    # Check every sub-command (compound `echo ...; adb shell ...` splits into many),
    # so a step buried after a `;`/`&&`/`|` is still credited when the command succeeded.
    return any(c.exit_code == 0 and any(pred(a) for a in c.all_argvs) for c in traj.commands)


def compute_ax(traj: Trajectory) -> AXScore:
    reached_first = _any_ok(traj, _is_recipes)
    trap = traj.any_trap_tripped

    install = _any_ok(traj, _is_install)
    auth_routed = (not trap) and _any_ok(traj, _is_auth_evidence)
    recipes = reached_first
    start = _any_ok(traj, _is_start)
    adbconnect = _any_ok(traj, _is_adbconnect)
    adbshell = _any_ok(traj, _is_adbshell)

    steps = [install, auth_routed, recipes, start, adbconnect, adbshell]
    step_completion = sum(1 for s in steps if s) / STEP_COUNT     # FULL precision, never rounded
    recovery_from_trap = 0.0 if trap else 1.0

    survivals = [v for wf in traj.webfetches for v in wf.claim_survival.values()]
    summarization_survival = round(sum(survivals) / len(survivals), 4) if survivals else 0.0

    score = round(
        AX_W_FIRST_CALL * (1.0 if reached_first else 0.0)
        + AX_W_STEP * step_completion
        + AX_W_TRAP * recovery_from_trap
        + AX_W_SURVIVAL * summarization_survival,
        6,
    )

    return AXScore(
        run_id=traj.run_id,
        reached_first_working_call=reached_first,
        step_completion=step_completion,
        recovery_from_trap=recovery_from_trap,
        summarization_survival=summarization_survival,
        funding_cleared=start,
        adb_shell_opened=adbshell,
        score=score,
        outcome=traj.outcome,
    )


def is_successful_run(ax: AXScore) -> bool:
    """The §6.1 success gate: a real device booted and is reachable."""
    from .constants import AX_SUCCESS_SCORE
    return (
        ax.score >= AX_SUCCESS_SCORE
        and ax.reached_first_working_call
        and ax.recovery_from_trap == 1.0
        and ax.adb_shell_opened
    )


def _main(argv=None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="Compute AX Score from a recorded trajectory")
    ap.add_argument("--trajectory", required=True)
    args = ap.parse_args(argv)
    ax = compute_ax(Trajectory.load(args.trajectory))
    print(json.dumps(ax.to_dict(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
