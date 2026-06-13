"""Sandbox / isolation tests (BUILD_PROMPT §8)."""
import os

from agentboarding.sandbox import (
    CommandGate,
    Sandbox,
    build_sandbox_env,
    egress_allowed,
    env_has_forbidden_secret,
    pretooluse_decision,
    run_settings,
)


def test_no_real_creds_in_sandbox_env():
    base = {
        "PATH": "/usr/bin", "HOME": "/home/x",
        "AWS_SECRET_ACCESS_KEY": "shh", "POSTGRES_PASSWORD": "shh",
        "PINECONE_API_KEY": "shh", "OPENAI_API_KEY": "shh",
        "GENYMOTION_API_TOKEN": "gtok",
    }
    env = build_sandbox_env(base)
    assert not env_has_forbidden_secret(env)
    for k in ("AWS_SECRET_ACCESS_KEY", "POSTGRES_PASSWORD", "PINECONE_API_KEY", "OPENAI_API_KEY"):
        assert k not in env
    # the gmsaas-auto-read token is the ONLY secret kept (never pasted into the shell)
    assert env.get("GENYMOTION_API_TOKEN") == "gtok"


def test_command_gate_blocks_disallowed():
    gate = CommandGate()
    probe = "/tmp/agentboarding_gate_probe_should_not_exist"
    rec = gate.run(["rm", "-rf", probe])
    assert rec.exit_code == 126                       # blocked by the ARGV gate
    assert "BLOCKED" in rec.stderr
    assert not os.path.exists(probe)                  # never executed
    # an allow-listed command still runs
    ok = gate.run(["echo", "hello"])
    assert ok.exit_code == 0 and "hello" in ok.stdout


def test_pretooluse_hook_denies_read():
    assert pretooluse_decision("Read") == "deny"
    assert pretooluse_decision("Write") == "deny"
    assert pretooluse_decision("Edit") == "deny"
    assert pretooluse_decision("Bash") == "allow"
    s = run_settings("/tmp/x")
    assert "Read" in s["disallowedTools"]
    assert "PreToolUse" in s["hooks"]


def test_sandbox_is_disposable():
    with Sandbox() as sb:
        wd = sb.workdir
        assert wd and os.path.isdir(wd)
    assert not os.path.exists(wd)


def test_egress_limited():
    assert egress_allowed("http://127.0.0.1:8731/runbook.html") is True
    assert egress_allowed("https://pypi.org/simple/gmsaas/") is True
    assert egress_allowed("https://files.pythonhosted.org/packages/x") is True
    assert egress_allowed("https://api.geny.io/v1/instances") is True
    assert egress_allowed("https://abc.cloud.geny.io/ws") is True       # *.cloud.geny.io
    assert egress_allowed("http://evil.example.com/x") is False
