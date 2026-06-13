"""Fidelity test (BUILD_PROMPT §8): a synthetic sandboxed Claude Code agent's UA
classifies as Claude-User -> 'citation' through the SAME ground-truth path real
traffic uses (geo_analytics.identify_bot via BOT_PATTERNS, not CLAUDE_PATTERNS)."""
from analytics.claude_crawler_analysis import is_claude_bot
from analytics.geo_analytics import GeoAnalytics

# Must contain the literal `claude-user` substring (matches real Claude Code traffic).
UA = "Mozilla/5.0 (compatible; claude-user; +https://www.anthropic.com/claude-user) claude-code/2.1.84"


def test_synthetic_agent_ua_is_claude_user_citation():
    g = GeoAnalytics()
    assert g.identify_bot(UA) == "Claude-User"            # routes through BOT_PATTERNS
    assert GeoAnalytics.BOT_CATEGORIES["Claude-User"] == "citation"
    assert is_claude_bot(UA) is True

    # The dependency to preserve: a claude-code-ONLY UA (no `claude-user` token)
    # would NOT match is_claude_bot — so the fixture UA must keep its claude-user token.
    assert is_claude_bot("Mozilla/5.0 some-tool claude-code/2.1.84") is False
