"""HaikuShred — faithful replay of Claude Code's WebFetch preprocessing pipe.

Per geo/README.md ("What we know about Claude Code's WebFetch"): WebFetch does
NOT pass page HTML to the model. It converts HTML -> markdown via Turndown
(which does NOT strip <style>), truncates to 100 KB (earlier content
prioritized), summarizes with Claude 3.5 Haiku under an *empty system prompt*
(the user's prompt is the only extraction lever), and clamps any verbatim quote
longer than 125 characters.

Replaying that pipe out-of-band lets us prove a whole class of adoption failures
as *summarization casualties*: the needed instruction is in the source HTML but
did not survive the lossy summary.

CAVEAT (do not over-claim fidelity): geo/README.md labels this pipe a
reverse-engineered spec, NOT an Anthropic-documented contract. We treat the spec
as the source of truth for replay *stages*, and evaluate survival with threshold
*bands* (median of N), never exact-string asserts against live Haiku output.
"""
from __future__ import annotations

import os
import re
import statistics
import subprocess
from dataclasses import dataclass, field
from typing import Callable, List, Optional

from dotenv import load_dotenv

from .constants import (
    HAIKU_MAX_TOKENS,
    HAIKU_MODEL,
    QUOTE_CLAMP_CHARS,
    TRUNCATE_BYTES,
)

load_dotenv()

STAGES = ["turndown", "truncate", "haiku", "quote_clamp"]


@dataclass
class HaikuShredResult:
    markdown: str
    truncated_markdown: str
    haiku_summary: str
    quote_clamp_events: int = 0
    dropped_claims: List[str] = field(default_factory=list)
    stages: List[str] = field(default_factory=list)
    turndown_engine: str = "approx"


# --------------------------------------------------------------------------- #
# Stage 1 — Turndown (HTML -> markdown). Node `turndown` if resolvable, else a
# documented Python approximation. Crucially: <style> is NOT stripped (CSS leaks
# into the markdown as text); <script> IS stripped (Turndown drops it).
# --------------------------------------------------------------------------- #
_NODE_TURNDOWN = """
const TurndownService = require('turndown');
let html = ''; process.stdin.on('data', d => html += d);
process.stdin.on('end', () => {
  const td = new TurndownService();
  process.stdout.write(td.turndown(html));
});
"""


def _node_turndown_available() -> bool:
    try:
        r = subprocess.run(
            ["node", "-e", "require.resolve('turndown')"],
            capture_output=True, timeout=10,
        )
        return r.returncode == 0
    except Exception:
        return False


def _turndown_node(html: str) -> str:
    r = subprocess.run(
        ["node", "-e", _NODE_TURNDOWN],
        input=html.encode("utf-8"), capture_output=True, timeout=30,
    )
    if r.returncode != 0:
        raise RuntimeError(r.stderr.decode("utf-8", "ignore"))
    return r.stdout.decode("utf-8", "ignore")


def _turndown_python(html: str) -> str:
    """Documented approximation: strip <script> (Turndown drops it) but KEEP
    <style> (Turndown does not strip it), then collect text with light markdown
    heading markers. Faithful enough for claim-survival measurement."""
    try:
        from bs4 import BeautifulSoup, NavigableString, Tag  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        for s in soup("script"):
            s.decompose()  # Turndown strips <script>; <style> is intentionally kept
        out: List[str] = []
        for el in soup.descendants:
            if isinstance(el, NavigableString):
                txt = str(el).strip()
                if not txt:
                    continue
                parent = el.parent.name if isinstance(el.parent, Tag) else ""
                if parent in ("h1", "h2", "h3", "h4", "h5", "h6"):
                    out.append("#" * int(parent[1]) + " " + txt)
                elif parent in ("code", "pre"):
                    out.append("`" + txt + "`")
                else:
                    out.append(txt)
        return "\n".join(out)
    except Exception:
        # last-resort: crude tag strip that keeps <style> text
        no_script = re.sub(r"(?is)<script.*?</script>", " ", html)
        return re.sub(r"(?s)<[^>]+>", "\n", no_script)


def to_markdown(html: str) -> tuple[str, str]:
    if _node_turndown_available():
        try:
            return _turndown_node(html), "node-turndown"
        except Exception:
            pass
    return _turndown_python(html), "approx"


