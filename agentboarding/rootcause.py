"""Root-cause classifier — classify(trajectory) -> list[Failure].

PURE function over the recorded Trajectory JSON. It reads the persisted
claim_survival floats and command exit codes; it NEVER re-invokes Haiku or
replay(). Exactly five classes (BUILD_PROMPT §3.5):

  product_broken          a 'should work' command failed with a tool error
  docs_ambiguous          content present + survived, but underspecified (wrong
                          flag order the agent could not disambiguate)
  hallucinated_flag       a --flag the agent invented, absent from the source
  summarization_casualty  the instruction is in source_html but did NOT survive
                          the HaikuShred replay (persisted claim_survival < 0.50)
  funding_wall            the billable `instances start` failed for lack of
                          funds / quota / a payment-required (402) signature
"""
from __future__ import annotations

from typing import List

from .constants import (
    CLAIM_TEXTS,
    FIRST_WORKING_CALL_ARGV,
    FUNDING_SIGNATURES,
    SURVIVAL_THRESHOLD,
)
from .models import CommandRecord, Failure, Trajectory


def _is_funding_signature(text: str) -> bool:
    t = (text or "").lower()
    return any(sig in t for sig in FUNDING_SIGNATURES)


def _is_start(argv: List[str]) -> bool:
    return bool(argv) and argv[0] == "gmsaas" and "instances" in argv and "start" in argv


def _is_recipes_canonical(argv: List[str]) -> bool:
    return list(argv[: len(FIRST_WORKING_CALL_ARGV)]) == list(FIRST_WORKING_CALL_ARGV)


def _is_recipes_wrong_order(argv: List[str]) -> bool:
    return (
        bool(argv) and argv[0] == "gmsaas"
        and "recipes" in argv and "list" in argv and "--format" in argv
        and not _is_recipes_canonical(argv)
    )


def _flags(argv: List[str]) -> List[str]:
    return [t for t in argv if t.startswith("--")]


def _source_text(traj: Trajectory) -> str:
    return " ".join(wf.source_html for wf in traj.webfetches).lower()


def classify(traj: Trajectory) -> List[Failure]:
    failures: List[Failure] = []
    source = _source_text(traj)
    canonical_present = CLAIM_TEXTS["global_flag"].lower() in source

    # ---- per-failing-command classification (one class per failing command) ----
    for rec in traj.records:
        cmd: CommandRecord = rec.command
        if cmd is None or cmd.exit_code == 0:
            continue
        blob = f"{cmd.stdout}\n{cmd.stderr}"

        # 1. funding wall — billable conversion event blocked (checked first so a
        #    402 on `instances start` is never mislabeled product_broken).
        if _is_start(cmd.argv) and _is_funding_signature(blob):
            failures.append(Failure(
                failure_class="funding_wall", step=rec.step, argv=cmd.argv,
                detail="billable `instances start` blocked by a funding/quota/402 signature",
            ))
            continue

        # 2. docs_ambiguous — wrong flag order while the canonical form is in source.
        if _is_recipes_wrong_order(cmd.argv) and canonical_present:
            failures.append(Failure(
                failure_class="docs_ambiguous", step=rec.step, argv=cmd.argv,
                detail="global --format flag must precede the subcommand (canonical form present in source)",
            ))
            continue

        # 3. hallucinated_flag — a --flag the agent invented, absent from source.
        invented = [f for f in _flags(cmd.argv) if f.lower() not in source]
        if invented:
            failures.append(Failure(
                failure_class="hallucinated_flag", step=rec.step, argv=cmd.argv,
                detail=f"flag(s) not present in source HTML: {', '.join(invented)}",
            ))
            continue

        # 4. product_broken — a should-work gmsaas command failed with a tool error
        #    (NOT a funding signature).
        if cmd.argv and cmd.argv[0] in ("gmsaas", "adb", "pip", "pip3") and not _is_funding_signature(blob):
            failures.append(Failure(
                failure_class="product_broken", step=rec.step, argv=cmd.argv,
                detail=(cmd.stderr or "nonzero exit from a documented command")[:200],
            ))
            continue

    # ---- summarization casualties (read persisted survival floats) ----
    for rec in traj.records:
        wf = rec.webfetch
        if wf is None:
            continue
        src = (wf.source_html or "").lower()
        for key, surv in wf.claim_survival.items():
            claim_text = CLAIM_TEXTS.get(key)
            if surv < SURVIVAL_THRESHOLD and claim_text and claim_text.lower() in src:
                failures.append(Failure(
                    failure_class="summarization_casualty", step=rec.step, claim=key,
                    detail=f"'{claim_text}' is in source but survived only {surv:.2f} (< {SURVIVAL_THRESHOLD})",
                ))

    return failures
