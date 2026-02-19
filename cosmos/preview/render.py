from __future__ import annotations

import math
from collections.abc import Sequence
from functools import lru_cache
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from cosmos.preview.contracts import PreviewRect, ViewPreview

PALETTE: list[tuple[int, int, int]] = [
    (58, 125, 255),
    (26, 188, 156),
    (255, 166, 0),
    (239, 71, 111),
    (17, 138, 178),
    (7, 59, 76),
    (255, 209, 102),
    (6, 214, 160),
    (131, 56, 236),
    (255, 0, 110),
]


@lru_cache(maxsize=1)
def _font() -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    # Prefer a readable monospace TrueType font for diagnostics and fall back safely.
    for candidate in ("DejaVuSansMono.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, 14)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_grid(draw: ImageDraw.ImageDraw, *, width: int, height: int, step_px: int) -> None:
    if step_px <= 0:
        return
    for x in range(0, width, step_px):
        draw.line([(x, 0), (x, height)], fill=(255, 255, 255, 64), width=1)
    for y in range(0, height, step_px):
        draw.line([(0, y), (width, y)], fill=(255, 255, 255, 64), width=1)


def _draw_rulers(
    draw: ImageDraw.ImageDraw,
    *,
    width: int,
    height: int,
    step_px: int,
) -> None:
    if step_px <= 0:
        step_px = 200
    font = _font()

    for x in range(0, width, step_px):
        draw.line([(x, 0), (x, 14)], fill=(255, 255, 255, 180), width=2)
        draw.text((x + 2, 2), str(x), font=font, fill=(255, 255, 255, 220))

    for y in range(0, height, step_px):
        draw.line([(0, y), (14, y)], fill=(255, 255, 255, 180), width=2)
        draw.text((2, y + 2), str(y), font=font, fill=(255, 255, 255, 220))


def _scale_rect(
    rect: PreviewRect, *, source_w: int, source_h: int, render_w: int, render_h: int
) -> tuple[int, int, int, int]:
    sx = render_w / source_w if source_w > 0 else 1.0
    sy = render_h / source_h if source_h > 0 else 1.0
    x = int(round(rect.x_px * sx))
    y = int(round(rect.y_px * sy))
    w = max(1, int(round(rect.w_px * sx)))
    h = max(1, int(round(rect.h_px * sy)))
    return x, y, w, h


def _draw_text_box(draw: ImageDraw.ImageDraw, *, x: int, y: int, text: str) -> None:
    font = _font()
    bbox = draw.multiline_textbbox((x, y), text, font=font, spacing=2)
    pad = 4
    draw.rectangle(
        [(bbox[0] - pad, bbox[1] - pad), (bbox[2] + pad, bbox[3] + pad)],
        fill=(0, 0, 0, 180),
    )
    draw.multiline_text((x, y), text, font=font, fill=(255, 255, 255, 240), spacing=2)


def _rect_bounds(x: int, y: int, w: int, h: int) -> tuple[tuple[int, int], tuple[int, int]]:
    # PIL rectangle coordinates are inclusive on the bottom-right edge.
    x1 = x + max(0, w - 1)
    y1 = y + max(0, h - 1)
    return (x, y), (x1, y1)


def _draw_center_crosshair(
    draw: ImageDraw.ImageDraw,
    *,
    x: int,
    y: int,
    w: int,
    h: int,
    color: tuple[int, int, int],
) -> None:
    cx = x + (w // 2)
    cy = y + (h // 2)
    arm = max(6, min(w, h) // 8)
    draw.line([(cx - arm, cy), (cx + arm, cy)], fill=(color[0], color[1], color[2], 255), width=2)
    draw.line([(cx, cy - arm), (cx, cy + arm)], fill=(color[0], color[1], color[2], 255), width=2)


def _diagnostic_lines(
    view: ViewPreview, *, time_sec: float, selector: str, source_w: int, source_h: int
) -> str:
    lines = [
        f"view: {view.view_id}",
        f"selector: {selector} @ {time_sec:.3f}s",
        f"crop(px): x={view.crop_px.x_px} y={view.crop_px.y_px} w={view.crop_px.w_px} h={view.crop_px.h_px}",
        (
            "crop(norm): "
            f"x={view.crop_px.x_norm:.4f} y={view.crop_px.y_norm:.4f} "
            f"w={view.crop_px.w_norm:.4f} h={view.crop_px.h_norm:.4f}"
        ),
        f"source: {source_w}x{source_h}",
    ]
    if view.trim_start_sec is not None or view.trim_end_sec is not None:
        lines.append(f"trim: start={view.trim_start_sec} end={view.trim_end_sec}")
    if view.warnings:
        lines.append("warnings: " + "; ".join(view.warnings))
    return "\n".join(lines)


def render_view_cell(
    *,
    frame_path: Path,
    view: ViewPreview,
    selector: str,
    time_sec: float,
    source_w: int,
    source_h: int,
    output_path: Path,
    grid_step_px: int,
    show_rulers: bool,
    show_crosshair: bool,
    alpha: float,
    color: tuple[int, int, int],
) -> None:
    base = Image.open(frame_path).convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")

    _draw_grid(draw, width=base.width, height=base.height, step_px=grid_step_px)
    if show_rulers:
        _draw_rulers(draw, width=base.width, height=base.height, step_px=grid_step_px)

    x, y, w, h = _scale_rect(
        view.crop_px,
        source_w=source_w,
        source_h=source_h,
        render_w=base.width,
        render_h=base.height,
    )

    fill_alpha = int(max(0.0, min(alpha, 1.0)) * 255)
    draw.rectangle(
        _rect_bounds(x, y, w, h),
        fill=(color[0], color[1], color[2], fill_alpha),
        outline=(color[0], color[1], color[2], 255),
        width=4,
    )
    if show_crosshair:
        _draw_center_crosshair(draw, x=x, y=y, w=w, h=h, color=color)

    draw.text((x + 6, max(4, y + 6)), view.view_id, font=_font(), fill=(255, 255, 255, 240))
    diagnostics = _diagnostic_lines(
        view,
        time_sec=time_sec,
        selector=selector,
        source_w=source_w,
        source_h=source_h,
    )
    _draw_text_box(draw, x=12, y=12, text=diagnostics)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(output_path)


def compose_contact_sheet(
    *,
    cell_paths: Sequence[Path],
    output_path: Path,
) -> None:
    if not cell_paths:
        return

    cells = [Image.open(path).convert("RGB") for path in cell_paths]
    try:
        cols = max(1, min(3, int(math.ceil(math.sqrt(len(cells))))))
        rows = int(math.ceil(len(cells) / cols))
        cell_w, cell_h = cells[0].size

        sheet = Image.new("RGB", (cell_w * cols, cell_h * rows), color=(10, 12, 16))
        for idx, cell in enumerate(cells):
            row = idx // cols
            col = idx % cols
            sheet.paste(cell, (col * cell_w, row * cell_h))

        output_path.parent.mkdir(parents=True, exist_ok=True)
        sheet.save(output_path)
    finally:
        for cell in cells:
            cell.close()


def render_stacked_overlay(
    *,
    frame_path: Path,
    views: Sequence[ViewPreview],
    time_sec: float,
    source_w: int,
    source_h: int,
    output_path: Path,
    grid_step_px: int,
    show_rulers: bool,
) -> None:
    base = Image.open(frame_path).convert("RGBA")
    draw = ImageDraw.Draw(base, "RGBA")

    _draw_grid(draw, width=base.width, height=base.height, step_px=grid_step_px)
    if show_rulers:
        _draw_rulers(draw, width=base.width, height=base.height, step_px=grid_step_px)

    legend_lines = [f"frame={time_sec:.3f}s", f"source={source_w}x{source_h}"]
    for idx, view in enumerate(views, start=1):
        color = PALETTE[(idx - 1) % len(PALETTE)]
        x, y, w, h = _scale_rect(
            view.crop_px,
            source_w=source_w,
            source_h=source_h,
            render_w=base.width,
            render_h=base.height,
        )
        draw.rectangle(
            _rect_bounds(x, y, w, h),
            outline=(color[0], color[1], color[2], 255),
            width=4,
        )

        label = str(idx)
        badge_top = max(0, y - 16)
        badge_bottom = min(base.height - 1, badge_top + 20)
        draw.rectangle(
            [(x, badge_top), (x + 20, badge_bottom)],
            fill=(color[0], color[1], color[2], 220),
        )
        draw.text((x + 5, badge_top + 2), label, font=_font(), fill=(255, 255, 255, 240))
        legend_lines.append(f"{idx}: {view.view_id}")

    _draw_text_box(draw, x=12, y=12, text="\n".join(legend_lines))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    base.convert("RGB").save(output_path)
