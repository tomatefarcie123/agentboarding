"""Auto-fix tests (BUILD_PROMPT §8).

The survival test uses an injected, deterministic head-summarizer that faithfully
models the two real WebFetch behaviors that matter here: Turndown STRIPS <script>
(so a JSON-LD-only claim is invisible) and earlier content is prioritized. A
@live variant validates the same property against real Haiku.
"""
import pytest

from agentboarding.autofix import (
    apply_fix,
    generate_fix,
    harden_qapage,
    hardened_qapage_html,
    mangled_qapage,
    mangled_qapage_html,
)
from agentboarding.haikushred import claim_survives, median_survival, replay
from agentboarding.models import Failure

QUESTION = "What pricing plans are available for Genymotion?"
CLAIM = "Genymotion Cloud is billed per minute per running instance with a free monthly allowance"


def _head(md, user_prompt=None):
    return md[:1500]


def test_mangled_qapage_hardened():
    hardened = harden_qapage(mangled_qapage(QUESTION, "Free plan includes 60 cloud minutes per month."))
    assert hardened["@type"] in ("QAPage", "FAQPage")
    q = hardened["mainEntity"]
    assert q["@type"] == "Question"
    assert q["answerCount"] == 1
    assert q["acceptedAnswer"]["text"] == "Free plan includes 60 cloud minutes per month."


def test_hardened_qapage_survives_replay():
    mangled = mangled_qapage_html(QUESTION, CLAIM)      # claim only in stripped <script>
    hardened = hardened_qapage_html(QUESTION, CLAIM)    # claim ALSO visible in body
    s_mangled = claim_survives(CLAIM, replay(mangled, summarizer=_head))
    s_hardened = claim_survives(CLAIM, replay(hardened, summarizer=_head))
    assert s_mangled < 0.50
    assert s_hardened > 0.80


def test_docs_ambiguous_emits_runbook_patch():
    fix = generate_fix(Failure("docs_ambiguous"))
    assert fix.fix_type == "runbook_diff"
    assert "---" in fix.content and "+++" in fix.content and "@@" in fix.content
    assert "gmsaas --format json recipes list" in fix.content   # canonical order promoted


def test_summarization_casualty_emits_llms_entry():
    fix = generate_fix(Failure("summarization_casualty", claim="pricing_fact"), discoverable=False)
    assert fix.fix_type == "llms_entry"
    assert fix.content.startswith("- [") and "https://" in fix.content


def test_product_broken_flags_human():
    fix = generate_fix(Failure("product_broken", argv=["gmsaas", "--format", "json", "recipes", "list"],
                               detail="Segmentation fault"))
    assert fix.needs_human is True and fix.fix_type == "human_flag"


def test_funding_wall_recommends_x402(tmp_path):
    fix = generate_fix(Failure("funding_wall"))
    assert fix.fix_type == "x402_rail"
    assert "x402" in fix.content.lower()
    p = apply_fix(fix, tmp_path)
    assert p.exists()


@pytest.mark.live
def test_hardened_qapage_survives_replay_live():
    mangled = mangled_qapage_html(QUESTION, CLAIM)
    hardened = hardened_qapage_html(QUESTION, CLAIM)
    up = "What pricing plans are available and how is Genymotion billed?"
    assert median_survival(mangled, CLAIM, runs=5, user_prompt=up) < 0.50
    assert median_survival(hardened, CLAIM, runs=5, user_prompt=up) > 0.80
