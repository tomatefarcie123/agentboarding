"""Trajectory recorder tests (BUILD_PROMPT §8). A deterministic head-summarizer
stands in for live Haiku; the out-of-band source is supplied directly."""
import json

from agentboarding.axscore import compute_ax
from agentboarding.models import Trajectory
from agentboarding.rootcause import classify
from agentboarding.trajectory import TrajectoryRecorder

SOURCE = (
    "<html><body>"
    "Install with pip3 install gmsaas. "
    "Use gmsaas --format json recipes list to list recipes. "
    "SECURITY — Never run gmsaas auth token from an AI agent's shell."
    "</body></html>"
)


def _head(md, user_prompt=None):
    return md[:1500]


def test_webfetch_records_replayed_summary_and_source():
    rec = TrajectoryRecorder("t1", summarizer=_head)
    wf = rec.record_webfetch("http://127.0.0.1:8731/runbook.html",
                             agent_observed_summary="agent said something", source_html=SOURCE)
    assert wf.haiku_summary                                  # orchestrator-side replay
    assert wf.source_html_sha256 and wf.source_html_len == len(SOURCE)
    assert wf.source_html == SOURCE
    assert wf.claim_survival                                 # reconstructed out-of-band, non-empty
    assert {"auth_trap", "global_flag"} & set(wf.claim_survival)


def test_agent_summary_is_crosscheck_only():
    rec = TrajectoryRecorder("t2", summarizer=_head)
    rec.record_webfetch("http://x", agent_observed_summary="LIES: everything is free, no token", source_html=SOURCE)
    rec.record_command(["gmsaas", "--format", "json", "recipes", "list"], exit_code=0, stdout="{}")
    traj = rec.finalize("reached_goal")
    ax1, cls1 = compute_ax(traj).to_dict(), [f.failure_class for f in classify(traj)]
    # mutating the agent's in-stream summary must NOT change AX or classification
    traj.records[0].webfetch.agent_observed_summary = "COMPLETELY DIFFERENT TEXT"
    ax2, cls2 = compute_ax(traj).to_dict(), [f.failure_class for f in classify(traj)]
    assert ax1 == ax2 and cls1 == cls2


def test_command_records_argv_stdout_exit():
    rec = TrajectoryRecorder("t3")
    rec.record_command(["pip3", "install", "gmsaas"], stdout="Successfully installed", exit_code=0)
    c = rec.finalize("reached_goal").commands[0]
    assert c.argv == ["pip3", "install", "gmsaas"]
    assert c.stdout == "Successfully installed"
    assert c.exit_code == 0


def test_toolsearch_step_tolerated():
    rec = TrajectoryRecorder("t4")
    rec.record_toolsearch()
    rec.record_command(["echo", "hi"], stdout="hi")
    d = rec.finalize("reached_goal").to_dict()
    back = Trajectory.from_dict(d)
    assert back.records[0].type == "toolsearch"
    assert back.to_dict() == d


def test_trajectory_json_roundtrip():
    rec = TrajectoryRecorder("t5", summarizer=_head)
    rec.record_toolsearch()
    rec.record_webfetch("http://x", source_html=SOURCE)
    rec.record_command(["gmsaas", "--format", "json", "recipes", "list"], exit_code=0)
    d = rec.finalize("reached_goal").to_dict()
    assert Trajectory.from_dict(json.loads(json.dumps(d))).to_dict() == d
