from __future__ import annotations

import re
from dataclasses import dataclass

_SELECTOR_RE = re.compile(r"^(start|mid|end)([+-]\d+(?:\.\d+)?)?$")


@dataclass(frozen=True)
class FrameSelector:
    raw: str
    kind: str
    anchor: str | None = None
    offset_sec: float = 0.0
    absolute_sec: float | None = None


class FrameSelectorError(ValueError):
    pass


def parse_frame_selector(raw: str) -> FrameSelector:
    value = raw.strip().lower()
    if not value:
        raise FrameSelectorError("frame selector cannot be empty")

    try:
        sec = float(value)
    except ValueError:
        sec = None

    if sec is not None:
        return FrameSelector(raw=raw, kind="absolute", absolute_sec=sec)

    match = _SELECTOR_RE.match(value)
    if match is None:
        raise FrameSelectorError(
            "invalid frame selector; use one of start|mid|end, anchor offsets like start+2.0/end-1.0, or absolute seconds"
        )

    anchor = match.group(1)
    offset_text = match.group(2)
    offset = float(offset_text) if offset_text else 0.0
    return FrameSelector(raw=raw, kind="anchor", anchor=anchor, offset_sec=offset)


def resolve_frame_selector(
    selector: FrameSelector,
    *,
    duration_sec: float,
    trim_start_sec: float | None,
    trim_end_sec: float | None,
) -> tuple[float, list[str]]:
    warnings: list[str] = []
    start = trim_start_sec if trim_start_sec is not None else 0.0
    end_default = duration_sec if duration_sec > 0 else start
    end = trim_end_sec if trim_end_sec is not None else end_default

    if end < start:
        warnings.append("trim_end_sec was before trim_start_sec; using trim_start_sec as end")
        end = start

    if selector.kind == "absolute":
        if selector.absolute_sec is None:
            raise FrameSelectorError("absolute selector is missing an absolute second value")
        resolved = selector.absolute_sec
    else:
        if selector.anchor is None:
            raise FrameSelectorError("anchor selector is missing anchor metadata")
        if selector.anchor == "start":
            base = start
        elif selector.anchor == "mid":
            base = (start + end) / 2.0
        else:
            base = end
        resolved = base + selector.offset_sec

    clamped = resolved
    if clamped < 0:
        clamped = 0.0
    if duration_sec > 0 and clamped > duration_sec:
        clamped = duration_sec
    if clamped != resolved:
        warnings.append(
            f"selector '{selector.raw}' resolved to {resolved:.3f}s and was clamped to {clamped:.3f}s"
        )

    return clamped, warnings
