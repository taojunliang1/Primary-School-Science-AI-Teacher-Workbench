"""Editable, sourced science diagrams for common classroom investigations."""

from math import sqrt

from .teaching_diagram import TeachingDiagram


def oval(x, y, w, h, fill="soft", stroke="primary"):
    return {"kind": "ellipse", "box": [x, y, w, h], "fill": fill, "stroke": stroke}


def box(x, y, w, h, fill="soft", stroke="none"):
    return {"kind": "rect", "box": [x, y, w, h], "fill": fill, "stroke": stroke}


def line(*points, color="primary", weight=3):
    return {"kind": "line", "points": points, "color": color, "weight": weight}


def label(text, x, y, width=170, target=None):
    return {"text": text, "x": x, "y": y, "width": width, "target": target}


def silkworm_body():
    body = [oval(180, 316, 668, 290), oval(106, 353, 109, 220, "surface")]
    for x in (231, 277, 323, 369, 415, 461, 507, 553, 599, 645, 691, 737):
        reach = round(144 * sqrt(1 - ((x - 514) / 334) ** 2))
        body.append(line((x, 461 - reach), (x + 4, 463), (x, 461 + reach), color="secondary", weight=1))
    for x in (221, 265, 309):
        body.append(line((x, 576), (x - 7, 659), (x + 8, 670), weight=3))
    for x in (437, 483, 529, 575, 787):
        body.append(oval(x, 568, 30, 102, "soft"))
    for x in (226, 366, 412, 458, 504, 550, 596, 642, 688):
        body.append(oval(x, 476, 8, 18, "accent", "none"))
    body += [oval(144, 420, 12, 26, "ink", "none"),
             line((138, 507), (146, 522), (158, 525), weight=2)]
    labels = [
        label("头", 40, 80, 130, (145, 353)),
        label("胸", 210, 80, 135, (267, 336)),
        label("腹", 440, 80, 160, (539, 330)),
        label("气门", 735, 80, 155, (648, 482)),
        label("三对胸足", 126, 780, 190, (265, 660)),
        label("四对腹足", 410, 780, 205, (529, 659)),
        label("尾足", 746, 780, 150, (797, 655)),
    ]
    return body, labels


def silkworm_cycle():
    marks = [oval(x, y, 19, 52, "accent", "none")
             for x, y in [(70, 327), (93, 318), (116, 341), (81, 392), (105, 400)]]
    marks += [oval(298, 350, 122, 105), oval(281, 371, 26, 66, "surface"),
              oval(567, 289, 88, 239, "tint", "accent"), oval(584, 313, 53, 187, "soft", "none"),
              oval(801, 300, 65, 170), oval(875, 300, 65, 170), oval(855, 346, 26, 158, "primary"),
              line((866, 346), (848, 312)), line((870, 346), (892, 312))]
    for x in (315, 336, 357, 378, 399):
        marks.append(line((x, 363), (x, 447), color="secondary", weight=1))
    for start, end in ((165, 267), (436, 536), (669, 777)):
        marks += [line((start, 409), (end, 409), color="accent"),
                  line((end - 13, 384), (end, 409), (end - 13, 434), color="accent")]
    marks += [line((877, 625), (877, 817), (100, 817), (100, 625), color="secondary", weight=2),
              line((90, 650), (100, 625), (110, 650), color="secondary", weight=2)]
    return marks, [label("卵", 40, 139, 120), label("幼虫", 284, 139, 130),
                   label("蛹（茧内）", 536, 139, 152), label("成虫（蚕蛾）", 775, 139, 185),
                   label("产卵，开始下一代", 380, 777, 240)]


def silkworm_egg():
    marks = [oval(224, 270, 542, 465, "soft", "secondary")]
    for x, y in [(343, 370), (428, 342), (511, 399), (584, 348),
                 (314, 503), (402, 483), (493, 521), (560, 482), (633, 514)]:
        marks.append(oval(x, y, 33, 68, "sun", "accent"))
    return marks, [label("蚕卵", 396, 88, 182, (531, 425))]


def silkworm_larva():
    marks, _ = silkworm_body()
    return marks, [label("蚕幼虫", 387, 84, 208, (459, 315)),
                   label("观察体节和足", 387, 787, 208, (519, 570))]


