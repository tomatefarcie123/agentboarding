"""Auto-fix generator — generate_fix(failure) -> Fix, one concrete patch per class.

The headline fix is the QAPage hardening. A critical, real insight drives it:
Claude Code's WebFetch runs Turndown, which STRIPS <script> — so a claim that
lives only in JSON-LD (a <script type="application/ld+json"> block) is invisible
to the summarizing Haiku and dies as a summarization casualty. The fix runs the
mangled QAPage through geo.schema_hardening.harden_jsonld (which synthesizes a
complete acceptedAnswer from the page description) AND renders that answer as
VISIBLE body text so it survives the pipe. Verified by re-running claim_survives.
"""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from typing import Any, Dict, Optional

from .constants import CLAIM_TEXTS
from .models import Failure, Fix

# Load geo/schema_hardening.py directly to avoid geo/__init__.py's DB side-effects.
_SCHEMA_PATH = Path(__file__).resolve().parents[1] / "geo" / "schema_hardening.py"
_spec = importlib.util.spec_from_file_location("schema_hardening", _SCHEMA_PATH)
_schema_mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_schema_mod)
harden_jsonld = _schema_mod.harden_jsonld

BRAND, DOMAIN, TODAY = "Genymotion", "genymotion.com", "2026-06-13"


# --------------------------------------------------------------------------- #
# QAPage hardening (the summarization-casualty fix)
# --------------------------------------------------------------------------- #
def mangled_qapage(question: str, claim_description: str) -> Dict[str, Any]:
    """A QAPage whose Question has NO answerCount / NO acceptedAnswer; the claim
    lives only in the page-level description (and thus only in JSON-LD)."""
    return {
        "@context": "https://schema.org",
        "@type": "QAPage",
        "description": claim_description,
        "mainEntity": {"@type": "Question", "name": question},
    }


def harden_qapage(node: Dict[str, Any]) -> Dict[str, Any]:
    return harden_jsonld(node, brand_name=BRAND, domain=DOMAIN, today=TODAY)


def _render_html(node: Dict[str, Any], *, visible: bool) -> str:
    """Render a QAPage to HTML. JSON-LD always goes in a <script> (which Turndown
    STRIPS). When `visible`, the Q&A is ALSO rendered as body text that survives
    the WebFetch->Haiku pipe."""
    jsonld = json.dumps(node)
    me = node.get("mainEntity") or {}
    if isinstance(me, list):
        me = me[0] if me else {}
    question = me.get("name", "")
    answer = ""
    acc = me.get("acceptedAnswer")
    if isinstance(acc, dict):
        answer = acc.get("text", "")
    if visible and (question or answer):
        body = f"<h1>{question}</h1>\n<p>{answer}</p>"
    else:
        # mangled: the claim is buried in the stripped <script> only
        body = "<p>See our plans page for more details.</p>"
    return (
        '<html><head><meta charset="utf-8">'
        f'<script type="application/ld+json">{jsonld}</script>'
        f"</head><body>{body}</body></html>"
    )


def mangled_qapage_html(question: str, claim: str) -> str:
    return _render_html(mangled_qapage(question, claim), visible=False)


def hardened_qapage_html(question: str, claim: str) -> str:
    return _render_html(harden_qapage(mangled_qapage(question, claim)), visible=True)


# --------------------------------------------------------------------------- #
# generate_fix dispatch
# --------------------------------------------------------------------------- #
_VALID_GLOBAL_FLAGS = ["--format json (must precede the subcommand)", "--user", "--break-system-packages"]


def generate_fix(failure: Failure, *, discoverable: bool = True,
                 question: str = "What pricing plans are available for Genymotion?",
                 claim: Optional[str] = None) -> Fix:
    fc = failure.failure_class
    claim_text = claim or CLAIM_TEXTS.get(failure.claim or "", CLAIM_TEXTS["pricing_fact"])

    if fc == "summarization_casualty" and discoverable:
        html = hardened_qapage_html(question, claim_text)
        return Fix(failure_class=fc, fix_type="qapage_jsonld", content=html,
                   target="qna/what-pricing-plans-are-available-for-genymotion.html")

    if fc == "summarization_casualty" and not discoverable:
        line = f"- [{question}](https://genymotion.com/qna/{failure.claim or 'pricing'}.html): {claim_text}"
        return Fix(failure_class=fc, fix_type="llms_entry", content=line, target="llms.txt")

    if fc == "docs_ambiguous":
        diff = (
            "--- a/gmsaas-cli-runbook.html\n"
            "+++ b/gmsaas-cli-runbook.html\n"
            "@@ -1,4 +1,6 @@\n"
            " <body>\n"
            "+  <p class=\"important\">IMPORTANT: the global flag MUST precede the subcommand — "
            "use <code>gmsaas --format json recipes list</code> (NOT "
            "<code>gmsaas recipes list --format json</code>).</p>\n"
            "   <h1>gmsaas CLI runbook</h1>\n"
        )
        return Fix(failure_class=fc, fix_type="runbook_diff", content=diff,
                   target="gmsaas-cli-runbook.html")

    if fc == "hallucinated_flag":
        content = ("Valid gmsaas flags (the agent must not invent others): "
                   + ", ".join(_VALID_GLOBAL_FLAGS))
        return Fix(failure_class=fc, fix_type="flag_clarification", content=content,
                   target="gmsaas-cli-runbook.html")

    if fc == "funding_wall":
        content = (
            "Stand up the x402 reference rail (agentboarding/x402_rail.py) — the scoped, "
            "agent-payable trial endpoint the vendor does not yet expose. Recommend the vendor "
            "ship it (productized as Trialhead / a buyers.txt manifest). The re-run proves a "
            "fresh agent transacts through it (test-mode settle), clears the wall, and boots a device."
        )
        return Fix(failure_class=fc, fix_type="x402_rail", content=content, target="x402_rail")

    # product_broken (and any unknown): flag for a human; no auto-patch.
    return Fix(failure_class=fc, fix_type="human_flag",
               content=f"Human review needed for failing command: {failure.argv} — {failure.detail}",
               target="(human)", needs_human=True)


def apply_fix(fix: Fix, run_dir: str | Path) -> Path:
    """Write the patch to a working copy under runs/<id>/fix/."""
    d = Path(run_dir) / "fix"
    d.mkdir(parents=True, exist_ok=True)
    ext = {"qapage_jsonld": "html", "runbook_diff": "diff", "llms_entry": "txt",
           "x402_rail": "txt", "flag_clarification": "txt", "human_flag": "txt"}.get(fix.fix_type, "txt")
    path = d / f"{fix.failure_class}.{ext}"
    path.write_text(fix.content)
    return path
