# Agentboarding

> **CI for the agent era.** Built at Claude Build Day (Shack15 SF, June 2026).

AI coding agents like Claude Code are becoming the buyers and integrators of developer tools: a developer asks an agent "how do I use X?", and the agent reads the docs and tries to set it up itself, in the terminal — no website visit. When it gets stuck, it quietly gives up and picks a competitor, and that failure is invisible today.

Agentboarding makes it visible, reproducible, and fixable. It turns a real, sandboxed Claude Code agent loose on a goal — *"from a clean machine, boot a cloud Android device with Genymotion"* — using only the product's public docs, records every step, root-causes each failure (product broken / docs ambiguous / hallucinated flag / **summarization casualty** / **funding wall**), auto-fixes the gap, and re-runs a fresh agent to prove it closed — an **AX Score** moves from red to green.

## Layout
| Path | What |
|---|---|
| `agentboarding/` | orchestrator, sandbox + bash gate, trajectory recorder, HaikuShred replay, root-cause classifier, auto-fix generator, AX Score, x402 funding rail |
| `tests/` + `tests/golden/` | pytest suite + recorded golden trajectories |
| `geo/`, `analytics/` | support files reused from the Rozz GEO stack (Schema.org hardener, AI-bot traffic classifier, the gmsaas runbook fixtures) |
| `hackathon/build-day/` | the brief, rubric, test-suite spec, and demo runbook/script that directed Claude |

## Run the tests
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q
```
Live agent runs additionally need these on PATH: the `claude` CLI, `gmsaas`, `adb` (Android platform-tools), and `node` (Turndown).

## How it was built
Authored by Claude Opus 4.8 in Claude Code: a multi-agent workflow produced the build spec — goals, evals, a 100-point rubric, and this test suite (see `hackathon/build-day/BUILD_PROMPT.md`) — which a headless Claude Code session then implemented block-by-block against the suite. Demo walkthrough: `hackathon/build-day/DEMO_SCRIPT.md`.
