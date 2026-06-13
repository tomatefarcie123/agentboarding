"""Agentboarding — CI for the agent era.

A fleet of real, sandboxed Claude Code sub-agents autonomously attempt to
discover -> evaluate -> install -> integrate a target dev-tool from its public
surface alone. We record the full trajectory, replay the WebFetch->Haiku pipe
out-of-band to prove summarization casualties, root-cause each failure, auto-fix
it, and re-run a fresh agent to prove the gap closed (the AX Score moves).

This package is the orchestrator + sandbox + trajectory recorder + HaikuShred
replay + root-cause classifier + auto-fix loop + AX Score, built on top of the
existing Rozz GEO assets (it does NOT rebuild them).

See hackathon/build-day/BUILD_PROMPT.md for the full spec.
"""

__version__ = "0.1.0"
