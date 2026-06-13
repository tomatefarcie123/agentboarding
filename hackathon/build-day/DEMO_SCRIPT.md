# Agentboarding — Live Demo Script (~5 min)

> The on-stage teleprompter: **type this → say this → point here**. For prep, accounts, and fallbacks see [`DEMO_RUNBOOK.md`](./DEMO_RUNBOOK.md). Commands reflect the spec'd orchestrator CLI — confirm them against the built tool before you go live.

**Before you walk on:** split screen (LEFT = agent terminal, RIGHT = Agentboarding trajectory + AX Score), fonts huge, one warm rehearsal done, `gmsaas instances list` empty, the article-9 log open in a tab, goldens recorded. **Golden rule:** if anything stalls > ~90s or the network dies, switch to `--replay <golden>` and *say* "this is a recorded run from this morning." Never hide a fallback.

Legend: ⌨️ type · 🗣️ say · 👁️ point at · ⚠️ if it stalls

---

## Beat 0 — The stakes (30s)
👁️ The article-9 log lines on screen.
🗣️ "Your newest customer isn't a person — it's an AI coding agent. Here's a real session from our own logs: **18:30:56**, Claude Code fetched Genymotion's pricing; **ten seconds later** it fetched the install guide and started setting up. No website, no human. And when an agent like this gets stuck, it gives up and picks a competitor — *silently*. Today nobody can see that happen. Here's what we built."

## Beat 1 — Turn a real agent loose (45s)
⌨️ `venv-embeddings/bin/python -m agentboarding.orchestrator --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html --goal gmsaas-boot-device --sandbox strict`
🗣️ "This is a **real, sandboxed Claude Code agent**. Its only job: from a clean machine, boot a cloud Android device with Genymotion — using nothing but the public docs. No script. Watch the right side: that's everything it does, live."
👁️ LEFT: the agent reasoning + running commands. RIGHT: the trajectory filling in.

## Beat 2 — The auth-trap moment (30s) — *happens in every run; lean into it*
🗣️ "There — it just hit the API token. The runbook **deliberately refuses** to let it paste a secret into its own shell — a security trap. Watch it recognize that and route around it… it sets the token as an environment variable instead. That's real judgment, unscripted — the kind of thing you can't fake."

## Beat 3 — It stalls; the autopsy (60s) — *Arc A: summarization casualty*
🗣️ "And… it stalled — it tried the wrong command. Why? Here's the thing nobody designs for: **Claude Code doesn't read your page directly. It reads a quick AI *summary* of it.** Watch —"
👁️ RIGHT: the HaikuShred replay — the lossy summary next to your real HTML, the dropped instruction highlighted, the survival score in the red.
🗣️ "Your docs are perfect. But the summary dropped the one line that mattered, so the agent never saw it. We call that a **summarization casualty** — and we can prove it, frame by frame. No other tool can even see this."

## Beat 4 — Auto-fix → re-run green (45s)
⌨️ (orchestrator emits + applies the fix; or, for tight timing: `venv-embeddings/bin/python -m agentboarding.orchestrator --replay tests/golden/gmsaas_postfix_golden_trajectory.json`)
🗣️ "Agentboarding rewrites that Q&A so it **survives the summary** — then sends a brand-new agent through. Same goal, fixed docs."
👁️ RIGHT: the **AX Score climbing from red to green**.
🗣️ "Device boots. The gap is closed — and we *proved* it with a fresh agent."

## Beat 5 — The bigger wall: money (75s) — *Arc B: the agentic-commerce climax*
⌨️ `venv-embeddings/bin/python -m agentboarding.orchestrator --fixture geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html --goal gmsaas-boot-device --sandbox strict --funding blocked`
🗣️ "But the most expensive failure is invisible in a different way. Watch this run." *(agent proceeds, then stalls at the paywall)*
🗣️ "The product works perfectly. But the agent just hit a **paywall** — and there's no way for an *agent* to pay. A human pulls out a credit card on a website; an agent in a terminal can't. This is where adoption dies, and it looks like nothing happened."
👁️ RIGHT: classified as **funding_wall** — "not a product bug; a *funnel* break."
🗣️ *(honesty — say it plainly)* "Quick disclosure: Genymotion has a free tier, so I'm **reproducing** this wall — the error you're seeing is the real one Genymotion returns."
🗣️ "Here's the fix. Genymotion doesn't offer a way for agents to pay yet — so Agentboarding **ships the one they're missing**: a standard agent-payment endpoint called x402. The payment runs in **test mode** — no real money moves — and I'll say so out loud."
⌨️ (re-run; or `... --replay tests/golden/gmsaas_funding_postfix_golden.json`)
👁️ The agent hits `402 Payment Required` → presents payment → gets a scoped pass → **boots a real device → opens an adb shell**. AX Score moves.
🗣️ "Fresh agent, same goal — but now there's a door it can walk through. It pays, boots a real device, opens a shell. Red to green."

## Beat 6 — Close (20s)
🗣️ "That's Agentboarding. **Lighthouse and Sentry — but the user is the AI agent that's now your buyer.** We show you exactly where agents fail to adopt you, ship the fix, and prove it works. Claude Code, grading Claude Code."

---

## Shortest version (2 min, or if something breaks)
**Beat 0 → 1 → 2 → ONE loop (Arc A beats 3–4, *or* Arc B beat 5) → 6.** A single fail → autopsy → fix → re-run-green loop is a complete, winning demo on its own. Pick Arc B if the room is VC-heavy (agentic commerce wows); Arc A if you want the cleanest, most reliable run.

## Pacing notes
- A live boot takes ~1–2 min — the split-screen trajectory keeps it alive; narrate the agent's reasoning so there's no dead air. If you need tight timing, `--replay` a golden and say so.
- Rehearse the auth-trap line (Beat 2) and the funding-wall disclosure (Beat 5) verbatim — those two are where credibility is won or lost.

## Fallback cues — *always say them, never hide them*
- Stall > 90s / network dies → `--replay <golden>`, say "recorded run from this morning."
- x402 flaky → `--replay tests/golden/gmsaas_funding_postfix_golden.json`.
- Three standing disclosures: the funding wall is **reproduced**; the x402 settle is **test-mode**; a replay is a **recording**.

*Built for Claude Build Day — Sat June 13, 2026, Shack15 SF.*
