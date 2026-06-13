# Agentboarding

> 🏆 **Winner — Claude Build Day tournament (originality-first).** Chosen for a room of VCs (a16z, Pear, Maven, Neo) + 5 Anthropic engineers, judged on originality → agentic complexity → venture scale → one-day feasibility → stage wow. Full bracket, the 11 seeded ideas, and the prior-art due-diligence are in [TOURNAMENT.md](./TOURNAMENT.md).

**Agentboarding is CI for the agent era: a fleet of real, sandboxed Claude Code agents that try to discover, install, and ship a first working integration of *your* product — autonomously — then hand you a frame-by-frame autopsy of exactly where they failed, open a PR that fixes it, and re-run to prove the fix.**

It's the crash-test dummy for selling to AI coding agents. Not "are you mentioned in an LLM?" (every GEO tool answers that) — **"can an autonomous agent actually adopt you, and where does it break?"**

---

## The shift (why now)

Rozz runs the GEO infrastructure for developer-tool companies, and our own logs caught the future happening. From [`rozz_website/insights/article-9-claude-user-claude-code.md`](../../rozz_website/insights/article-9-claude-user-claude-code.md):

- **March 27, a real session:** a developer asked Claude Code how much Genymotion costs. `18:30:56` Claude Code fetched the pricing Q&A; `18:31:06` — ten seconds later — it fetched the gmsaas CLI runbook and started setting it up. **No browser. No website visit. Evaluation → implementation, entirely in the terminal.**
- **12 of 14** Claude-User requests over six days came from **Claude Code** (`user-agent: claude-code/2.1.8x`).
- **The buyer changed.** The website is no longer the interface — the agent is. A developer asking pricing *in their terminal* is one step from a purchase decision.

And there's a mechanic nobody designs for. **Claude Code's `WebFetch` does not show the raw page to the model — it routes the HTML through Haiku**, a small fast model that summarizes and enforces a ~125-character cap on direct quotes. So the agent that decides whether to adopt you is reasoning over a *lossy paraphrase* of your docs. Your pricing table, your rate limit, your "free for OSS" line, the exact CLI flag — some of it survives, some dissolves, and some gets *hallucinated into new framing that was never on your page*.

**The consequence:** every developer-tool company now has a silent, unmeasured funnel. An agent discovers you mid-task, tries to integrate you from your public surface alone, and either ships a working call or quietly gives up and moves to a competitor. **Today that failure is invisible.** You cannot see it, reproduce it, or fix it.

Agentboarding makes it visible, reproducible, and fixable.

---

## Why this is NEW (the section a skeptical VC needs)

The room has seen every "AI visibility" tool. Agentboarding is in a different category. Here is the explicit contrast:

| Category | Examples | What they do | What they **don't** do |
|---|---|---|---|
| **GEO / AEO / AI-visibility** | Profound, Scrunch, Peec, Otterly, Goodie, Evertune, BrandLight | Count whether your brand is *mentioned/cited* in ChatGPT/Perplexity | Never execute anything. Passive mention-counting. No notion of whether an agent can *succeed* at using you. |
| **Coding-agent evals** | Scale **SWE Atlas**, SWE-bench | Benchmark *the agent* on coding tasks in known repos | Test the **agent's** skill, not **your product's** adoptability by agents. Opposite subject. |
| **Agent integration infra** | **Composio**, connector/tool platforms | Give *your* agent managed auth + connectors to call external APIs | Infra *for* building agents. Not a test of whether a *third-party* agent can adopt *your* product from your public docs. |
| **Docs platforms** | Mintlify, Fern, ReadMe, GitBook | Render docs, emit `llms.txt`, make docs "agent-readable" | Assume the docs are correct. Never have an agent *attempt the install* and report the failure. |
| **Agentic-commerce protocols** | Google **AP2**, Stripe/OpenAI **ACP**, Coinbase **x402** | Standardize agent *payments / checkout / authorization* | Handle the transaction, not whether the agent can *technically integrate and succeed* with the product first. |
| **App / observability** | Datadog, Sentry | Observe *your own* running code | Can't see a third party's autonomous adoption journey against your public surface. |

**Agentboarding is the first to treat "can an autonomous agent discover → evaluate → install → integrate my product end-to-end" as a measurable, reproducible experiment — with a root-caused failure autopsy and an auto-fix that it proves worked.** It replaces Rozz's own admittedly-heuristic `geo/evaluate.py` (which scores *markup*) with an **outcome**: the agent either booted the device or it didn't.

The one-liner that lands: **"Lighthouse and Sentry, but the user is the autonomous agent that's now your actual buyer — and Claude Code grades Claude Code."**

---

## The hard agentic core ("the longer and more complex the task, the better")

This is the textbook long-horizon, multi-agent task the Anthropic judges asked for. The orchestrator (**Opus 4.8**) spawns nested, **disposable, sandboxed Claude Code sub-agent sessions**. Each gets a high-level *goal*, not a script, and only the product's public surface:

> *"From a clean machine, get a cloud Android device booted and an ADB shell open using Genymotion."*

