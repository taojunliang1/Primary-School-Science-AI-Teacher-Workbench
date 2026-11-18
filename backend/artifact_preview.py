"""Render browser previews of generated PowerPoint slides without Office."""

import base64
import io
from html import escape
from pathlib import Path
from zipfile import BadZipFile

from PIL import Image
from pptx import Presentation
from pptx.enum.dml import MSO_COLOR_TYPE, MSO_FILL
from pptx.enum.shapes import MSO_AUTO_SHAPE_TYPE, MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN
from pptx.exc import PackageNotFoundError
from pptx.oxml.ns import qn

from .skill_runtime.slide_design import _wrap

EMU_PER_PIXEL = 9525


def _color(color, default):
    return f"#{color.rgb}" if color.type == MSO_COLOR_TYPE.RGB else default


def _fill(fill, default="none"):
    return _color(fill.fore_color, default) if fill.type == MSO_FILL.SOLID else default


def _picture(shape, x, y, width, height):
    try:
        with Image.open(io.BytesIO(shape.image.blob)) as source:
            if source.width * source.height > 18_000_000:
                return ""
            crop = source.crop((
                round(source.width * max(0, shape.crop_left)),
                round(source.height * max(0, shape.crop_top)),
                round(source.width * (1 - max(0, shape.crop_right))),
                round(source.height * (1 - max(0, shape.crop_bottom))),
            ))
            crop.thumbnail((1280, 900))
            if not crop.width or not crop.height:
                return ""
            data = io.BytesIO()
            crop.convert("RGB").save(data, format="JPEG", quality=86)
    except (OSError, ValueError, Image.DecompressionBombError):
        return ""
    encoded = base64.b64encode(data.getvalue()).decode("ascii")
    return (
        f'<image x="{x}" y="{y}" width="{width}" height="{height}" '
        f'preserveAspectRatio="none" href="data:image/jpeg;base64,{encoded}"/>'
    )


def _text(shape, x, y, width):
    frame = shape.text_frame
    parts = []
    baseline = y + frame.margin_top / EMU_PER_PIXEL
    for paragraph in frame.paragraphs:
        if not paragraph.text:
            continue
        size = max((run.font.size.pt * 4 / 3 for run in paragraph.runs if run.font.size), default=20)
        baseline += size
        if paragraph.alignment == PP_ALIGN.CENTER:
            left, anchor = x + width / 2, "middle"
        elif paragraph.alignment == PP_ALIGN.RIGHT:
            left, anchor = x + width - frame.margin_right / EMU_PER_PIXEL, "end"
        else:
            left, anchor = x + frame.margin_left / EMU_PER_PIXEL, "start"
        runs = []
        for run in paragraph.runs:
            color = _color(run.font.color, "#20343A")
            weight = "bold" if run.font.bold else "normal"
            runs.append(f'<tspan fill="{color}" font-weight="{weight}">{escape(run.text)}</tspan>')
        parts.append(
            f'<text x="{left}" y="{baseline}" text-anchor="{anchor}" '
            f'font-size="{size}" xml:space="preserve">{"".join(runs)}</text>'
        )
        baseline += size * .34
    return "".join(parts)


def _table(shape, x, y):
    table = shape.table
    graphics = []
    for row_index, row in enumerate(table.rows):
        left = x
        height = row.height / EMU_PER_PIXEL
        for column_index, column in enumerate(table.columns):
            cell = table.cell(row_index, column_index)
            width = column.width / EMU_PER_PIXEL
            fill = _fill(cell.fill, "#FFFFFF")
            border = cell._tc.find("/".join(map(qn, ("a:tcPr", "a:lnL", "a:solidFill", "a:srgbClr"))))
            stroke = "#" + border.get("val") if border is not None else "#B9C5C2"
            graphics.append(f'<rect x="{left}" y="{y}" width="{width}" height="{height}" fill="{fill}" stroke="{stroke}"/>')
            for paragraph in cell.text_frame.paragraphs:
                if not paragraph.text or not paragraph.runs:
                    continue
                run = paragraph.runs[0]
                size = run.font.size.pt * 4 / 3 if run.font.size else 20
                wrapped = _wrap(paragraph.text, size, width - 24)
                baseline = y + (height - len(wrapped) * size * 1.26) / 2 + size
                for line in wrapped:
                    color = _color(run.font.color, "#20343A")
                    bold = "bold" if run.font.bold else "normal"
                    graphics.append(f'<text x="{left + 12}" y="{baseline}" font-size="{size}" fill="{color}" '
                                    f'font-weight="{bold}">{escape(line)}</text>')
                    baseline += size * 1.26
            left += width
        y += height
    return "".join(graphics)


def _shape(shape):
    x, y, width, height = (float(getattr(shape, name)) / EMU_PER_PIXEL
                            for name in ("left", "top", "width", "height"))
    if shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
        return _picture(shape, x, y, width, height)
    if shape.has_table:
        return _table(shape, x, y)
    if shape.shape_type == MSO_SHAPE_TYPE.LINE:
        color = _color(shape.line.color, "#285799")
        weight = max(1, shape.line.width / EMU_PER_PIXEL)
        transform = shape._element.spPr.xfrm
        flip_h = transform is not None and transform.get("flipH") in {"1", "true"}
        flip_v = transform is not None and transform.get("flipV") in {"1", "true"}
        y1, y2 = (y + height, y) if flip_h != flip_v else (y, y + height)
        return f'<line x1="{x}" y1="{y1}" x2="{x + width}" y2="{y2}" stroke="{color}" stroke-width="{weight}"/>'
    graphics = ""
    if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE:
        fill = _fill(shape.fill)
        stroke = _fill(shape.line.fill)
        weight = shape.line.width / EMU_PER_PIXEL
        style = f'fill="{fill}" stroke="{stroke}" stroke-width="{weight}"'
        if shape.auto_shape_type == MSO_AUTO_SHAPE_TYPE.OVAL:
            graphics = f'<ellipse cx="{x + width/2}" cy="{y + height/2}" rx="{width/2}" ry="{height/2}" {style}/>'
        else:
            radius = min(14, height / 3, width / 3) if shape.auto_shape_type == MSO_AUTO_SHAPE_TYPE.ROUNDED_RECTANGLE else 0
            graphics = f'<rect x="{x}" y="{y}" width="{width}" height="{height}" rx="{radius}" {style}/>'
    return graphics + (_text(shape, x, y, width) if shape.has_text_frame else "")


def preview_slide(path: Path, index: int) -> tuple[str, int]:
    try:
        presentation = Presentation(path)
    except (PackageNotFoundError, BadZipFile, KeyError, OSError, ValueError) as exc:
        raise ValueError("invalid presentation") from exc
    count = len(presentation.slides)
    if not 1 <= index <= count:
        raise IndexError(index)
    width = presentation.slide_width / EMU_PER_PIXEL
    height = presentation.slide_height / EMU_PER_PIXEL
    slide = presentation.slides[index - 1]
    background = _fill(slide.background.fill, "#FFFFFF")
    graphics = "".join(_shape(shape) for shape in slide.shapes)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width} {height}" '
        f'font-family="Microsoft YaHei, Noto Sans CJK SC, sans-serif">'
        f'<rect width="100%" height="100%" fill="{background}"/>{graphics}</svg>',
        count,
    )
