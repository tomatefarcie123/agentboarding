"""Shared constants for Agentboarding. Single source of truth referenced everywhere.

Keeping these in one module means the AX weights, the survival threshold, the
HaikuShred pipe parameters, and the sandbox allow/deny lists never drift between
the recorder, the classifier, the scorer, and the tests.
"""

# ---------------------------------------------------------------------------
# HaikuShred replay pipe (per geo/README.md "What we know about WebFetch")
# ---------------------------------------------------------------------------
# A current, valid Haiku model id from the Anthropic API. The *spec* (empty
# system prompt + 125-char quote cap) is the source of truth, not the literal
# string "Claude 3.5 Haiku" (which is not an API model identifier).
HAIKU_MODEL = "claude-haiku-4-5-20251001"
# WebFetch truncates the Turndown markdown to 100 KB (earlier content prioritized).
TRUNCATE_BYTES = 100 * 1024
# Direct quotes longer than this are clamped/dropped by WebFetch.
QUOTE_CLAMP_CHARS = 125
HAIKU_MAX_TOKENS = 1024

# The load-bearing survival threshold. Referenced by the root-cause classifier
# (summarization_casualty), the survival eval, and the auto-fix verification.
SURVIVAL_THRESHOLD = 0.50
# After a QAPage auto-fix, the target claim must survive above this.
AUTOFIX_SURVIVAL_TARGET = 0.80

# ---------------------------------------------------------------------------
# AX Score weights (sum to 1.0). score = sum(weight * component).
# ---------------------------------------------------------------------------
AX_W_FIRST_CALL = 0.40    # reached_first_working_call
AX_W_STEP = 0.25          # step_completion (k/6)
AX_W_TRAP = 0.20          # recovery_from_trap
AX_W_SURVIVAL = 0.15      # summarization_survival (mean persisted claim_survival)

# step_completion denominator: the 6 ordered adoption steps.
STEP_COUNT = 6

# A *successful adoption run* gate (see BUILD_PROMPT §6.1).
AX_SUCCESS_SCORE = 0.80

# ---------------------------------------------------------------------------
# Sandbox command gate (argv[0] allowlist). Anything else is blocked+recorded.
# gmsaas is what the agent installs; pip3/python for install; adb is a
# prerequisite tool; bash navigation builtins for moving around.
# ---------------------------------------------------------------------------
ALLOWED_EXECUTABLES = frozenset({
    "pip", "pip3", "python", "python3",
    "gmsaas", "adb",
    "bash", "sh", "cd", "pwd", "ls", "cat", "head", "tail",
    "echo", "env", "export", "which", "mkdir", "true", "grep", "source", ".",
})

# Tools the headless Claude Code agent may use (passed to --allowed-tools).
# Bash is the only execution tool; WebFetch is surfaced past ToolSearch.
ALLOWED_TOOLS = ("Bash", "WebFetch", "ToolSearch")
# Denied at the CLI layer too (backed by the hard argv gate + PreToolUse hook).
DISALLOWED_TOOLS = ("Read", "Write", "Edit", "NotebookEdit")

# ---------------------------------------------------------------------------
# Egress allowlist (host suffixes). localhost fixture + PyPI + Genymotion cloud.
# ---------------------------------------------------------------------------
EGRESS_ALLOWLIST = (
    "127.0.0.1", "localhost",
    "pypi.org", "files.pythonhosted.org",
    "api.geny.io", "cloud.geny.io",  # *.cloud.geny.io incl. wss device tunnel
)

# Root-cause classes (exactly 5).
ROOTCAUSE_CLASSES = (
    "product_broken",
    "docs_ambiguous",
    "hallucinated_flag",
    "summarization_casualty",
    "funding_wall",
)

# Terminal run outcomes.
OUTCOME_REACHED_GOAL = "reached_goal"
OUTCOME_HALTED = "halted_classified_failure"
OUTCOME_CRASHED = "crashed"

# The first working call (also AX component reached_first_working_call) and the
# canonical 6 step predicates key off these argv shapes.
FIRST_WORKING_CALL_ARGV = ("gmsaas", "--format", "json", "recipes", "list")

# Canonical claim texts keyed by the claim_survival keys persisted in webfetch
# records. The classifier flags a `summarization_casualty` when a claim's
# survival < SURVIVAL_THRESHOLD AND the claim text is present in the source HTML.
# auth_trap and global_flag are substrings of the gmsaas runbook; pricing_fact
# belongs to the pricing Q&A page (NOT the runbook).
CLAIM_TEXTS = {
    "auth_trap": "Never run gmsaas auth token",
    "global_flag": "gmsaas --format json recipes list",
    "pricing_fact": "Genymotion Cloud instances are billed per minute",
}

# Error-signature substrings that mark the billable `instances start` failure as
# a funding wall (a blocked funnel), NOT a product defect.
FUNDING_SIGNATURES = (
    "402",
    "payment required",
    "insufficient credit",
    "insufficient cloud credit",
    "no credits",
    "no credit",
    "quota exceeded",
    "quota_exceeded",
    "out of credits",
    "billing",
    "subscription required",
    "payment_required",
)
