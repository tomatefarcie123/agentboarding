# Agentboarding — CI for the agent era

A fleet of real, sandboxed **Claude Code** sub-agents try to discover → evaluate → install → integrate a dev tool from its public surface alone. We record the full trajectory, replay the **WebFetch→Haiku** pipe out-of-band to prove *summarization casualties*, root-cause each failure, **auto-fix** it, and **re-run a fresh agent to prove the gap closed** (the **AX Score** moves).

This is the implementation of the Claude Build Day winner. The pitch, prior-art, and tournament are in [`../hackathon/build-day/`](../hackathon/build-day/). The full spec is [`../hackathon/build-day/BUILD_PROMPT.md`](../hackathon/build-day/BUILD_PROMPT.md). The on-stage script is [`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md).

## Modules

| Module | Role |
|---|---|
| `orchestrator.py` | Spawns a fresh headless `claude -p` agent, serves the fixture over **HTTP** (never `file://`), parses stream-json into the recorder, tears down cloud instances. `--replay`, `--funding blocked`. |
| `sandbox.py` | Disposable per-run isolation: hard **argv command gate**, PreToolUse deny-list, no-creds env (except the gmsaas-auto-read token), egress allowlist. |
| `trajectory.py` | Recorder. Reconstructs **both** WebFetch halves out-of-band (source HTML + replayed Haiku summary); the agent's in-stream summary is cross-check only. |
| `haikushred.py` | Faithful WebFetch replay: Turndown → 100 KB truncate → Haiku (empty system prompt) → 125-char quote clamp. `claim_survives` = deterministic token-recall. |
| `rootcause.py` | Pure classifier, 5 classes: `product_broken`, `docs_ambiguous`, `hallucinated_flag`, `summarization_casualty`, `funding_wall`. |
| `autofix.py` | Per-class patches. The QAPage fix runs `geo/schema_hardening.harden_jsonld` and renders the answer as **visible** text (JSON-LD alone is stripped by Turndown). |
| `axscore.py` | Pure, deterministic outcome score (reads persisted survival floats, never re-invokes Haiku). |
| `runloop.py` | Re-run-to-prove-delta. |
| `funding.py` / `x402_rail.py` | Funding-wall detection + the protocol-faithful x402 reference rail (402 → mandate → test-mode settle → scoped single-use grant). |

## Run it

```bash
# Definition-of-Done suite (deterministic, offline)
venv-embeddings/bin/python -m pytest \
  tests/test_agentboarding_sandbox.py tests/test_trajectory.py tests/test_haikushred.py \
  tests/test_rootcause.py tests/test_autofix.py tests/test_axscore.py \
  tests/test_runloop.py tests/test_fidelity.py tests/test_funding.py tests/test_e2e.py -q
# -> 43 passed, 3 skipped (the live Haiku / live device-boot tests)

# Live validation (real Haiku / real agent / real cloud), authorized credits:
venv-embeddings/bin/python -m pytest tests/ --run-live -v
```

Determinism: `compute_ax` and `classify` are pure over recorded JSON and read the persisted `claim_survival` floats; HaikuShred runs once at record time. The live device boot is the target; a clearly-labeled committed golden is the offline / demo-day fallback when the Genymotion cloud is unreachable.
