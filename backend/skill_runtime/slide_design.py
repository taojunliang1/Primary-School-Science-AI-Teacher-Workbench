"""Slide compositions for the workbench's editable PowerPoint renderer."""

import re
from html import escape
from unicodedata import east_asian_width

from .teaching_diagram import render_teaching_diagram

CONTENT_LAYOUTS = {"figure", "compare", "process", "inquiry", "concepts", "diagram", "focus", "record"}
IMAGE_PANELS = {
    "cover": (726, 108, 490, 448),
    "figure": (64, 197, 696, 352),
    "content": (735, 197, 481, 348),
}
LABELS = {
    "section": "进入探究", "content": "课堂学习", "figure": "观察与解释",
    "compare": "对照比较", "process": "梳理过程", "inquiry": "动手探究",
    "concepts": "概念梳理", "quote": "交流与思考", "diagram": "观察与解释",
    "focus": "读出证据", "record": "观察记录",
}
LEFT = 64
RIGHT = 1216
CONTENT_WIDTH = RIGHT - LEFT


def image_panel(layout):
    return IMAGE_PANELS[layout]


def _rect(x, y, w, h, color, radius=0):
    corner = f' rx="{radius}"' if radius else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}"{corner} fill="{color}"/>'


def _circle(x, y, r, color, stroke="none"):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="{color}" stroke="{stroke}" stroke-width="2"/>'


def _line(x1, y1, x2, y2, color, width=2):
    return f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{color}" stroke-width="{width}"/>'


def _width(char, size):
    if char.isspace():
        return size * .36
    if east_asian_width(char) in {"W", "F", "A"}:
        return size
    return size * (.69 if char.isupper() else .59)


def _wrap(text, size, width):
    lines = []
    current = ""
    used = 0.0
    for char in text.strip():
        char_width = _width(char, size)
        if current and used + char_width > width:
            # Keep short English words together when there is a word boundary.
            split = current.rfind(" ") if char.isascii() and char.isalnum() else -1
            if split > len(current) // 2:
                lines.append(current[:split])
                current = current[split + 1:]
            elif char in "，。；：、！？）》】" and len(current) > 1:
                lines.append(current[:-1].rstrip())
                current = current[-1]
            else:
                lines.append(current.rstrip())
                current = ""
            used = sum(_width(letter, size) for letter in current)
        if current or not char.isspace():
            current += char
            used += char_width
    if current:
        lines.append(current.rstrip())
    return lines


def _fit(value, width, height, size, minimum):
    for selected in range(size, minimum - 1, -1):
        lines = _wrap(value, selected, width - 8)
        leading = round(selected * 1.34)
        if len(lines) * leading <= height:
            return selected, lines, leading
    raise ValueError("文字超过版面可容纳范围")


def _text(value, x, top, width, height, size, color, *, bold=False, minimum=16, align="start"):
    if not value:
        return ""
    selected, lines, leading = _fit(value, width, height, size, minimum)
    anchor_x = {"start": x, "middle": x + width / 2, "end": x + width}[align]
    return "".join(
        f'<text x="{anchor_x}" y="{top + selected + index * leading}" '
        f'font-size="{selected}" fill="{color}" font-weight="{"bold" if bold else "normal"}" '
        f'text-anchor="{align}" data-width="{width}">{escape(line)}</text>'
        for index, line in enumerate(lines)
    )


def _cover(slide, deck, theme):
    diagram = None
    if deck.theme == "field" and not slide.image_asset_id:
        diagram = next((page.diagram for page in deck.slides if page.diagram), None)
    body = _rect(0, 0, 1280, 720, theme["bg"])
    body += _rect(0, 0, 1280, 14, theme["primary"])
    body += _text(deck.audience, LEFT, 72, 624, 60, 24, theme["secondary"], bold=True)
    body += _line(LEFT, 147, 688 if slide.image_asset_id else RIGHT, 147, theme["primary"], 2)
    if slide.image_asset_id:
        body += _rect(*image_panel("cover"), theme["surface"], 8)
    elif diagram:
        body += _rect(698, 205, 518, 320, theme["soft"], 8)
        body += render_teaching_diagram(
            diagram, theme, _text, _line, _rect, frame=(715, 236, 484, 255), show_labels=False,
        )
    width = 602 if slide.image_asset_id or diagram else 1140
    title_y = 207 if slide.image_asset_id or diagram else 241
    _, title_lines, leading = _fit(slide.title, width, 202, 76, 34)
    divider_y = title_y + len(title_lines) * leading + 18
    body += _text(slide.title, LEFT, title_y, width, 202, 76, theme["primary"], bold=True, minimum=34)
    body += _rect(LEFT, divider_y, 55, 5, theme["accent"])
    body += _text(
        slide.subtitle or deck.subtitle, LEFT, divider_y + 27, width, 622 - divider_y - 27,
        32, theme["ink"], minimum=19,
    )
    return body