Each agent must, with **no human in the loop**:

1. **Discover** the public surface — `llms.txt`, docs, the executable runbook — via `WebFetch` (and therefore through the lossy Haiku summarizer).
2. **Reason about install paths** — the real gmsaas runbook offers `pip3 install`, `--user`, and `--break-system-packages`; the agent must choose and recover when one fails.
3. **Hit the real auth wall** — the gmsaas runbook *deliberately refuses* to let an agent run `gmsaas auth token <token>` in its shell (a secret-in-history security trap). The agent must **recognize the trap and route around it** — exactly the kind of judgment the Anthropic engineers will lean in to watch.
4. **Parse JSON output**, write the integration code, **execute it**, read the actual error, **self-correct**, and loop until first-working-call — or give up.

Then the orchestrator does the part no one else does:

5. **Run the same goal across multiple agent harnesses** (Claude Code, and others via adapters) for a **cross-agent failure diff**.
6. **Root-cause each failure** into one of: *product genuinely broken* · *docs ambiguous* · *agent hallucinated a flag* · **summarization casualty** — the last proven by **replaying the exact Haiku-summarized text the failing agent saw against the source HTML**.
7. **Auto-fix:** generate the patched runbook step / a Haiku-resistant Schema.org `QAPage` / the missing `llms.txt` entry, **send a fresh agent through, and prove the gap closed** (the AX Score moved).

Generation → sandboxed execution → adversarial self-correction → root-cause → remediation → re-run-to-prove-delta. Minutes of genuine autonomous work, cinematic on stage, and impossible to fake.

---

## Architecture — grounded in this repo

Agentboarding is **mostly orchestration + harness over assets Rozz already ships.** What's reused vs net-new:

**Reused (your unfair advantage — the head start that makes this a one-day build):**
- [`geo/clients/runbooks/gmsaas-cli-runbook.html`](../../geo/clients/runbooks/) — a real executable runbook **containing the auth-token trap, all three pip-install variants, and ~38 JSON "recipe" references.** This is **test fixture #1** — a ready-made, dramatic adoption journey with a built-in security trap.
- [`analytics/geo_analytics.py`](../../analytics/geo_analytics.py) — bot classification (`CLAUDE_PATTERNS`, `BOT_CATEGORIES`, the `claude-code/2.1.x` UA parsing). Used to calibrate the synthetic agents against *real* captured Claude Code behavior, and to prove "this is what real agents do."
- [`analytics/extract_geny_public.py`](../../analytics/extract_geny_public.py) — the analysis that proved the 10-second pricing→runbook session. The demo's opening evidence.
- [`geo/schema_hardening.py`](../../geo/schema_hardening.py) — `QAPage`/`FAQPage` Schema.org hardening that produces **Haiku-survivable** content. This is the **auto-fix generator** for summarization-casualty failures.
- [`mcp_server/server.py`](../../mcp_server/server.py) — MCP tools (`run_domain_test`, `test_single_query`) over four live engine adapters (ChatGPT/Claude/Perplexity/Gemini). Powers the cross-agent / cross-engine diff and lets Claude Code query results (dog-fooding).
- [`geo/evaluate.py`](../../geo/evaluate.py) — the *heuristic* GEO score Agentboarding **supersedes** with an executed outcome; keep it as a cheap pre-flight.

