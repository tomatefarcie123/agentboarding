"""Data model for Agentboarding.

Every cross-module contract lives here: the Trajectory (what the recorder writes
and the scorer/classifier read), the AXScore, Failure, Fix, Delta, and the small
config/value objects. All types JSON round-trip losslessly so golden trajectories
load through exactly the same path a live run writes.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #
@dataclass
class Goal:
    """An adoption objective handed to a sandboxed agent."""
    name: str
    description: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Goal":
        return cls(name=d.get("name", ""), description=d.get("description", ""))


@dataclass
class Fixture:
    """A product's public surface (a runbook HTML file) served over HTTP."""
    name: str
    path: str

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Fixture":
        return cls(name=d.get("name", ""), path=d.get("path", ""))


@dataclass
class SandboxConfig:
    """Disposable per-run sandbox configuration."""
    workdir: Optional[str] = None
    allowed_executables: List[str] = field(default_factory=list)
    egress_allowlist: List[str] = field(default_factory=list)
    strict: bool = True


# --------------------------------------------------------------------------- #
# Trajectory records
# --------------------------------------------------------------------------- #
@dataclass
class WebFetchRecord:
    """Both halves of a WebFetch, reconstructed orchestrator-side (§3.3).

    The agent's in-stream WebFetch result is ONLY the Haiku summary string; the
    recorder independently re-fetches the URL out-of-band and runs HaikuShred to
    reconstruct the source HTML + a replayed summary + per-claim survival floats.
    """
    url: str
    source_html_sha256: str = ""
    source_html_len: int = 0
    source_html: str = ""                      # full text, orchestrator-fetched
    haiku_summary: str = ""                     # orchestrator-side replayed lossy text
    haiku_summary_len: int = 0
    agent_observed_summary: str = ""            # the agent's in-stream summary; CROSS-CHECK ONLY
    dropped_claims: List[str] = field(default_factory=list)
    quote_clamp_events: int = 0
    claim_survival: Dict[str, float] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "WebFetchRecord":
        return cls(
            url=d.get("url", ""),
            source_html_sha256=d.get("source_html_sha256", ""),
            source_html_len=int(d.get("source_html_len", 0) or 0),
            source_html=d.get("source_html", ""),
            haiku_summary=d.get("haiku_summary", ""),
            haiku_summary_len=int(d.get("haiku_summary_len", 0) or 0),
            agent_observed_summary=d.get("agent_observed_summary", ""),
            dropped_claims=list(d.get("dropped_claims", []) or []),
            quote_clamp_events=int(d.get("quote_clamp_events", 0) or 0),
            claim_survival={k: float(v) for k, v in (d.get("claim_survival", {}) or {}).items()},
        )


@dataclass
class CommandRecord:
    """A Bash command the agent executed inside the sandbox.

    Agents often run COMPOUND shell commands (`echo ...; adb -s X shell ...`).
    `subcommands` holds the decomposed sub-command argv lists so the scorer can
    credit a step buried after a `;`/`&&`/`|`. None => treat [argv] as the only one.
    """
    argv: List[str] = field(default_factory=list)
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    subcommands: Optional[List[List[str]]] = None

    @property
    def all_argvs(self) -> List[List[str]]:
        return self.subcommands if self.subcommands else [self.argv]

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CommandRecord":
        subs = d.get("subcommands")
        return cls(
            argv=list(d.get("argv", []) or []),
            stdout=d.get("stdout", ""),
            stderr=d.get("stderr", ""),
            exit_code=int(d.get("exit_code", 0) or 0),
            subcommands=[list(s) for s in subs] if subs else None,
        )


# Valid trajectory step types.
STEP_TYPES = ("toolsearch", "webfetch", "command", "tool_result")


@dataclass
class TrajectoryRecord:
    """One step of a run."""
    step: int
    type: str
    ts: Optional[str] = None
    webfetch: Optional[WebFetchRecord] = None
    command: Optional[CommandRecord] = None
    trap_tripped: bool = False
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        out: Dict[str, Any] = {"step": self.step, "ts": self.ts, "type": self.type}
        if self.webfetch is not None:
            out["webfetch"] = asdict(self.webfetch)
        if self.command is not None:
            out["command"] = asdict(self.command)
        out["trap_tripped"] = self.trap_tripped
        out["note"] = self.note
        return out

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "TrajectoryRecord":
        return cls(
            step=int(d.get("step", 0)),
            type=d.get("type", ""),
            ts=d.get("ts"),
            webfetch=WebFetchRecord.from_dict(d["webfetch"]) if d.get("webfetch") else None,
            command=CommandRecord.from_dict(d["command"]) if d.get("command") else None,
            trap_tripped=bool(d.get("trap_tripped", False)),
            note=d.get("note"),
        )


@dataclass
class Trajectory:
    """The full record of one run; persisted to runs/<run_id>/trajectory.json."""
    run_id: str
    goal: Optional[Goal] = None
    fixture: Optional[Fixture] = None
    outcome: str = ""
    records: List[TrajectoryRecord] = field(default_factory=list)

    # -- convenience accessors used by the pure scorer / classifier ---------- #
    @property
    def commands(self) -> List[CommandRecord]:
        return [r.command for r in self.records if r.command is not None]

    @property
    def webfetches(self) -> List[WebFetchRecord]:
        return [r.webfetch for r in self.records if r.webfetch is not None]

    @property
    def any_trap_tripped(self) -> bool:
        return any(r.trap_tripped for r in self.records)

    def command_records(self) -> List[TrajectoryRecord]:
        return [r for r in self.records if r.command is not None]

    # -- serialization ------------------------------------------------------- #
    def to_dict(self) -> Dict[str, Any]:
        return {
            "run_id": self.run_id,
            "goal": asdict(self.goal) if self.goal else None,
            "fixture": asdict(self.fixture) if self.fixture else None,
            "outcome": self.outcome,
            "records": [r.to_dict() for r in self.records],
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "Trajectory":
        return cls(
            run_id=d.get("run_id", ""),
            goal=Goal.from_dict(d["goal"]) if d.get("goal") else None,
            fixture=Fixture.from_dict(d["fixture"]) if d.get("fixture") else None,
            outcome=d.get("outcome", ""),
            records=[TrajectoryRecord.from_dict(r) for r in d.get("records", [])],
        )

    def save(self, path: str | Path) -> None:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.to_dict(), indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: str | Path) -> "Trajectory":
        return cls.from_dict(json.loads(Path(path).read_text()))


# --------------------------------------------------------------------------- #
# Outputs
# --------------------------------------------------------------------------- #
@dataclass
class Failure:
    """One classified failure produced by the root-cause classifier."""
    failure_class: str
    step: int = -1
    claim: Optional[str] = None
    detail: str = ""
    argv: Optional[List[str]] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Fix:
    """A concrete patch produced by the auto-fix generator for one Failure."""
    failure_class: str
    fix_type: str               # "qapage_jsonld" | "runbook_diff" | "llms_entry" | "x402_rail" | "human_flag" | "flag_clarification"
    content: str = ""
    target: str = ""
    needs_human: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AXScore:
    """Outcome-based score, derived (never independently stored) from components."""
    run_id: str
    reached_first_working_call: bool
    step_completion: float
    recovery_from_trap: float
    summarization_survival: float
    funding_cleared: bool
    adb_shell_opened: bool
    score: float
    outcome: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class Delta:
    """Result of a re-run-to-prove-delta loop."""
    before: float
    after: float
    improved: bool

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FundingStatus:
    """Result of a funding pre-flight probe."""
    funded: bool
    detail: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