def _header(slide, theme):
    return (
        _text(LABELS[slide.layout], LEFT, 46, 450, 30, 18, theme["secondary"], bold=True)
        + _text(slide.title, LEFT, 89, CONTENT_WIDTH, 86, 44, theme["primary"], bold=True, minimum=24)
        + _line(LEFT, 180, RIGHT, 180, theme["soft"])
    )


def _footer(slide, page, total, theme):
    bar = _line(LEFT, 660, RIGHT, 660, theme["soft"])
    bar += _text(f"{page:02d} / {total:02d}", 1102, 673, 114, 24, 15, theme["muted"], align="end", minimum=15)
    if slide.takeaway and slide.layout not in {"cover", "end"}:
        bar += _rect(LEFT, 600, CONTENT_WIDTH, 47, theme["tint"], 5)
        bar += _rect(LEFT, 600, 5, 47, theme["accent"])
        bar += _text(slide.takeaway, 86, 601, 1105, 45, 22, theme["primary"], bold=True, minimum=16)
    return bar


def _point_values(slide):
    values = slide.bullets or [item.detail or item.label for item in slide.items] or [slide.subtitle]
    points = [re.sub(r"^\s*(?:[①-⑳•▪]|\d{1,2}[、)]|\d{1,2}[.．](?!\d))\s*", "", value)
              for value in values if value]
    return [value for value in points if value]


