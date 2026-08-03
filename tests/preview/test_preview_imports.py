from __future__ import annotations

import subprocess
import sys


def _run_isolated(script: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(  # noqa: S603
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
    )


def test_preview_contract_import_does_not_depend_on_sdk_import_order() -> None:
    result = _run_isolated(
        """
from cosmos.preview.contracts import PreviewRect
from cosmos.preview import PreviewRunResult, RenderOptions
assert PreviewRect.__name__ == "PreviewRect"
assert PreviewRunResult.__name__ == "PreviewRunResult"
assert RenderOptions.__name__ == "RenderOptions"
"""
    )
    assert result.returncode == 0, result.stderr


def test_sdk_first_preview_imports_keep_existing_public_names() -> None:
    result = _run_isolated(
        """
from cosmos.sdk import PreviewRunResult, RenderOptions, preview, preview_curated_views
from cosmos.preview.contracts import PreviewRect
assert PreviewRunResult.__name__ == "PreviewRunResult"
assert RenderOptions.__name__ == "RenderOptions"
assert preview.__name__ == "preview"
assert preview_curated_views.__name__ == "preview_curated_views"
assert PreviewRect.__name__ == "PreviewRect"
"""
    )
    assert result.returncode == 0, result.stderr
