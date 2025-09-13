import os

import pytest


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line("markers", "localdata: requires local ladybird dataset; skipped in CI")


def require_localdata() -> None:
    if os.environ.get("COSMOS_ENABLE_LOCAL_TESTS") != "1":
        pytest.skip("Set COSMOS_ENABLE_LOCAL_TESTS=1 to run local data tests", allow_module_level=True)

