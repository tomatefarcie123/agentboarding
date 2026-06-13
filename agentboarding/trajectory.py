"""Trajectory recorder — captures every event of a run and persists it as JSON.

CRITICAL (BUILD_PROMPT §3.3): source-HTML reconstruction is ORCHESTRATOR-SIDE,
not agent-observed. The agent's in-stream WebFetch result is only the Haiku
summary string. So for each URL the agent fetches, the recorder INDEPENDENTLY
re-fetches that URL out-of-band and runs HaikuShred itself to reconstruct BOTH
halves — the source HTML (hash + length + full text) and a replayed Haiku
summary + per-claim survival floats. The agent's own summary is stored as
`agent_observed_summary` and used at most as a cross-check; AX/classify never
read it as the source.
"""
from __future__ import annotations

import hashlib
import urllib.request
from pathlib import Path
from typing import Callable, Dict, List, Optional

from .constants import CLAIM_TEXTS, SURVIVAL_THRESHOLD
from .haikushred import claim_survives, replay
from .models import (
    CommandRecord,
    Fixture,
    Goal,
    Trajectory,
    TrajectoryRecord,
    WebFetchRecord,
)

DEFAULT_USER_PROMPT = "Summarize this page for a developer who wants to install and use this tool."


def _http_get(url: str, timeout: int = 15) -> str:
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


class TrajectoryRecorder:
    def __init__(
        self,
        run_id: str,
        goal: Optional[Goal] = None,
        fixture: Optional[Fixture] = None,
        *,
        fetcher: Optional[Callable[[str], str]] = None,
        summarizer: Optional[Callable[[str, Optional[str]], str]] = None,
        claims: Optional[Dict[str, str]] = None,
        user_prompt: str = DEFAULT_USER_PROMPT,
    ):
        self.run_id = run_id
        self.goal = goal
        self.fixture = fixture
        self._fetcher = fetcher or _http_get          # OUT-OF-BAND fetch
        self._summarizer = summarizer                 # None => live Haiku
        self._claims = claims or dict(CLAIM_TEXTS)
        self._user_prompt = user_prompt
        self._records: List[TrajectoryRecord] = []
        self._step = 0

    def _next(self) -> int:
        self._step += 1
        return self._step

    # -- step recorders ------------------------------------------------------ #
    def record_toolsearch(self, note: str = "agent selected WebFetch via ToolSearch") -> None:
        self._records.append(TrajectoryRecord(step=self._next(), type="toolsearch", note=note))

    def record_webfetch(self, url: str, agent_observed_summary: str = "",
                         source_html: Optional[str] = None) -> WebFetchRecord:
        # Reconstruct BOTH halves out-of-band; never trust the agent's summary as source.
        src = source_html if source_html is not None else self._fetcher(url)
        result = replay(src, user_prompt=self._user_prompt, summarizer=self._summarizer)
        survival = {
            key: claim_survives(text, result)
            for key, text in self._claims.items()
            if text.lower() in src.lower()            # only claims actually on this page
        }
        wf = WebFetchRecord(
            url=url,
            source_html_sha256=hashlib.sha256(src.encode("utf-8")).hexdigest(),
            source_html_len=len(src),
            source_html=src,
            haiku_summary=result.haiku_summary,
            haiku_summary_len=len(result.haiku_summary),
            agent_observed_summary=agent_observed_summary,   # CROSS-CHECK ONLY
            dropped_claims=[k for k, v in survival.items() if v < SURVIVAL_THRESHOLD],
            quote_clamp_events=result.quote_clamp_events,
            claim_survival=survival,
        )
        self._records.append(TrajectoryRecord(step=self._next(), type="webfetch", webfetch=wf))
        return wf

    def record_command(self, argv: List[str], stdout: str = "", stderr: str = "",
                        exit_code: int = 0, trap_tripped: bool = False, note: Optional[str] = None,
                        subcommands: Optional[List[List[str]]] = None) -> None:
        self._records.append(TrajectoryRecord(
            step=self._next(), type="command",
            command=CommandRecord(argv=list(argv), stdout=stdout, stderr=stderr,
                                  exit_code=exit_code, subcommands=subcommands),
            trap_tripped=trap_tripped, note=note,
        ))

    def record_tool_result(self, note: str) -> None:
        self._records.append(TrajectoryRecord(step=self._next(), type="tool_result", note=note))

    # -- finalize ------------------------------------------------------------ #
    def finalize(self, outcome: str) -> Trajectory:
        return Trajectory(run_id=self.run_id, goal=self.goal, fixture=self.fixture,
                          outcome=outcome, records=list(self._records))

    def save(self, outcome: str, base_dir: str | Path = "agentboarding/runs") -> Path:
        traj = self.finalize(outcome)
        path = Path(base_dir) / self.run_id / "trajectory.json"
        traj.save(path)
        return path