def silkworm_pupa():
    marks = [
        oval(218, 206, 568, 596, "tint", "accent"),
        oval(254, 238, 495, 525, "surface", "secondary"),
        oval(389, 311, 230, 380, "soft"),
        oval(409, 311, 190, 110, "primary"),
    ]
    marks += [line((x, 479), (x, 610), color="muted", weight=1) for x in (447, 482, 517, 552)]
    return marks, [label("茧壳", 75, 40, 175, (339, 273)),
                   label("茧中的蛹", 690, 54, 204, (582, 440))]


def silkworm_moth():
    marks = [
        oval(233, 240, 248, 374, "soft"), oval(514, 240, 248, 374, "soft"),
        oval(276, 388, 208, 269, "surface"), oval(510, 388, 208, 269, "surface"),
        oval(450, 308, 99, 381, "tint"), oval(457, 260, 85, 104, "primary"),
        line((485, 275), (453, 207), (408, 161)), line((513, 275), (547, 207), (593, 161)),
    ]
    return marks, [label("翅", 146, 743, 153, (348, 485)),
                   label("触角", 685, 100, 165, (548, 200))]


def air_cup():
    marks = [box(63, 408, 874, 345), line((63, 408), (937, 408), color="secondary"),
             line((498, 227), (498, 750), color="secondary", weight=1),
             box(175, 262, 152, 389, "surface"),
             line((146, 657), (176, 251), (326, 251), (355, 657)),
             line((149, 654), (353, 654), color="secondary", weight=2),
             box(197, 277, 107, 71, "sun"),
             line((591, 638), (699, 245), (839, 408), (714, 745)),
             line((598, 635), (711, 744), color="secondary", weight=2),
             line((618, 408), (839, 408), color="secondary", weight=2),
             box(740, 412, 55, 52, "sun")]
    for x, y, width in ((580, 571, 13), (553, 502, 18), (586, 464, 11)):
        marks.append(oval(x, y, width, width * 3, "surface", "secondary"))
    return marks, [label("直着压入", 116, 54, 238), label("倾斜杯口", 642, 54, 207),
                   label("空气留在杯内", 125, 812, 225, (250, 464)),
                   label("气泡逸出，水进入", 604, 812, 294, (585, 573))]


def water_cycle():
    marks = [box(442, 688, 493, 152),
             oval(302, 242, 135, 153), oval(378, 187, 119, 202), oval(457, 237, 122, 152),
             line((68, 765), (186, 480), (302, 733), (419, 616), (521, 704), color="muted", weight=4),
             line((758, 665), (814, 489), (774, 333), (620, 319), color="accent"),
             line((633, 298), (620, 319), (633, 346), color="accent"),
             line((365, 418), (340, 623), color="secondary"),
             line((330, 594), (340, 623), (355, 599), color="secondary"),
             line((408, 418), (383, 623), color="secondary"),
             line((373, 594), (383, 623), (398, 599), color="secondary"),
             line((291, 676), (393, 753), (516, 770), color="secondary"),
             line((503, 743), (516, 770), (502, 793), color="secondary")]
    return marks, [label("凝结成云", 348, 40, 214, (435, 255)),
                   label("降水", 64, 291, 170, (350, 485)),
                   label("地表径流", 40, 817, 206, (360, 733)),
                   label("蒸发", 790, 175, 145, (789, 443)),
                   label("地表水", 684, 852, 188, (751, 769))]


_SILKWORM_LIFECYCLE_SOURCE = "https://www.mdpi.com/2227-9717/9/10/1730"
PRESETS = {
    "silkworm-body": (silkworm_body, "https://pmc.ncbi.nlm.nih.gov/articles/PMC5436023/"),
    "silkworm-cycle": (silkworm_cycle, _SILKWORM_LIFECYCLE_SOURCE),
    "silkworm-egg": (silkworm_egg, _SILKWORM_LIFECYCLE_SOURCE),
    "silkworm-larva": (silkworm_larva, _SILKWORM_LIFECYCLE_SOURCE),
    "silkworm-pupa": (silkworm_pupa, _SILKWORM_LIFECYCLE_SOURCE),
    "silkworm-moth": (silkworm_moth, _SILKWORM_LIFECYCLE_SOURCE),
    "air-cup": (air_cup, "https://teachersinstitute.yale.edu/curriculum/units/2016/4/16.04.08/5"),
    "water-cycle": (water_cycle, "https://www.usgs.gov/water-science-school/water-cycle-diagrams"),
}


def build_preset(name: str):
    build, source = PRESETS[name]
    marks, labels = build()
    return TeachingDiagram.model_validate({"marks": marks, "labels": labels}), source