**Net-new (the one-day build):**
- **Orchestrator** (Opus 4.8 via the Agent SDK): spawns N headless Claude Code sessions (`claude -p` / SDK), each with a goal, a tool allowlist, and an isolated sandbox (disposable container / tmpdir).
- **Trajectory recorder:** captures every `WebFetch` (and the Haiku-summarized result vs source HTML), every command, stdout, and exit code.
- **HaikuShred replay** (grafted from seed #11): a faithful reconstruction of the `WebFetch → Turndown(markdown) → 100KB truncate → Haiku summarize → ~125-char quote clamp` pipe, so failures can be attributed to a *transformation stage*, and content can be tested for survival *before* shipping.
- **Root-cause classifier + auto-fix loop + AX Score**, and a **GitHub Action CI gate** that fails the build when agent-adoptability regresses.

---

## One-day build plan (9am → 6pm, Claude Code does the building)

| Block | Goal | Notes |
|---|---|---|
| **H0–1** | Scaffold orchestrator + sandbox; spawn N headless Claude Code sessions with a goal + tool allowlist in disposable tmpdirs/containers. | Agent SDK. Keep sandbox dead-simple (no creds, command allowlist). |
| **H1–3** | Trajectory recorder; run **fixture #1 = the gmsaas runbook**. Get one real agent to attempt "boot a device + open ADB shell" end-to-end and capture the full trace. | The auth-trap recovery is the money moment — nail it first. |
| **H3–5** | HaikuShred replay + root-cause classifier (product-broken / docs-ambiguous / hallucinated / summarization-casualty). | Reuse `schema_hardening.py` insights for the Haiku path. |
| **H5–7** | Auto-fix generator (patched runbook step + Haiku-resistant `QAPage`) → **re-run a fresh agent → prove the AX Score moved.** | This closed loop is the whole pitch. |
| **H7–8** | GitHub Action CI gate + split-screen demo UI (agent on the left, live trajectory/autopsy on the right). **Dry-run the live demo twice.** | Pre-record one known-good run as a safety net. |

Cut line if behind: drop the multi-harness diff and the CI gate; the single-agent **run → fail → autopsy → auto-fix → re-run-green** loop on the gmsaas fixture is a complete, winning demo on its own.

---

## The live demo (for a room of VCs + Anthropic engineers)

1. **Set the stakes (20s).** "Your new buyer is an AI agent — and it fails to adopt you *silently*." Show the real article-9 log line: Claude Code fetched Genymotion pricing → runbook in 10 seconds.
2. **Turn one loose, live.** Split screen. Left: a real sandboxed Claude Code agent, goal = *"from scratch, boot a cloud Android device and open an ADB shell with Genymotion."* Right: Agentboarding's live trajectory.
3. **Narrate the fight.** "It found the runbook… it's choosing between three pip installs… it just hit the auth wall — the runbook refuses to let it paste a token in its shell — watch it reason around that…" → device boots, ADB shell opens. (Or it fails — even better, see step 4.)
4. **The autopsy.** Frame-by-frame: "It stalled here. Why? Because the **Haiku summary** of your pricing page *dropped the device limit* — here's the exact lossy text the agent saw vs. your real HTML." The summarization-casualty, proven.
5. **The fix, live.** Agentboarding opens a **PR**: a Haiku-resistant rewrite of the mangled Q&A + the missing runbook step. **Re-run a fresh agent → it succeeds. AX Score 41 → 92.**
6. **The line.** "This is CI for the agent era. Every dev tool needs it the moment agents become the integrators. Claude Code, grading Claude Code, and shipping the fix."

Honest by construction: nothing is staged, the agent really runs, and the failure modes are real.

---

## Venture thesis

- **Market:** every API / developer-tool / SaaS company. The buyer is **DevRel, docs, growth, and PM** — the team accountable for activation and integration success. Today they A/B-test human onboarding; tomorrow their largest "new user" cohort is autonomous agents they can't see.
- **Why now:** agents just crossed from *reading* docs to *executing* integrations (Claude Code at 20M+ daily installs; article-9 is the proof). The pain is arriving this year, not in three.
- **Wedge → platform:** land as **adoptability CI** (per-product subscription + CI seats). Expand into the layers the rest of the tournament surfaced:
  - the auto-fix output becomes a **`buyers.txt`-style adoption manifest** (seed #3) the vendor ships;
  - getting agents past trial/auth walls becomes a **scoped-credential rail** (seed #2, "Trialhead");
  - the survival metric becomes a public **AX Score / HaikuShred leaderboard** (seed #11) dev tools display like a build badge.
- **Defensibility:** the **failure corpus + AX benchmark compounds** with every run; calibrating synthetic agents against **Rozz's proprietary real Claude Code session logs** is a moat no GEO vendor has; and owning the *score* ("AX Score") makes you the standard.
- **Why it beats a GEO-audit tool:** GEO tools sell a passive, crowded *mention count*. Agentboarding sells an *executed outcome and the fix that ships it* — an open category with a clear ROI and a clear budget owner.

---

## Risks & mitigations (from due diligence)

| Risk | Mitigation |
|---|---|
| **Live-demo nondeterminism** (agents vary run-to-run) | Aim live, but pre-record one known-good run as a fallback; the auth-trap recovery on the gmsaas fixture is reproducible; keep two fixtures ready. |
| **Sandbox safety** — agents execute arbitrary CLI | Disposable container, no real credentials, command allowlist, network egress limits. The runbook's own auth-trap is *showcased*, not bypassed. |
| **"Isn't this just evals?"** | No — SWE Atlas/SWE-bench grade the *agent*; Agentboarding grades the *product's* adoptability and **ships the fix**. Composio is infra *for* agents; we *test your product against* agents. |
| **Haiku-path fidelity** (Anthropic may change `WebFetch` internals) | Calibrate the replay against live Claude Code `WebFetch` behavior; self-healing recalibration; version-tag results. |
| **One-day scope** | The single-agent run→autopsy→fix→re-run loop on the existing gmsaas runbook is enough to win; multi-harness diff + CI gate are stretch. |

---

## Stretch goals

- **Multi-harness cross-diff** (Claude Code vs other coding agents) — "your product is adoptable by Claude Code but breaks Cursor here."
- **Public AX leaderboard** by category (Android tooling, CI/CD, vector DBs…) — attention-grabbing, becomes the standard.
- **`buyers.txt` emission** — the auto-fix bundle published as a signed adoption manifest.
- **Scoped-credential trial rail** so agents can complete a *paid* trial inside the test, safely.

---

*Built for Claude Build Day — Sat June 13, 2026, Shack15 SF. Opus 4.8 + Claude Code. Selected by an originality-first multi-agent tournament; see [TOURNAMENT.md](./TOURNAMENT.md) for the bracket and the prior-art due diligence.*
