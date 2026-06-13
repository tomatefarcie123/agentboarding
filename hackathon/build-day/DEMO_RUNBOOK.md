# Agentboarding — Demo Runbook

> Operator guide for driving the live demo (VCs + Anthropic engineers, Shack15 SF, Build Day). Pairs with [`BUILD_PROMPT.md`](./BUILD_PROMPT.md) (what gets built) and [`README.md`](./README.md) (the pitch). This file is for the person at the keyboard — prep the day-of, then run the arcs.

The whole credibility of this demo is **"honest by construction."** Every fallback below is *labeled out loud*, never disguised as live. If anything is faked silently, the pitch dies the moment an Anthropic engineer notices. Read §6 (Honesty disclosures) before you go on stage.

---

## 1. The 90-second mental model

Agentboarding spawns a **real, sandboxed Claude Code agent** and gives it a goal — *"from a clean machine, boot a cloud Android device and open an ADB shell with Genymotion"* — and only the product's public docs (served over HTTP so WebFetch routes them through Haiku). The agent tries to adopt the product. It either succeeds or stalls. We then **autopsy** the stall, **root-cause** it, **auto-fix** it, and **re-run a fresh agent to prove the gap closed** (the **AX Score** moves).

Two demo arcs, both real:
- **Arc A — Summarization casualty (technical).** The agent fails because Haiku's lossy summary of the docs dropped a needed instruction. Fix = a Haiku-resistant QAPage. Re-run → succeeds.
- **Arc B — Funding wall (commercial / agentic-commerce climax).** The agent fails because it can't get past the paywall (`instances start` needs funds). Fix = stand up the missing agent-payable **x402** rail. Re-run → the agent transacts (test-mode settle) → boots the device → opens an ADB shell.

Plus the **auth-trap** beat in every run: the agent refuses to paste the API token into its own shell and routes around it. Lean into it — the Anthropic engineers will.

---

## 2. Pre-flight checklist (do this the morning of, not at the podium)

Work top to bottom. Each line is a hard gate.

### 2.0 Operator prerequisites — status (these are NOT the build agent's job)
The coding agent (separate session) builds the software; it cannot fund accounts or install host tooling. Current state of those operator-owned items, as of build-day prep:

| Item | Status | Note |
|---|---|---|
| `adb` (Android platform-tools) | ✅ **done** | `brew install android-platform-tools` → `/opt/homebrew/bin/adb` (v36.0.2) |
| gmsaas (operator pre-flight) | ✅ **done** | `venv-embeddings/bin/gmsaas` v1.15.0 |
| gmsaas `android-sdk-path` | ✅ **done** | `~/android-sdk/platform-tools/adb` → symlink to brew adb; `gmsaas doctor` = "Android SDK OK" |
| Hero `GENYMOTION_API_TOKEN` | ✅ **valid** | in repo-root `.env`; `gmsaas doctor` = "Authentication OK"; auth + recipes + instances-list all work |
| Hero account **credits/subscription** | ✅ **confirmed (2026-06-13)** | capped test boot booted Android 12, `adb shell getprop` returned `12`, instance stopped (no orphan). The full live path — start → adbconnect → adb devices → adb shell → stop — works on this machine + account. |
| Arc B funding wall | ✅ **resolved (injection)** | gmsaas has free monthly device-time → even an unfunded account boots, so no real wall is triggerable. Using `--funding blocked` **labeled injection**; no token needed (removed from `.env`). Open TODO: capture Genymotion's exact insufficient-credit error string. |
| Recorded goldens | ⛔ **pending build** | record during/after the build (§2.4) once the orchestrator exists |