def _points(values, x, y, width, height, theme, *, numbered=True, start=1, preferred=30):
    if not values:
        return ""
    text_inset = 42 if numbered else 23
    text_width = width - text_inset
    for size in range(preferred, 17, -1):
        leading = round(size * 1.34)
        lines = [len(_wrap(value, size, text_width - 8)) for value in values]
        used = sum(lines) * leading
        if used + (len(values) - 1) * 9 <= height:
            break
    else:
        raise ValueError("投影要点超过版面可容纳范围")
    gap = min((height - used) // max(1, len(values) - 1), 24)
    y += min(18, (height - used - gap * (len(values) - 1)) // 2)
    body = ""
    for index, (value, count) in enumerate(zip(values, lines), start):
        if numbered:
            body += _rect(x, y + 3, 30, 28, theme["soft"], 6)
            body += _text(str(index), x, y + 5, 30, 24, 16, theme["primary"], bold=True, align="middle")
        else:
            body += _circle(x + 5, y + (size + 7) / 2, 4, theme["accent"])
        body += _text(value, x + text_inset, y, text_width, count * leading, size, theme["ink"], minimum=size)
        y += count * leading + gap
    return body


def _content(slide, theme):
    values = _point_values(slide)
    if slide.image_asset_id:
        return (
            _points(values, LEFT, 205, 624, 355, theme, preferred=27)
            + _rect(*image_panel("content"), theme["surface"], 8)
        )
    if len(values) <= 4:
        return _points(values, LEFT, 218, 1094, 352, theme, numbered=False, preferred=35)
    midpoint = (len(values) + 1) // 2
    return (
        _line(640, 218, 640, 562, theme["soft"])
        + _points(values[:midpoint], LEFT, 218, 548, 344, theme, preferred=29)
        + _points(values[midpoint:], 676, 218, 540, 344, theme, preferred=29, start=midpoint + 1)
    )


def _figure(slide, theme):
    return (
        _rect(*image_panel("figure"), theme["surface"], 8)
        + _line(780, 210, 780, 554, theme["secondary"])
        + _points(_point_values(slide), 801, 212, 410, 343, theme, numbered=False, preferred=29)
    )


def _diagram(slide, theme):
    if slide.bullets:
        return (
            render_teaching_diagram(slide.diagram, theme, _text, _line, _rect, frame=(68, 213, 720, 368))
            + _line(795, 226, 795, 553, theme["soft"])
            + _points(_point_values(slide), 817, 228, 378, 320, theme, numbered=False, preferred=25)
        )
    return render_teaching_diagram(
        slide.diagram, theme, _text, _line, _rect, frame=(76, 194, 1128, 394),
    )


def _focus(slide, theme):
    return (
        _text(slide.value, 84, 232, 1110, 174, 102, theme["primary"],
              bold=True, minimum=47, align="middle")
        + _line(450, 435, 830, 435, theme["accent"], 3)
        + _text(slide.subtitle, 144, 463, 992, 117, 32, theme["ink"], minimum=20, align="middle")
    )


def _compare(slide, theme):
    body = _line(640, 204, 640, 573, theme["soft"], 2)
    for index, item in enumerate(slide.items):
        x = LEFT + index * 600
        body += _rect(x, 213, 552, 339, theme["surface"], 8)
        body += _rect(x, 213, 552, 92, theme["tint"] if index else theme["soft"], 8)
        body += _text(item.label, x + 26, 228, 501, 67, 35, theme["primary"], bold=True, minimum=22)
        body += _text(item.detail, x + 26, 334, 501, 183, 31, theme["ink"], minimum=21)
    return body


def _process(slide, theme):
    count = len(slide.items)
    width = CONTENT_WIDTH // count
    if any(len(_wrap(item.label, 27, width - 32)) > 2
           or len(_wrap(item.detail, 22, width - 32)) > 4 for item in slide.items):
        return _process_rows(slide, theme)
    body = ""
    track_y = 278
    positions = [LEFT + index * width + width / 2 for index in range(count)]
    for x1, x2 in zip(positions, positions[1:]):
        body += _arrow(x1 + 35, track_y, x2 - 36, theme["muted"])
    for index, item in enumerate(slide.items):
        center = positions[index]
        x = LEFT + index * width + 12
        body += _circle(center, track_y, 32, theme["primary"])
        body += _text(str(index + 1), center - 26, 260, 52, 39, 27, "#FFFFFF", bold=True, align="middle")
        body += _text(item.label, x, 332, width - 24, 82, 34, theme["primary"],
                      bold=True, minimum=25, align="middle")
        body += _text(item.detail, x, 427, width - 24, 122, 26, theme["ink"],
                      minimum=21, align="middle")
    return body


def _arrow(x1, y, x2, color):
    return (
        _line(x1, y, x2, y, color, 2)
        + _line(x2 - 9, y - 6, x2, y, color, 2)
        + _line(x2 - 9, y + 6, x2, y, color, 2)
    )


def _process_rows(slide, theme):
    body = _line(88, 238, 88, 238 + (len(slide.items) - 1) * 92, theme["soft"], 4)
    for index, item in enumerate(slide.items):
        y = 206 + index * 92
        body += _rect(115, y, 1101, 86, theme["surface"], 6)
        body += _circle(88, y + 32, 20, theme["primary"])
        body += _text(str(index + 1), 70, y + 18, 36, 28, 21, "#FFFFFF", bold=True, align="middle")
        body += _text(item.label, 137, y + 9, 288, 76, 27, theme["primary"], bold=True, minimum=19)
        body += _line(443, y + 14, 443, y + 72, theme["soft"])
        body += _text(item.detail, 467, y + 5, 722, 78, 25, theme["ink"], minimum=18)
    return body


def _inquiry(slide, theme):
    row = 367 // len(slide.items)
    body = ""
    for index, item in enumerate(slide.items):
        y = 208 + index * row
        body += _rect(LEFT, y, CONTENT_WIDTH, row - 10, theme["surface"], 5)
        body += _rect(LEFT, y, 5, row - 10, theme["primary"])
        body += _text(f"{index + 1:02d}", 88, y + 18, 49, 33, 22, theme["secondary"], bold=True)
        body += _text(item.label, 145, y + 18, 286, row - 37, 29, theme["primary"], bold=True, minimum=20)
        body += _line(458, y + 14, 458, y + row - 24, theme["soft"])
        body += _text(item.detail, 487, y + 18, 694, row - 36, 26, theme["ink"], minimum=20)
    return body


def _concepts(slide, theme):
    width = (1152 - 24 * (len(slide.items) - 1)) // len(slide.items)
    body = ""
    for index, item in enumerate(slide.items):
        x = 64 + index * (width + 24)
        body += _line(x, 229, x + width, 229, theme["secondary"], 3)
        body += _text(item.label, x + 14, 261, width - 28, 116, 36, theme["primary"], bold=True, minimum=22)
        body += _text(item.detail, x + 14, 389, width - 28, 166, 27, theme["ink"], minimum=20)
    return body


def _record(slide, theme):
    top = 222
    body = ""
    if slide.subtitle:
        body = _text(slide.subtitle, LEFT, 205, CONTENT_WIDTH, 56, 25, theme["ink"], minimum=19)
        top = 273
    cell_width = CONTENT_WIDTH // len(slide.items) - 24
    for item in slide.items:
        if len(_wrap(item.label, 23, cell_width)) > 2:
            raise ValueError("观察记录表的列名超过两行")
        if len(_wrap(item.detail, 19, cell_width)) > 2:
            raise ValueError("观察记录表的填写提示超过两行")
    columns = "".join(
        f'<column label="{escape(item.label, quote=True)}" detail="{escape(item.detail, quote=True)}"/>'
        for item in slide.items
    )
    return body + (
        f'<table x="{LEFT}" y="{top}" width="{CONTENT_WIDTH}" height="{588 - top}"'
        f' header-fill="{theme["soft"]}" body-fill="{theme["surface"]}"'
        f' ink="{theme["ink"]}" rule="{theme["muted"]}">{columns}</table>'
    )


def _reflection(slide, theme):
    quote = slide.bullets[0] if slide.bullets else slide.subtitle
    return (
        _rect(LEFT, 215, CONTENT_WIDTH, 339, theme["soft"], 8)
        + _rect(LEFT, 215, 7, 339, theme["primary"])
        + _text(quote, 115, 250, 1044, 232, 51, theme["primary"], bold=True, minimum=28)
    )


def _section(slide, theme):
    return (
        _rect(0, 0, 1280, 720, theme["bg"])
        + _rect(64, 148, 1152, 411, theme["soft"], 20)
        + _rect(111, 201, 56, 6, theme["accent"], 3)
        + _text(slide.title, 111, 245, 1050, 167, 55, theme["primary"], bold=True, minimum=28)
        + _text(slide.subtitle, 111, 419, 1000, 93, 26, theme["ink"], minimum=17)
    )


def _end(slide, theme):
    supporting = slide.takeaway or slide.subtitle or "你能用今天找到的证据作出解释吗？"
    return (
        _rect(0, 0, 1280, 720, theme["bg"])
        + _rect(0, 0, 1280, 14, theme["primary"])
        + _text("回顾与迁移", LEFT, 116, 610, 48, 23, theme["secondary"], bold=True)
        + _text(slide.title, LEFT, 185, 1140, 139, 60, theme["primary"], bold=True, minimum=32)
        + _line(LEFT, 354, RIGHT, 354, theme["accent"], 3)
        + _text(supporting, LEFT, 399, 1090, 166, 41, theme["ink"], minimum=24)
    )


RENDERERS = {
    "content": _content, "figure": _figure, "compare": _compare,
    "process": _process, "inquiry": _inquiry, "concepts": _concepts,
    "quote": _reflection, "diagram": _diagram, "focus": _focus, "record": _record,
}


def render_slide(slide, page, total, deck, theme):
    if slide.layout == "cover":
        body = _cover(slide, deck, theme)
    elif slide.layout == "section":
        body = _section(slide, theme)
    elif slide.layout == "end":
        body = _end(slide, theme)
    else:
        body = _rect(0, 0, 1280, 720, theme["bg"])
        body += _header(slide, theme) + RENDERERS[slide.layout](slide, theme)
    body += _footer(slide, page, total, theme)
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 720" font-family="Microsoft YaHei">{body}</svg>'
