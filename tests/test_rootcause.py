"""Root-cause classifier tests (BUILD_PROMPT §8) — one crafted trajectory per
class, each pure over recorded JSON."""
from pathlib import Path

from agentboarding.models import (
    CommandRecord, Trajectory, TrajectoryRecord, WebFetchRecord,
)
from agentboarding.rootcause import classify

# A tiny source surface containing the canonical global-flag form + auth trap.
SOURCE = (
    "<html><body>"
    "Install: pip3 install gmsaas. "
    "Use gmsaas --format json recipes list to list recipes. "
    "SECURITY — Never run gmsaas auth token from an AI agent's shell. "
    "Flags: --format, --user, --break-system-packages."
    "</body></html>"
)


def _wf(source=SOURCE, survival=None):
    return TrajectoryRecord(
        step=1, type="webfetch",
        webfetch=WebFetchRecord(
            url="http://127.0.0.1:8731/runbook.html", source_html=source,
            source_html_len=len(source), source_html_sha256="deadbeef",
            haiku_summary="summary", claim_survival=survival or {},
        ),
    )


def _cmd(step, argv, exit_code=0, stdout="", stderr=""):
    return TrajectoryRecord(step=step, type="command",
                            command=CommandRecord(argv=argv, stdout=stdout, stderr=stderr, exit_code=exit_code))


def _traj(commands, source=SOURCE, survival=None):
    return Trajectory(run_id="t", outcome="halted_classified_failure",
                      records=[_wf(source, survival)] + commands)


def _classes(failures):
    return {f.failure_class for f in failures}


def test_product_broken():
    t = _traj([_cmd(2, ["gmsaas", "--format", "json", "recipes", "list"],
                    exit_code=1, stderr="Segmentation fault (core dumped)")])
    cls = _classes(classify(t))
    assert cls == {"product_broken"}


def test_docs_ambiguous():
    t = _traj([_cmd(2, ["gmsaas", "recipes", "list", "--format", "json"],
                    exit_code=2, stderr="unrecognized arguments: --format")])
    cls = _classes(classify(t))
    assert cls == {"docs_ambiguous"}


def test_hallucinated_flag():
    t = _traj([_cmd(2, ["gmsaas", "--format", "json", "instances", "start", "r-1", "demo", "--turbo"],
                    exit_code=2, stderr="no such option: --turbo")])
    cls = _classes(classify(t))
    assert cls == {"hallucinated_flag"}


def test_summarization_casualty():
    # The global-flag instruction is in source but survived only 0.30 (< 0.50).
    t = _traj([], survival={"global_flag": 0.30})
    failures = classify(t)
    assert _classes(failures) == {"summarization_casualty"}
    assert failures[0].claim == "global_flag"


def test_funding_wall():
    t = _traj([_cmd(2, ["gmsaas", "--format", "json", "instances", "start", "r-1", "demo"],
                    exit_code=1, stderr="HTTP 402 Payment Required: insufficient cloud credits")])
    cls = _classes(classify(t))
    assert cls == {"funding_wall"}            # separated from product_broken by signature
    assert "product_broken" not in cls


def test_golden_classifies_empty():
    golden = Trajectory.load(Path("tests/golden/gmsaas_golden_trajectory.json"))
    assert classify(golden) == []