### 2.1 Accounts & funding — **the part that bites**
- [ ] **Hero account is funded.** Log in to **cloud.geny.io → Billing**. Confirm an active subscription / cloud credits. Budget generously: each device boot bills **per minute**; plan ~5–10 min per live run × (rehearsals + the real thing + buffer) → fund well above that. The `--max-run-duration` cap and the teardown sweep protect you, but credits are the thing that silently kills the live boot.
- [ ] **API token in place.** Create/confirm the token at **cloud.geny.io/api**, set `GENYMOTION_API_TOKEN=<token>` in the **repo-root `.env`** (the one `load_dotenv()` reads). gmsaas picks it up automatically — **never** paste it in a shell (that's the trap the demo showcases).
- [ ] **Run the funding pre-flight:** `venv-embeddings/bin/python -m agentboarding.funding --preflight` → must report **funded**. If it fails here, the live boot will fail on stage. Fix funding now.
- [x] **Arc B funding-wall reproduction — DECIDED: labeled injection.** We tested a real "unfunded" account; gmsaas grants generous **free monthly device-time**, so even an unfunded token boots — a real wall can't be triggered on demand. So `--funding blocked` **injects** Genymotion's real insufficient-credit error into the `instances start` result. This is a reproduction harness, **disclosed on stage** ("we reproduce the unfunded state; the error is the real one Genymotion returns") — never a silent fake. *Open TODO:* capture Genymotion's exact insufficient-credit / quota error string (API docs or a truly-exhausted account) so the injection is verbatim; until then it's a faithful approximation tagged `[reproduced]`.

### 2.2 Host tooling
- [x] **Android platform-tools installed** — `brew install android-platform-tools` → `adb` at `/opt/homebrew/bin/adb`. gmsaas `android-sdk-path` is set to `~/android-sdk` (a minimal layout whose `platform-tools/adb` symlinks to the brew adb); `gmsaas doctor` reports "Android SDK OK". (`adb` is a prerequisite tool, NOT the product — the agent installs only gmsaas.) *Re-run on a fresh machine:* `brew install android-platform-tools && mkdir -p ~/android-sdk/platform-tools && ln -sf "$(which adb)" ~/android-sdk/platform-tools/adb && gmsaas config set android-sdk-path ~/android-sdk`.
- [ ] `claude --version` → **2.1.177** (the orchestrator drives `claude -p`).
- [ ] `node --version` present (HaikuShred uses the real Turndown lib, not the approximation).
- [ ] `venv-embeddings/bin/python -c "import boto3, anthropic, pytest"` → ok.
- [ ] `ANTHROPIC_API_KEY` in `.env` (HaikuShred's Haiku stage needs it).

### 2.3 Code is green
- [ ] Full suite green: `venv-embeddings/bin/python -m pytest tests/ -v` (per `BUILD_PROMPT.md` §6.2 — incl. `test_funding.py`).
- [ ] Golden AX eval prints exactly `0.94`: `venv-embeddings/bin/python -m agentboarding.axscore --trajectory tests/golden/gmsaas_golden_trajectory.json`.
- [ ] x402 rail self-test passes: `venv-embeddings/bin/python -m agentboarding.x402_rail --selftest` (shows `402 → mandate → settle → grant`).

### 2.4 Safety nets recorded (do NOT skip — this is what lets you go live with confidence)
- [ ] **Record fresh goldens this morning**, so every live arc has a same-day replay fallback:
  - `tests/golden/gmsaas_golden_trajectory.json` — a full live boot → ADB shell (the hero happy path).
  - `tests/golden/gmsaas_baseline_trajectory.json` + `gmsaas_postfix_golden_trajectory.json` — Arc A baseline + post-fix.
  - `tests/golden/gmsaas_funding_postfix_golden.json` — Arc B post-fix (agent clears the wall via x402).
- [ ] Confirm the **`--replay <golden.json>`** flag plays a recorded run with a visible `REPLAY` banner.

### 2.5 Network & teardown
- [ ] Venue wifi is hostile. Confirm egress to `api.geny.io`, `*.cloud.geny.io` (incl. the `wss://` device tunnel), and PyPI. **Have a phone hotspot ready.**
- [ ] **No orphan instances:** `gmsaas instances list` is empty before you start. The orchestrator stops instances on every run end; if a rehearsal crashed, sweep manually: `gmsaas instances list --quiet | xargs -I {} gmsaas instances stop {}`.

---

## 3. Stage setup

- **Split screen.** Left: the live agent terminal (the `claude -p` session's stream). Right: Agentboarding's trajectory/autopsy view (and the AX Score, big).
- **Font huge.** VCs read from the back.
- **Open the evidence tab:** `rozz_website/insights/article-9-claude-user-claude-code.md` — the real 10-second pricing→runbook session is your opener.
- **Pre-warm:** run one full rehearsal end-to-end within the hour so pip caches are warm and a device-boot is fresh in your muscle memory. Then `gmsaas instances stop` it.

---

## 4. The two arcs (run scripts)

### Opener (20s)
> "Your new buyer is an AI agent — and it fails to adopt you *silently*. Here's a real Claude Code session from our logs: **18:30:56** it fetched Genymotion's pricing; **18:31:06** — ten seconds later — it fetched the install runbook and started setting up. No browser. No website visit. Evaluation to implementation, in the terminal. Today, when that agent fails, nobody can see it. Watch."

### Arc A — Summarization casualty (technical proof)
1. **Turn one loose, live.** `venv-embeddings/bin/python -m agentboarding.orchestrator --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html --goal gmsaas-boot-device --sandbox strict`
2. **Narrate the fight:** "It found the runbook… it's choosing between three pip installs… it just hit the **auth wall** — the runbook refuses to let it paste a token in its shell — watch it route around that."
3. **The stall + autopsy:** "It stalled here. Why? The **Haiku summary** of the page dropped [the needed instruction]. Here's the exact lossy text the agent saw vs. the real HTML." (Show the HaikuShred replay + `claim_survival < 0.50`.)
4. **The fix, live:** Agentboarding emits a Haiku-resistant **QAPage** (and/or a patched runbook step) → re-run a fresh agent → it survives the summary → **AX Score moves** (e.g. 41 → 92).

### Arc B — Funding wall (the agentic-commerce climax)
1. **Run against the unfunded state:** `... --goal gmsaas-boot-device --funding blocked` (per §2.1's chosen method).
2. **The stall:** "The product works perfectly. But the agent just hit the **paywall** — `instances start` needs funds and there's no agent-payable path. This is where adoption dies, and today it's invisible. We call it the **funding wall**." (Show it classified as `funding_wall`, distinct from a product bug.)
3. **The fix — say the honesty line first (see §6):** "Genymotion doesn't expose an agent-commerce endpoint yet — so Agentboarding ships the one they're missing: a protocol-faithful **x402** rail. The settle is test-mode; the device boot is real."
4. **Re-run, live:** a fresh agent hits the rail → `402 Payment Required` → presents a payment mandate → **test-mode settle** → gets a scoped, single-use grant → boots a **real** device → `adb devices` → **opens an ADB shell**. **AX Score moves; `funding_cleared` + `adb_shell_opened` flip true.**
5. **The line:** "This is CI for the agent era. Claude Code, grading Claude Code — and shipping the fix that turns a silent funnel death into a booted device."

---

## 5. Live-vs-fallback decision tree

Decide fast; never freeze on stage.

| Symptom | Do this |
|---|---|
| Funding pre-flight failed in §2.3 | Don't go live on the boot. Run Arc A live; play Arc B from `--replay tests/golden/gmsaas_funding_postfix_golden.json` (announce REPLAY). |
| Venue network flaky / `api.geny.io` unreachable | `--replay tests/golden/gmsaas_golden_trajectory.json` for the boot; keep HaikuShred/autopsy live (local). Say "network's hostile, here's this morning's recorded run." |
| Live agent wanders > ~90s without progress | Let it ride 10–15s more (the recovery IS the story). If truly stuck, cut to the matching `--replay` golden. |
| x402 re-run flaky on stage | `--replay tests/golden/gmsaas_funding_postfix_golden.json`. The x402 self-test (`--selftest`) shown earlier already proves the protocol. |
| Device boot stuck in `ERROR`/`DELETING` | That's the runbook's own guardrail working — narrate it, then `--replay` the happy path. Do NOT proceed to adbconnect on a bad instance. |
| `adbconnect` exit 0 but `adb devices` empty | Known: exit 0 ≠ connected. The agent should retry; if it doesn't recover, `--replay`. |

**Golden rule:** a labeled `REPLAY` is a strength ("we record every run; here's a real one"), a hidden replay is a fraud. Always say it.

---

## 6. Honesty disclosures — say these out loud

- **"The agent is real."** Real headless Claude Code, real commands, real WebFetch through real Haiku. Failures are real, not staged.
- **"We *reproduce* the funding wall."** gmsaas grants generous free monthly device-time, so a real wall can't be triggered on demand — `--funding blocked` injects Genymotion's real insufficient-credit error and **we say so**. The error format is real; the trigger is reproduced. (Do NOT claim it's an organic billing failure.)
- **"The x402 settle is test-mode / sandboxed — no funds move in the handshake.** The endpoint is the one Genymotion doesn't expose yet; we built the reference rail. The **device boot after it is real** and really spends credits."
- **"This is a recorded run from this morning"** — every single time you use `--replay`.
- **Never** present the test-mode settle as a real payment, and never present a replay as live.

---

## 7. Teardown & after

- [ ] `gmsaas instances list` → empty. If not: `gmsaas instances list --quiet | xargs -I {} gmsaas instances stop {}`.
- [ ] Check cloud.geny.io that no device is still billing.
- [ ] The agent held **no reusable payment instrument** at any point (scoped grant only) — that's the money-trap guarantee; mention it if asked about safety.

---

## 8. Quick command reference

```bash
# Pre-flight
venv-embeddings/bin/python -m agentboarding.funding --preflight
venv-embeddings/bin/python -m agentboarding.x402_rail --selftest
venv-embeddings/bin/python -m pytest tests/ -v

# Arc A (live)
venv-embeddings/bin/python -m agentboarding.orchestrator \
  --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html \
  --goal gmsaas-boot-device --sandbox strict

# Arc B (live, trips the funding wall)
venv-embeddings/bin/python -m agentboarding.orchestrator \
  --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html \
  --goal gmsaas-boot-device --sandbox strict --funding blocked

# Fallbacks (announce REPLAY)
venv-embeddings/bin/python -m agentboarding.orchestrator --replay tests/golden/gmsaas_golden_trajectory.json
venv-embeddings/bin/python -m agentboarding.orchestrator --replay tests/golden/gmsaas_funding_postfix_golden.json

# Emergency: stop everything
gmsaas instances list --quiet | xargs -I {} gmsaas instances stop {}
```

*Built for Claude Build Day — Sat June 13, 2026, Shack15 SF.*
