"""Re-run delta tests (BUILD_PROMPT §8). Deterministic via committed goldens."""
from pathlib import Path

from agentboarding.axscore import compute_ax
from agentboarding.models import Trajectory
from agentboarding.runloop import prove_fix

BASELINE = "tests/golden/gmsaas_baseline_trajectory.json"
POSTFIX = "tests/golden/gmsaas_postfix_golden_trajectory.json"


def test_axscore_increases_after_fix():
    before = compute_ax(Trajectory.load(BASELINE)).score
    assert before < 0.60
    delta = prove_fix(baseline=BASELINE, postfix=POSTFIX)
    assert delta.improved is True
    assert delta.after > delta.before
    assert delta.before == before
