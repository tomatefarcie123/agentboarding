"""AX Score determinism tests (BUILD_PROMPT §8). compute_ax is pure over recorded
JSON and reads the persisted survival floats — it never re-invokes Haiku."""
from pathlib import Path

from agentboarding.axscore import compute_ax
from agentboarding.constants import (
    AX_W_FIRST_CALL, AX_W_STEP, AX_W_SURVIVAL, AX_W_TRAP,
)
from agentboarding.models import Trajectory

GOLDEN = Path("tests/golden/gmsaas_golden_trajectory.json")


def _golden() -> Trajectory:
    return Trajectory.load(GOLDEN)


def test_golden_score_exact():
    ax = compute_ax(_golden())
    assert ax.score == 0.94
    assert ax.summarization_survival == 0.60          # persisted mean, read not recomputed
    assert ax.reached_first_working_call is True
    assert ax.recovery_from_trap == 1.0
    assert ax.adb_shell_opened is True
    assert ax.step_completion == 1.0


def test_components_derive_score():
    ax = compute_ax(_golden())
    a = 1.0 if ax.reached_first_working_call else 0.0
    expected = round(
        AX_W_FIRST_CALL * a
        + AX_W_STEP * ax.step_completion
        + AX_W_TRAP * ax.recovery_from_trap
        + AX_W_SURVIVAL * ax.summarization_survival,
        6,
    )
    assert ax.score == expected


def test_step_completion_full_precision():
    # Drop the final adb-shell step from the golden -> 5/6 completed.
    t = _golden()
    t.records = [r for r in t.records
                 if not (r.command and r.command.argv[:2] == ["adb", "shell"])]
    ax = compute_ax(t)
    assert abs(ax.step_completion - 5 / 6) < 1e-12          # 0.8333...
    assert ax.step_completion != round(ax.step_completion, 2)  # not pre-rounded to 0.83
    assert ax.adb_shell_opened is False


def test_recompute_is_stable():
    t = _golden()
    assert compute_ax(t).to_dict() == compute_ax(t).to_dict()