# --------------------------------------------------------------------------- #
# Stage 2 — truncate to 100 KB (keep head; drop tail).
# --------------------------------------------------------------------------- #
def truncate_markdown(markdown: str, limit: int = TRUNCATE_BYTES) -> str:
    raw = markdown.encode("utf-8")
    if len(raw) <= limit:
        return markdown
    return raw[:limit].decode("utf-8", "ignore")


# --------------------------------------------------------------------------- #
# Stage 3 — Haiku summarize (empty system prompt; user_prompt steers extraction).
# --------------------------------------------------------------------------- #
def haiku_summarize(truncated_markdown: str, user_prompt: Optional[str] = None) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
    steer = user_prompt or "Summarize this web page so a developer can act on it."
    content = f"{steer}\n\n<page>\n{truncated_markdown}\n</page>"
    # Empty system prompt: we simply omit the `system` parameter.
    resp = client.messages.create(
        model=HAIKU_MODEL,
        max_tokens=HAIKU_MAX_TOKENS,
        messages=[{"role": "user", "content": content}],
    )
    return "".join(b.text for b in resp.content if getattr(b, "type", None) == "text")


# --------------------------------------------------------------------------- #
# Stage 4 — quote clamp: any verbatim span from source longer than 125 chars is
# clamped; count events.
# --------------------------------------------------------------------------- #
def clamp_quotes(summary: str, source: str, max_len: int = QUOTE_CLAMP_CHARS) -> tuple[str, int]:
    events = 0
    out = summary
    candidates = set()
    for chunk in re.split(r"[\n.;!?]", source):
        c = chunk.strip()
        if len(c) > max_len:
            candidates.add(c)
    for c in sorted(candidates, key=len, reverse=True):
        if c in out:
            out = out.replace(c, c[:max_len].rstrip() + "…")
            events += 1
    return out, events


# --------------------------------------------------------------------------- #
# Survival primitive — token recall of a claim against the (lossy) summary.
# Fully deterministic given a fixed haiku_summary.
# --------------------------------------------------------------------------- #
def _content_tokens(s: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", s.lower()))


def claim_survives(claim: str, result: HaikuShredResult) -> float:
    ct = _content_tokens(claim)
    if not ct:
        return 1.0
    st = _content_tokens(result.haiku_summary)
    return len(ct & st) / len(ct)


# --------------------------------------------------------------------------- #
# Public replay. `summarizer` is an injectable seam so deterministic stage tests
# avoid the network; production/live tests use the real Haiku call (default).
# --------------------------------------------------------------------------- #
def replay(
    source_html: str,
    user_prompt: Optional[str] = None,
    summarizer: Optional[Callable[[str, Optional[str]], str]] = None,
) -> HaikuShredResult:
    stages: List[str] = []
    summarize = summarizer or haiku_summarize

    markdown, engine = to_markdown(source_html)
    stages.append("turndown")

    truncated = truncate_markdown(markdown)
    stages.append("truncate")

    summary = summarize(truncated, user_prompt)
    stages.append("haiku")

    clamped, events = clamp_quotes(summary, source_html)
    stages.append("quote_clamp")

    return HaikuShredResult(
        markdown=markdown,
        truncated_markdown=truncated,
        haiku_summary=clamped,
        quote_clamp_events=events,
        dropped_claims=[],
        stages=stages,
        turndown_engine=engine,
    )


def median_survival(source_html: str, claim: str, runs: int = 5, user_prompt: Optional[str] = None) -> float:
    vals = [claim_survives(claim, replay(source_html, user_prompt=user_prompt)) for _ in range(runs)]
    return statistics.median(vals)


# --------------------------------------------------------------------------- #
# CLI: python -m agentboarding.haikushred --source <file> --claim "<c>" --runs 5
# --------------------------------------------------------------------------- #
def _main(argv: Optional[List[str]] = None) -> int:
    import argparse

    ap = argparse.ArgumentParser(description="HaikuShred WebFetch replay")
    ap.add_argument("--source", required=True, help="path to source HTML")
    ap.add_argument("--claim", required=True, help="claim to measure survival of")
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--user-prompt", default=None)
    args = ap.parse_args(argv)

    html = open(args.source, encoding="utf-8", errors="replace").read()
    med = median_survival(html, args.claim, runs=args.runs, user_prompt=args.user_prompt)
    print(f"median_survival over {args.runs} runs: {med:.3f}  (threshold 0.50)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
