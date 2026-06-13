"""Shared pytest config for the Agentboarding suite.

`live` tests (real Haiku / real headless agent / real cloud) are skipped unless
`--run-live` is passed, so the default suite is deterministic and offline.
"""
import pytest


def pytest_addoption(parser):
    parser.addoption(
        "--run-live", action="store_true", default=False,
        help="run tests marked @pytest.mark.live (network / Haiku / cloud)",
    )


def pytest_configure(config):
    config.addinivalue_line("markers", "live: requires network / live Haiku / Genymotion cloud")


def pytest_collection_modifyitems(config, items):
    if config.getoption("--run-live"):
        return
    skip_live = pytest.mark.skip(reason="needs --run-live (network/cloud)")
    for item in items:
        if "live" in item.keywords:
            item.add_marker(skip_live)
