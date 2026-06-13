"""HaikuShred replay tests (BUILD_PROMPT §8).

Deterministic stage tests inject a fake summarizer (no network). The genuinely
stochastic survival assertions use real Haiku and are marked `live` (median over
N runs against a threshold band).
"""
import pytest

from agentboarding.haikushred import (
    STAGES,
    HaikuShredResult,
    claim_survives,
    clamp_quotes,
    median_survival,
    replay,
)

GMSAAS = "geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html"
AUTH_TRAP_CLAIM = "Never run gmsaas auth token from an AI agent's shell"


def _echo_head(markdown, user_prompt=None):
    """Fake summarizer: returns the head of the (already truncated) markdown."""
    return markdown[:2000]


def test_pipe_stage_order():
    res = replay("<h1>Hello</h1><p>world</p>", summarizer=lambda md, up: "s")
    assert res.stages == ["turndown", "truncate", "haiku", "quote_clamp"] == STAGES
    assert res.markdown
    assert res.truncated_markdown


def test_style_tags_not_stripped():
    html = "<html><head><style>.zzqqmarker{color:#bada55}</style></head><body><h1>Hi</h1></body></html>"
    res = replay(html, summarizer=lambda md, up: "s")
    # Turndown does NOT strip <style>: the CSS leaks into the markdown as text.
    assert "zzqqmarker" in res.markdown


def test_truncate_at_100kb():
    big = "<p>" + ("word " * 40000) + "</p>"   # ~200 KB of text
    res = replay(big, summarizer=lambda md, up: "s")
    assert len(res.markdown.encode("utf-8")) > 100 * 1024          # pre-truncate is bigger
    assert len(res.truncated_markdown.encode("utf-8")) <= 100 * 1024  # tail dropped


def test_quote_over_125_chars_clamped():
    sentence = (
        "The diligent autonomous agent carefully avoids pasting any long-lived secret "
        "authentication token directly into its own interactive shell history buffer today."
    )
    assert len(sentence) > 125
    clamped, events = clamp_quotes("intro " + sentence + " outro", sentence)
    assert events >= 1
    assert sentence not in clamped  # the >125-char verbatim span was clamped/dropped


def test_buried_sentence_low_survival():
    """Truncation bite: a bottom-buried sentence past the 100 KB cut does not
    survive (deterministic via a fake summarizer that sees only the truncated head)."""
    sentence = (
        "Obscure bottommost instruction about configuring the rarely used "
        "experimental teardown sweep parameter for orphaned cloud instances zzfinal."
    )
    filler = "<p>" + ("filler " * 30000) + "</p>"   # >100 KB before the sentence
    src = f"<html><body>{filler}<p>{sentence}</p></body></html>"
    res = replay(src, summarizer=_echo_head)
    assert claim_survives(sentence, res) < 0.30


def test_claim_survives_is_deterministic_token_recall():
    res = HaikuShredResult(
        markdown="", truncated_markdown="",
        haiku_summary="Never paste the auth token into the agent shell.",
    )
    # claim tokens all present -> recall 1.0; a disjoint claim -> 0.0
    assert claim_survives("auth token agent shell", res) == 1.0
    assert claim_survives("kubernetes helm chart rollout", res) == 0.0
    # stable across calls
    assert claim_survives("auth token", res) == claim_survives("auth token", res)


# --------------------------------------------------------------------------- #
# Live (real Haiku) — bounded nondeterminism: median over N, threshold band.
# --------------------------------------------------------------------------- #
@pytest.mark.live
def test_authtrap_claim_survives():
    html = open(GMSAAS, encoding="utf-8", errors="replace").read()
    med = median_survival(
        html, AUTH_TRAP_CLAIM, runs=5,
        user_prompt="How do I install and authenticate gmsaas safely?",
    )
    assert med >= 0.50
