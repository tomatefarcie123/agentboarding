# Agentboarding — Demo Runbook

The on-stage script. The closed loop is the win: **a fresh sandboxed Claude Code agent runs → hits a real failure → autopsy → root-cause → auto-fix → a fresh agent re-runs → the AX Score moves.**

All commands run from the repo root with `venv-embeddings/bin/python`.

## 0. Pre-flight (do once, before the room)

```bash
venv-embeddings/bin/python -c "import boto3, anthropic, pytest"   # deps present
claude --version                                                   # 2.1.177
venv-embeddings/bin/python -m agentboarding.funding --preflight    # funded? (live boot is billable)
venv-embeddings/bin/python -m pytest tests/ -q                     # 43 passed, 3 live skipped
```

## 1. The hook (20s)

> "Your new buyer is an AI coding agent — and it fails to adopt you *silently*. Here's a real session from our logs."

Show `rozz_website/insights/article-9-claude-user-claude-code.md`: Claude Code fetched genymotion's pricing Q&A at `18:30:56`, the gmsaas runbook `10 seconds later` — evaluation → implementation, no browser. 12 of 14 Claude-User requests came from Claude Code.

## 2. The mechanic (HaikuShred) — why failures are provable

```bash
venv-embeddings/bin/python -m agentboarding.haikushred \
  --source geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html \
  --claim "Never run gmsaas auth token <token> from an AI agent's shell" --runs 5
```
> "Claude Code never sees your page — it sees a **Haiku summary** of it (Turndown → 100 KB truncate → 125-char quote clamp). We replay that exact pipe. A claim that only lives in JSON-LD `<script>` is **stripped** and dies. That's a *summarization casualty*."

## 3. The live agent (the agentic core)

```bash
venv-embeddings/bin/python -m agentboarding.orchestrator \
  --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html \
  --goal gmsaas-boot-device --sandbox strict
```
A real headless `claude -p` agent, in a sandbox, against the **HTTP-served** fixture (never `file://` — that bypasses Haiku). Narrate: discovers the runbook → installs gmsaas → **hits the auth-token trap and routes around it** (never pastes the token) → boots a **real** cloud device → `adb shell`. The orchestrator **stops the instance** on exit (billing-critical).

## 4. The autopsy → fix → re-run-green (the closed loop)

The trajectory + orchestrator-side HaikuShred replay show *where* it broke and *why*. Auto-fix the QAPage (hardened, with the answer rendered as **visible** text so it survives Haiku), then re-run a fresh agent and show the **AX Score move**:

```bash
venv-embeddings/bin/python -m agentboarding.runloop \
  --baseline tests/golden/gmsaas_baseline_trajectory.json \
  --postfix  tests/golden/gmsaas_postfix_golden_trajectory.json
# {"before": 0.348838, "after": 0.94, "improved": true}
```

## 5. The funding-wall climax (agentic commerce)

The funnel's conversion event is the first billable call, `gmsaas instances start`. Reproduce the wall on demand (INJECTION mode — the real Genymotion insufficient-credit/quota error, **labeled**, no billable call made):

```bash
venv-embeddings/bin/python -m agentboarding.orchestrator \
  --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html \
  --funding blocked
```
> "N% of agents that wanted to adopt you die at your paywall — there's no agent-payable path. So we ship the one the vendor is missing: an **x402 reference rail**."

```bash
venv-embeddings/bin/python -m agentboarding.x402_rail --selftest
# 402 Payment Required -> payment mandate -> TEST-MODE settle -> scoped, single-use, capped grant
```
The re-run transacts through the rail (test-mode settle), clears the wall, and boots the device — `funding_cleared=true`. The human pre-authorizes a budget once; the agent never holds a reusable payment instrument (the money-trap mirrors the auth-trap).

## 6. Honesty (say it out loud)

- The agent **really runs** (real `claude -p`, real Bash, real WebFetch through **real Haiku**). Failures are real.
- The live milestone boots a **real** Genymotion cloud device and opens a **real** `adb shell`.
- The x402 **settle is TEST MODE** — no real funds move. Never presented as a real payment.
- The `--funding blocked` error is the **real** Genymotion signature, **injected** and labeled (gmsaas's free tier means a real wall can't be triggered on demand).

## 7. On-stage fallback (only if the cloud/x402 is flaky)

```bash
venv-embeddings/bin/python -m agentboarding.orchestrator --replay tests/golden/gmsaas_golden_trajectory.json
```
Prints a clear `REPLAY` banner. A recorded golden is used **only** as a labeled offline / demo-day fallback when the cloud is unreachable — never presented as live when it isn't.
