"""Convert the workbench's own slide graphics to editable PowerPoint shapes."""

import re
from xml.etree import ElementTree

from pptx import Presentation
from pptx.dml.color import RGBColor
from pptx.enum.shapes import MSO_CONNECTOR, MSO_SHAPE
from pptx.enum.text import MSO_ANCHOR, MSO_AUTO_SIZE, PP_ALIGN
from pptx.oxml.xmlchemy import OxmlElement
from pptx.util import Emu, Pt

SLIDE_WIDTH = 1280
SLIDE_HEIGHT = 720


def px(value):
    return Emu(round(float(value) * 9525))


def _remove_theme_shadow(shape):
    effect = shape._element.find(".//" + "{http://schemas.openxmlformats.org/drawingml/2006/main}effectRef")
    if effect is not None:
        effect.set("idx", "0")


def _style(shape, attributes):
    _remove_theme_shadow(shape)
    fill = attributes.get("fill", "")
    if fill.startswith("#"):
        shape.fill.solid()
        shape.fill.fore_color.rgb = RGBColor.from_string(fill[1:])
    else:
        shape.fill.background()
    stroke = attributes.get("stroke", "")
    if stroke.startswith("#"):
        shape.line.color.rgb = RGBColor.from_string(stroke[1:])
        shape.line.width = px(attributes.get("stroke-width", 1))
    else:
        shape.line.fill.background()


def _font(run, size, color, bold=False):
    run.font.name = "Microsoft YaHei"
    east_asian = OxmlElement("a:ea")
    east_asian.set("typeface", "Microsoft YaHei")
    run._r.get_or_add_rPr().insert_element_before(east_asian, "a:cs", "a:sym", "a:extLst")
    run.font.size = Pt(size * .75)
    run.font.bold = bold
    run.font.color.rgb = RGBColor.from_string(color[1:])


def _text(shapes, node):
    attributes = node.attrib
    size = float(attributes["font-size"])
    x, baseline = float(attributes["x"]), float(attributes["y"])
    anchor = attributes.get("text-anchor", "start")
    width = float(attributes.get("data-width", SLIDE_WIDTH - x))
    lines = [(node.text, baseline)]
    for part in node:
        baseline += float(part.get("dy", size))
        lines.append((part.text, baseline))
    for text, y in lines:
        if not text:
            continue
        if anchor == "middle":
            left, alignment = x - width / 2, PP_ALIGN.CENTER
        elif anchor == "end":
            left, alignment = x - width, PP_ALIGN.RIGHT
        else:
            left, alignment = x, PP_ALIGN.LEFT
        frame = shapes.add_textbox(px(left), px(y - size), px(width), px(size * 1.35)).text_frame
        frame.margin_left = frame.margin_right = frame.margin_top = frame.margin_bottom = 0
        frame.word_wrap = False
        frame.auto_size = MSO_AUTO_SIZE.NONE
        paragraph = frame.paragraphs[0]
        paragraph.alignment = alignment
        run = paragraph.add_run()
        run.text = text
        _font(run, size, attributes["fill"], attributes.get("font-weight") == "bold")


def _table(shapes, node):
    a = node.attrib
    geometry = [px(a[key]) for key in ("x", "y", "width", "height")]
    columns = list(node)
    table = shapes.add_table(4, len(columns), *geometry).table
    table.first_row = table.horz_banding = False
    for row_index, row in enumerate(table.rows):
        for col_index, column in enumerate(columns):
            cell = table.cell(row_index, col_index)
            cell.fill.solid()
            cell.fill.fore_color.rgb = RGBColor.from_string(a["header-fill" if row_index == 0 else "body-fill"][1:])
            cell.margin_left = cell.margin_right = px(12)
            cell.margin_top = cell.margin_bottom = px(6)
            cell.vertical_anchor = MSO_ANCHOR.MIDDLE
            cell.text_frame.word_wrap = True
            tcpr = cell._tc.get_or_add_tcPr()
            for edge in ("lnL", "lnR", "lnT", "lnB"):
                border = OxmlElement(f"a:{edge}")
                border.set("w", str(px(1)))
                solid = OxmlElement("a:solidFill")
                color = OxmlElement("a:srgbClr")
                color.set("val", a["rule"][1:])
                solid.append(color)
                border.append(solid)
                tcpr.insert_element_before(border, "a:solidFill")
            if row_index <= 1:
                value = column.get("label" if row_index == 0 else "detail", "")
                if value:
                    run = cell.text_frame.paragraphs[0].add_run()
                    run.text = value
                    _font(run, 23 if row_index == 0 else 19, a["ink"], bold=row_index == 0)


def _path_points(path):
    points = []
    for command, coords in re.findall(r"([MLQZ])([^MLQZ]*)", path):
        values = [int(value) for value in re.findall(r"-?\d+", coords)]
        if command in {"M", "L"}:
            points.append(tuple(values))
        elif command == "Q":
            x, y = points[-1]
            cx, cy, end_x, end_y = values
            for step in range(1, 13):
                t = step / 12
                u = 1 - t
                points.append((round(u*u*x + 2*u*t*cx + t*t*end_x),
                               round(u*u*y + 2*u*t*cy + t*t*end_y)))
    return points


def _add_graphics(shapes, node):
    for child in node:
        tag = child.tag.rsplit("}", 1)[-1]
        a = child.attrib
        if tag == "g":
            _add_graphics(shapes, child)
            continue
        if tag == "text":
            _text(shapes, child)
            continue
        if tag == "table":
            _table(shapes, child)
            continue
        if tag == "rect":
            kind = MSO_SHAPE.ROUNDED_RECTANGLE if a.get("rx") else MSO_SHAPE.RECTANGLE
            shape = shapes.add_shape(kind, *(px(a[key]) for key in ("x", "y", "width", "height")))
            if a.get("rx"):
                shape.adjustments[0] = min(0.5, float(a["rx"]) / min(float(a["width"]), float(a["height"])))
        elif tag in {"circle", "ellipse"}:
            x, y = float(a["cx"]), float(a["cy"])
            rx, ry = (float(a.get(key, a.get("r"))) for key in ("rx", "ry"))
            shape = shapes.add_shape(MSO_SHAPE.OVAL, px(x - rx), px(y - ry), px(2 * rx), px(2 * ry))
        elif tag == "line":
            shape = shapes.add_connector(MSO_CONNECTOR.STRAIGHT, *(px(a[key]) for key in ("x1", "y1", "x2", "y2")))
            _remove_theme_shadow(shape)
            shape.line.color.rgb = RGBColor.from_string(a["stroke"][1:])
            shape.line.width = px(a.get("stroke-width", 1))
            continue
        elif tag in {"polygon", "path"}:
            points = (
                [tuple(map(int, pair.split(","))) for pair in a["points"].split()]
                if tag == "polygon" else _path_points(a["d"])
            )
            builder = shapes.build_freeform(*points[0], scale=9525)
            builder.add_line_segments(points[1:], close=True)
            shape = builder.convert_to_shape()
        else:
            raise ValueError(f"Unsupported slide graphic: {tag}")
        _style(shape, a)


def export_presentation(graphics):
    presentation = Presentation()
    presentation.slide_width = px(SLIDE_WIDTH)
    presentation.slide_height = px(SLIDE_HEIGHT)
    for svg, notes in graphics:
        slide = presentation.slides.add_slide(presentation.slide_layouts[6])
        _add_graphics(slide.shapes, ElementTree.fromstring(svg))
        if notes:
            slide.notes_slide.notes_text_frame.text = notes
    return presentation
