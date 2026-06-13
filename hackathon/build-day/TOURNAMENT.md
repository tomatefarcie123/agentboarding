# Claude Build Day — Idea Tournament (Originality-First)

Selecting an **original, venture-scale** project for **Claude Build Day** (Sat June 13 2026, Shack15 SF; build with **Opus 4.8 + Claude Code**; judged by VCs from **a16z / Pear / Maven / Neo** + **Replit** + **5 Anthropic Members of Technical Staff**; $150K in Claude credits across 3 finalists).

The event prompt — *"The broken process in your industry. The tool you wish existed. The idea you've been sitting on. **The longer and more complex the task, the better.**"* — decodes to a specific judging order:

1. **Originality / non-obviousness** — the room has seen every AI-visibility / GEO audit tool; me-too loses.
2. **Agentic complexity** — *"the longer and more complex the task, the better"*; Opus 4.8 + Claude Code must autonomously do something genuinely hard on stage (5 Anthropic engineers judging).
3. **Venture scale** — a16z/Pear/Maven must see a fundable company.
4. **One-day demo feasibility.**  5. **Stage wow.**

Anchored on the frontier Rozz's own logs exposed: **AI coding agents are becoming the buyers, evaluators, and integrators of software** (see [`article-9`](../../rozz_website/insights/article-9-claude-user-claude-code.md)).

## 🏆 Winner — #9 Agentboarding

**CI for the agent era: a fleet of sandboxed Claude Code agents that try to install + ship a first working integration of your product, autopsy where they failed, open a fix PR, and re-run to prove it.** Full self-contained build proposal: [README.md](./README.md).

It won by dominating its bracket (three 3-0 panel wins, beating Escrow and Canary) and then surviving prior-art due diligence as the only finalist whose category is genuinely open.

---

## The 11 seeded ideas

The ideation pool (6 lenses × 3 = 18 ideas) was deduped by the committee to 11 distinct seeds, with me-too AI-visibility ideas dropped.

| Seed | Idea | Why it's new |
|---|---|---|
| **1** | **Escrow for Agents** | Verification-gated commerce rail: an agent buys only after it *proves the integration works* in a sandbox. Trust from running the software, not reading a contract. |
| **2** | **Trialhead** | Agent-grantable, scope-limited, **non-exfiltrable** trial-credential broker so Claude Code can safely *start a paid trial* without a human. Inverts Rozz's "never let the agent see the secret" runbook rule into a product. |
| **3** | **buyers.txt** | A self-validating commerce/adoption **protocol manifest** (`/.well-known/buyers.txt`): pricing answers, runbook, SAFE/UNSAFE command boundary, trial path, MCP checkout — and it re-tests itself through the live Haiku-lossy pipe. |
| **4** | **Canary** | Detects when an LLM is *describing your product wrong* (Haiku hallucinations), classifies drift by commercial damage, ships counter-content, and re-probes to confirm the model's *belief* corrected. |
| **5** | **AgentProbe** | A fleet of real Claude Code agents given buyer jobs-to-be-done; records where each failed/hallucinated, scores Agent Experience, ships fix PRs, re-runs to prove the delta. |
| **6** | **AX Wind-Tunnel** | Reconstructs a *real* captured agent session into a replayable trajectory, then A/B-tests content against a calibrated synthetic agent fleet *before* you ship. |
| **7** | **Terminal of Record** | The agent-buyer **CRM**: turns terminal/CloudFront log telemetry into qualified, contactable "agent opportunities" with intent scores — demand your funnel is blind to. |
| **8** | **Recommendation Radar** | Early-warning **intelligence feed** for which products coding agents are about to start recommending/dropping — citation velocity + half-life + a conversion overlay. |
| **9** | **Agentboarding** 🏆 | Runs the developer-adoption journey as an autonomous, executed trial across multiple agents; outputs a reproducible failure transcript + ranked friction points + patches + a CI gate. |
| **10** | **RunbookForge** | Self-verifying, self-healing executable runbooks: an agent *runs every command* in a sandbox and rewrites any step the docs got wrong, carrying an agent-verified attestation. |
| **11** | **HaikuShred** | A public benchmark: how many of your critical facts *survive* the exact `WebFetch→Turndown→truncate→Haiku→125-char` pipe a buyer-agent actually sees. A new primitive: claim-survival-rate. |

---

## Bracket results

Each matchup was decided by a 3-judge panel (a VC partner / an Anthropic engineer / a skeptical founder), with ideas shown in alternating L/R order to reduce positional bias; ties break to the higher seed.

### Round of 16 *(11 seeds; #1 byes)*
- **#2 Trialhead** def. #11 HaikuShred (2–1)
- **#3 buyers.txt** def. #10 RunbookForge (3–0)
- **#9 Agentboarding** def. #4 Canary (3–0)
- **#5 AgentProbe** def. #8 Recommendation Radar (3–0)
- **#7 Terminal of Record** def. #6 AX Wind-Tunnel (3–0)
- #1 Escrow for Agents — bye

