"""Validate and render editable instructional diagram geometry."""

from math import ceil
from typing import Annotated, Literal
from unicodedata import east_asian_width

from pydantic import BaseModel, Field, StringConstraints, model_validator

Coordinate = Annotated[int, Field(ge=0, le=1000, strict=True)]
Point = tuple[Coordinate, Coordinate]
Color = Literal["primary", "secondary", "accent", "sun", "ink", "muted", "soft", "surface", "tint"]


class DiagramLine(BaseModel):
    kind: Literal["line"]
    points: Annotated[list[Point], Field(min_length=2, max_length=24)]
    color: Color = "primary"
    weight: Annotated[int, Field(ge=1, le=8, strict=True)] = 2


class DiagramShape(BaseModel):
    kind: Literal["ellipse", "rect"]
    box: tuple[Coordinate, Coordinate, Coordinate, Coordinate]
    fill: Color | Literal["none"] = "soft"
    stroke: Color | Literal["none"] = "primary"

    @model_validator(mode="after")
    def check_bounds(self):
        x, y, width, height = self.box
        if not width or not height or x + width > 1000 or y + height > 1000:
            raise ValueError("图形超出画布")
        return self


class DiagramLabel(BaseModel):
    text: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=22)]
    x: Coordinate
    y: Coordinate
    width: Annotated[int, Field(ge=80, le=520, strict=True)] = 170
    target: Point | None = None


class TeachingDiagram(BaseModel):
    marks: Annotated[list[Annotated[DiagramLine | DiagramShape, Field(discriminator="kind")]],
                     Field(min_length=1, max_length=48)]
    labels: Annotated[list[DiagramLabel], Field(min_length=1, max_length=10)]

    @model_validator(mode="after")
    def check_labels(self):
        boxes = []
        for label in self.labels:
            x, y, right, bottom = label.x, label.y, label.x + label.width, label.y + 105
            if right > 1000 or bottom > 1000:
                raise ValueError("说明标签超出画布")
            if any(x < r and right > l and y < b and bottom > t for l, t, r, b in boxes):
                raise ValueError("说明标签互相重叠")
            boxes.append((x, y, right, bottom))
        return self


def fit_labels(raw):
    """Reposition crowded labels while retaining their scientific anchor points."""
    if not isinstance(raw, dict) or not isinstance(raw.get("labels"), list):
        return raw
    if not 1 <= len(raw["labels"]) <= 10:
        return raw
    packed = []
    bounds = []
    for entry in raw["labels"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("text"), str):
            return raw
        x, y, width = entry.get("x"), entry.get("y"), entry.get("width", 170)
        if any(type(value) is not int for value in (x, y, width)):
            return raw
        text = entry["text"].strip()
        if not 1 <= len(text) <= 22:
            return raw
        units = sum(17 if east_asian_width(char) in {"W", "F", "A"} else 12 for char in text)
        width = min(520, max(width, 80, ceil((units + 16) / 1.08)))
        x = min(max(x, 0), 1000 - width)
        y = min(max(y, 0), 895)
        positions = sorted(
            ((left, top) for left in sorted({x, 1000 - width, *range(0, 1001 - width, 25)})
             for top in sorted({y, 895, *range(0, 896, 35)})),
            key=lambda pos: abs(pos[0] - x) + abs(pos[1] - y) * 2,
        )
        for left, top in positions:
            right, bottom = left + width, top + 105
            if not any(left < r and right > l and top < b and bottom > t for l, t, r, b in bounds):
                bounds.append((left, top, right, bottom))
                packed.append({**entry, "x": left, "y": top, "width": width})
                break
        else:
            return raw
    return {**raw, "labels": packed}


def render_teaching_diagram(diagram, theme, text, line, rect, *,
                            frame=(88, 184, 1104, 380), show_labels=True):
    left, top, width, height = frame

    def point(x, y):
        return round(left + width * x / 1000), round(top + height * y / 1000)

    parts = []
    for mark in diagram.marks:
        if isinstance(mark, DiagramLine):
            for start, end in zip(mark.points, mark.points[1:]):
                if start != end:
                    parts.append(line(*point(*start), *point(*end), theme[mark.color], mark.weight))
            continue
        x, y, w, h = mark.box
        px, py = point(x, y)
        right, bottom = point(x + w, y + h)
        fill = theme.get(mark.fill, "none")
        stroke = theme.get(mark.stroke, "none")
        if mark.kind == "ellipse":
            tag = f'<ellipse cx="{(px + right) / 2}" cy="{(py + bottom) / 2}" rx="{(right-px)/2}" ry="{(bottom-py)/2}"'
        else:
            tag = f'<rect x="{px}" y="{py}" width="{right-px}" height="{bottom-py}" rx="8"'
        parts.append(f'{tag} fill="{fill}" stroke="{stroke}" stroke-width="2"/>')

    if not show_labels:
        return "".join(parts)

    for label in diagram.labels:
        x, y = point(label.x, label.y)
        box_width = round(width * label.width / 1000)
        if label.target:
            target_x, target_y = point(*label.target)
            parts.append(line(x + box_width // 2, y + (38 if target_y > y else 0),
                              target_x, target_y, theme["muted"], 1.5))
        parts.append(rect(x, y, box_width, 38, theme["bg"], 3))
        parts.append(text(label.text, x, y + 1, box_width, 38, 23, theme["primary"],
                          bold=True, minimum=17, align="middle"))
    return "".join(parts)
