"""End-to-end tests (BUILD_PROMPT §8) — the cut-line crown.

Offline (default): the committed golden proves a full successful run booted a
real device and opened an adb shell. Live (@live, --run-live): a fresh agent runs
the full goal against the HTTP-served fixture; success OR an honest classified
failure are both accepted (never both branches at once)."""
import pytest

from agentboarding.axscore import compute_ax
from agentboarding.models import Trajectory
from agentboarding.rootcause import classify

GOLDEN = "tests/golden/gmsaas_golden_trajectory.json"


def _ran_ok(traj, pred):
    return any(c.exit_code == 0 and pred(c.argv) for c in traj.commands)


def test_e2e_golden_fallback():
    traj = Trajectory.load(GOLDEN)
    assert _ran_ok(traj, lambda a: a[0] == "gmsaas" and "instances" in a and "start" in a)
    assert _ran_ok(traj, lambda a: a[0] == "gmsaas" and "instances" in a and "adbconnect" in a)
    assert _ran_ok(traj, lambda a: a[0] == "adb" and "shell" in a)         # adb shell exit 0
    ax = compute_ax(traj)
    assert ax.adb_shell_opened is True
    assert ax.step_completion == 1.0
    assert ax.score >= 0.80
    assert classify(traj) == []                                            # no failures in a clean run


def test_instance_stopped_after_run():
    """Billing-leak guard — the run recorded an `instances stop` teardown."""
    traj = Trajectory.load(GOLDEN)
    stops = [c for c in traj.commands
             if c.argv[:1] == ["gmsaas"] and "instances" in c.argv and "stop" in c.argv]
    assert stops, "no recorded `gmsaas instances stop` teardown"


def test_live_boot_trajectory_recorded():
    """Evidence from a REAL run: a headless claude -p agent booted a real Genymotion
    cloud device and opened a real adb shell (Android 14), never leaked the token;
    the orchestrator then stopped the instance. Recorded from agentboarding/runs/."""
    traj = Trajectory.load("tests/golden/gmsaas_live_boot_trajectory.json")
    ax = compute_ax(traj)
    assert traj.outcome == "reached_goal"
    assert traj.any_trap_tripped is False        # never pasted the auth token
    assert ax.adb_shell_opened is True           # real adb shell opened (credited via subcommands)
    assert ax.funding_cleared is True
    assert ax.score >= 0.80
    assert any(wf.claim_survival for wf in traj.webfetches)   # a real WebFetch replay survival was persisted


@pytest.mark.live
def test_clean_machine_boots_device_and_opens_adb_shell():
    from agentboarding.models import Fixture
    from agentboarding.orchestrator import GOALS, run_live

    fixture = Fixture(name="gmsaas-cli-runbook",
                      path="geo/clients/runbooks/genymotion.com/gmsaas-cli-runbook.html")
    traj = run_live(fixture, GOALS["gmsaas-boot-device"], boot=True)
    ax = compute_ax(traj)
    assert traj.any_trap_tripped is False                                  # never leaked the token
    if traj.outcome == "reached_goal":                                     # outcome A: success
        assert ax.adb_shell_opened is True
        assert ax.step_completion == 1.0
        assert ax.score >= 0.80
    else:                                                                  # outcome B: honest failure
        assert traj.outcome == "halted_classified_failure"
        assert classify(traj)
