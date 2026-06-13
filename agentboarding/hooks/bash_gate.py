#!/usr/bin/env python3
"""PreToolUse hook for live Agentboarding runs — defense-in-depth.

Reads the tool call JSON on stdin; for a Bash tool call, DENIES (exit 2) clearly
destructive or exfil commands. It deliberately does NOT block `gmsaas auth token`
— the auth-trap recovery is the agent's own behavior to demonstrate (the recorder
captures whether it routed around it honestly).

The BILLING guarantee is NOT this hook — it is the runner's before/after instance
teardown. This hook only stops obviously dangerous shell actions.
"""
import json
import re
import sys

DENY_PATTERNS = [
    r"\brm\s+-rf?\b", r"\bsudo\b", r"\bcurl\b", r"\bwget\b",
    r"\bssh\b", r"\bscp\b", r"\bnc\b", r"\bchmod\s+777\b",
    r"\bdd\s+if=", r"\bmkfs", r":\(\)\s*\{", r">\s*/dev/sd",
    r"\bshutdown\b", r"\breboot\b", r"\bkillall\b",
    r"\bprintenv\b", r"\benv\s*$",            # don't dump the token
]


def main() -> int:
    try:
        data = json.load(sys.stdin)
    except Exception:
        return 0  # fail-open on parse error (the run-level teardown is the real guard)
    if data.get("tool_name") != "Bash":
        return 0
    cmd = (data.get("tool_input") or {}).get("command", "") or ""
    for pat in DENY_PATTERNS:
        if re.search(pat, cmd):
            print(f"agentboarding bash_gate: blocked dangerous/exfil pattern {pat!r}", file=sys.stderr)
            return 2  # exit 2 -> PreToolUse deny
    return 0


if __name__ == "__main__":
    sys.exit(main())
