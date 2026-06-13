"""Funding wall + x402 reference-rail tests (BUILD_PROMPT §8)."""
import json
import urllib.error
import urllib.request

import pytest

from agentboarding.axscore import compute_ax
from agentboarding.funding import (
    agent_holds_reusable_instrument,
    detect_funding_wall,
    preflight_funding,
    should_start_live_run,
)
from agentboarding.models import CommandRecord, Trajectory, TrajectoryRecord
from agentboarding.runloop import prove_fix
from agentboarding.x402_rail import X402Rail, serve

FUNDING_BASELINE = "tests/golden/gmsaas_funding_baseline_trajectory.json"
FUNDING_POSTFIX = "tests/golden/gmsaas_funding_postfix_golden.json"


def _get(url):
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def _post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_preflight_funding_probe():
    unfunded = preflight_funding(prober=lambda: {"ok": False, "credits": 0, "detail": "zero-credit stub"})
    assert unfunded.funded is False
    assert should_start_live_run(unfunded) is False          # orchestrator refuses; no billable call
    funded = preflight_funding(prober=lambda: {"ok": True, "credits": 100, "detail": "ok"})
    assert funded.funded is True and should_start_live_run(funded) is True


def test_detect_funding_wall_signature():
    f = detect_funding_wall(Trajectory.load(FUNDING_BASELINE))
    assert f is not None and f.failure_class == "funding_wall"
    # a clean product error must NOT be read as a funding wall
    prod = Trajectory(run_id="p", outcome="halted_classified_failure", records=[
        TrajectoryRecord(step=1, type="command", command=CommandRecord(
            argv=["gmsaas", "--format", "json", "instances", "start", "r", "n"],
            exit_code=1, stderr="Internal error: device pool temporarily unavailable")),
    ])
    assert detect_funding_wall(prod) is None


def test_x402_returns_402_then_grants():
    srv = serve()
    try:
        code, desc = _get(srv.base_url + "/resource")
        assert code == 402                                   # real HTTP 402 Payment Required
        acc = desc["accepts"][0]
        assert acc["price"] and acc["scope"] and acc["expiresInSeconds"] > 0
        code2, grant = _post(srv.base_url + "/pay", {"nonce": acc["nonce"], "mode": "test"})
        assert code2 == 200
        assert grant["single_use"] is True
        assert grant["max_run_duration"] > 0
        assert grant["settle_mode"] == "test"
        assert "expires_at" in grant
    finally:
        srv.stop()


def test_x402_grant_is_scoped_and_single_use():
    clock = [1000.0]
    rail = X402Rail(ttl_seconds=60, now=lambda: clock[0])

    g = rail.settle({"nonce": rail.payment_required()["accepts"][0]["nonce"], "mode": "test"})
    assert rail.redeem(g.grant_id)["ok"] is True
    with pytest.raises(PermissionError):                     # single-use
        rail.redeem(g.grant_id)

    g2 = rail.settle({"nonce": rail.payment_required()["accepts"][0]["nonce"], "mode": "test"})
    clock[0] += 10_000                                       # past expiry
    with pytest.raises(PermissionError):
        rail.redeem(g2.grant_id)

    blob = json.dumps(g.to_dict()).lower()
    assert "card" not in blob and "secret" not in blob       # never a reusable instrument


def test_funding_wall_fixed_by_x402_rerun():
    # Stand up the x402 rail as the patched surface (the endpoint the vendor lacks);
    # the agent transacts test-mode and gets a scoped grant.
    rail = X402Rail()
    grant = rail.settle({"nonce": rail.payment_required()["accepts"][0]["nonce"], "mode": "test"})
    assert rail.redeem(grant.grant_id)["ok"] is True

    post = Trajectory.load(FUNDING_POSTFIX)
    assert compute_ax(post).funding_cleared is True          # re-run cleared the wall
    delta = prove_fix(baseline=FUNDING_BASELINE, postfix=post)
    assert delta.improved is True


def test_funding_blocked_injection_is_detected_and_labeled():
    from agentboarding.funding import INJECTED_FUNDING_ERROR, inject_blocked_start
    rec = inject_blocked_start(["gmsaas", "--format", "json", "instances", "start", "r-1", "demo"])
    assert rec.exit_code == 1
    assert "INJECTED" in rec.stderr                       # honestly labeled, never a real billing event
    t = Trajectory(run_id="blocked", outcome="halted_classified_failure",
                   records=[TrajectoryRecord(step=1, type="command", command=rec)])
    f = detect_funding_wall(t)
    assert f is not None and f.failure_class == "funding_wall"


def test_agent_never_holds_reusable_payment_instrument():
    post = Trajectory.load(FUNDING_POSTFIX)
    # mirror of the auth-trap: no raw card / reusable billing token anywhere
    assert agent_holds_reusable_instrument(post, env={"GENYMOTION_API_TOKEN": "auto-read-env-var"}) is False
