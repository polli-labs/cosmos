from __future__ import annotations

import pytest
from cosmos.preview.selectors import (
    FrameSelectorError,
    parse_frame_selector,
    resolve_frame_selector,
)


def test_parse_frame_selector_absolute() -> None:
    selector = parse_frame_selector("12.5")
    assert selector.kind == "absolute"
    assert selector.absolute_sec == 12.5


def test_parse_frame_selector_anchor_with_offset() -> None:
    selector = parse_frame_selector("end-1.25")
    assert selector.kind == "anchor"
    assert selector.anchor == "end"
    assert selector.offset_sec == -1.25


def test_resolve_anchor_mid_uses_trim_window() -> None:
    selector = parse_frame_selector("mid")
    resolved, warnings = resolve_frame_selector(
        selector,
        duration_sec=30.0,
        trim_start_sec=10.0,
        trim_end_sec=18.0,
    )
    assert resolved == 14.0
    assert warnings == []


def test_resolve_selector_clamps_and_warns() -> None:
    selector = parse_frame_selector("end+10")
    resolved, warnings = resolve_frame_selector(
        selector,
        duration_sec=12.0,
        trim_start_sec=2.0,
        trim_end_sec=8.0,
    )
    assert resolved == 12.0
    assert any("clamped" in warning for warning in warnings)


def test_parse_frame_selector_rejects_invalid() -> None:
    with pytest.raises(FrameSelectorError):
        parse_frame_selector("later")