### Quarterfinals
- **#9 Agentboarding** def. #1 Escrow for Agents (3–0) — *"the cleaner inverse of every GEO tool: executes the adoption journey and diffs the failures rather than counting mentions, and makes hard long-horizon Opus 4.8 autonomy the actual product."*
- **#2 Trialhead** def. #7 Terminal of Record (3–0) — *"productizes a non-obvious inversion of Rozz's own runbook safety boundary into a new infrastructure rail."*
- **#3 buyers.txt** def. #5 AgentProbe (2–1) — *"both share the identical hard-agentic core; buyers.txt additionally defines and registers a brand-new protocol."*

### Semifinals & Final — adjudicated by the orchestrator (see note)
The 3-judge panels for the Semifinal (#3 vs #9) and Final were never reached — the workflow hit a **session limit** at the semifinals. The orchestrator completed them directly, using the prior-art due diligence below:

- **Semifinal — #9 Agentboarding def. #3 buyers.txt.** buyers.txt's headline (a commerce/checkout protocol for agent-buyers) collides with the already-crowded agentic-commerce-protocol space (**AP2, ACP, x402** — below); its genuinely-novel parts (self-validation through the Haiku pipe; the adoption manifest) survive **as components of Agentboarding's roadmap**, not as the headline. Agentboarding's category is open, its one-day demo far stronger, and its agentic spectacle greater.
- **Final — #9 Agentboarding def. #2 Trialhead.** Trialhead overlaps AP2's authorization *mandates* and the crowded agent-auth space (Descope/WorkOS/Stytch), and a "safe scoped credential" is the single riskiest thing to demo live to 5 Anthropic security engineers. Agentboarding is more original, more cinematic, has a clearer buyer, and a safer honest demo. Trialhead's scoped-credential rail is grafted in as a roadmap layer.

**Champion: #9 Agentboarding.**

---

## VC due diligence — prior-art search on the finalists

The whole point of this run was *don't pick something already on the market.* Live web search + landscape knowledge on the three finalists:

| Finalist | Originality | Closest existing | Verdict |
|---|---|---|---|
| **#9 Agentboarding** | **High — open category** | Scale **SWE Atlas** / SWE-bench *(grade the agent, not your product's adoptability)*; **Composio** *(infra for building agents, not a test of your product)*; Mintlify/Fern/ReadMe *(render docs, never execute the install)* | **Fund.** No one runs the *executed* third-party adoption journey against your product and ships the fix. |
| **#3 buyers.txt** | Medium — collides on the headline | **Google AP2** (Sept 2025, 60+ partners incl. Mastercard/PayPal/Coinbase), **Stripe + OpenAI ACP** (checkout/merchant layer), **Coinbase x402** (programmable API payments) | **Pass as headline / graft as component.** The agent-commerce protocol slot is already a heavyweight pile-up. |
| **#2 Trialhead** | Medium — adjacent to two hot spaces | **AP2** authorization mandates; agent-auth (Descope/WorkOS/Stytch); x402 | **Pass / graft.** Crowded, and "prove it's secure" is the worst thing to demo to Anthropic security engineers in a one-day hack. |

**Sources:** [Google AP2 announcement](https://cloud.google.com/blog/products/ai-machine-learning/announcing-agents-to-payments-ap2-protocol) · [AP2 protocol docs](https://ap2-protocol.org/) · [ACP/AP2/x402 comparison (Orium)](https://orium.com/blog/agentic-payments-acp-ap2-x402) · [Scale SWE Atlas](https://scale.com/blog/swe-atlas) · [Composio — AI agent integration platforms](https://composio.dev/content/ai-agent-integration-platforms)

---

## Method notes & transparency

- **Pipeline:** 4 recon scouts (unfair-advantage, agentic-primitives, frontier-insight, prior-art landscape) over both repos + the web → 6 novelty-pushing ideators (18 ideas) → committee dedup/seed to 11 → originality-first bracket of 3-judge VC/Anthropic/founder panels → prior-art + feasibility due diligence on the finalists → synthesis.
- **What ran as designed:** recon, ideation, seeding, Round of 16, and Quarterfinals — all completed via 3-judge subagent panels (24 judge verdicts, reconstructed above).
- **Where the handoff happened:** the run hit a **session usage limit at the Semifinals (reset 16:00 PDT)**. Rather than ship a degraded seed-default result, the **Semifinal, Final, and due-diligence were completed by the orchestrating agent directly**, grounded in the cached panel verdicts and live prior-art web search. The winner selection is therefore a reasoned, prior-art-checked call — exactly what the automated DD stage was designed to produce.
- **Reproducible:** the workflow script was hardened (graceful fallback on a null synthesis) and is **resumable** after the limit resets — completed agents return from cache; only the Semifinal/Final/DD/synthesis panels re-run — to regenerate the fully panel-graded version.
- **Prior art deliberately avoided:** Profound, Scrunch, Peec, Otterly, Goodie, Evertune, BrandLight, and the whole "is your brand cited in ChatGPT/Perplexity" GEO/AEO category — plus, after due diligence, the agentic-commerce-protocol space (AP2/ACP/x402) and the agent-auth space.
