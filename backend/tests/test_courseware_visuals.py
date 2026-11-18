from pptx import Presentation

from backend.artifact_preview import preview_slide
from backend.courseware import _prefer_lesson_diagrams, _visual_targets
from backend.skill_runtime.diagram_presets import PRESETS
from backend.skill_runtime.ppt_master import PptMasterService, build_svg, parse_deck_spec
from backend.skill_runtime.teaching_diagram import TeachingDiagram, fit_labels


def test_science_presets_include_native_geometry_and_source():
    for preset, (_, source) in PRESETS.items():
        deck = parse_deck_spec({"title": "图解", "slides": [
            {"layout": "diagram", "title": "课堂证据", "visualPreset": preset, "note": "请学生观察。"},
        ]}, expected_pages=1)
        svg = build_svg(deck.slides[0], 1, 1, deck)
        assert "<ellipse" in svg and "<line" in svg
        assert source in deck.slides[0].note
        assert "marks" in deck.editable_source()["slides"][0]["diagram"]


def test_packing_keeps_diagram_targets_and_marks():
    raw = {
        "marks": [{"kind": "ellipse", "box": [200, 250, 400, 400]}],
        "labels": [
            {"text": "昆虫胸部的足", "x": 950, "y": 980, "width": 90, "target": [450, 500]},
            {"text": "腹部观察要点", "x": 950, "y": 980, "width": 90, "target": [580, 590]},
        ],
    }
    packed = fit_labels(raw)
    diagram = TeachingDiagram.model_validate(packed)
    assert packed["marks"] == raw["marks"]
    assert [label.target for label in diagram.labels] == [(450, 500), (580, 590)]
    assert diagram.labels[0].width > 90
    assert packed == fit_labels(packed)


def test_observation_record_remains_editable_and_previews(tmp_path):
    result = PptMasterService(tmp_path).create({"title": "蚕宝宝观察", "slides": [
        {"layout": "record", "title": "把观察变成证据", "subtitle": "每天同一时段观察",
         "items": [{"label": "日期"}, {"label": "阶段", "detail": "根据外观判断"},
                   {"label": "外观证据", "detail": "画下来或用文字描述"}],
         "note": "先让学生说出观察到的现象，再判断阶段。"},
    ]}, user_id=8, expected_pages=1)
    slide = Presentation(result.path).slides[0]
    table, = [shape.table for shape in slide.shapes if shape.has_table]
    assert table.cell(0, 2).text == "外观证据"
    assert table.cell(1, 1).text == "根据外观判断"
    assert not table.cell(2, 2).text
    assert "现象" in slide.notes_slide.notes_text_frame.text
    svg, _ = preview_slide(result.path, 1)
    assert "外观证据" in svg and "画下来或用文字描述" in svg


def test_silkworm_visuals_replace_poor_geometry_without_rewriting_facts():
    draft = {"title": "蚕宝宝探秘局", "slides": [
        {"layout": "diagram", "title": "蚕幼虫身体结构", "diagram": {"marks": []}, "note": "先让学生数足。"},
        {"layout": "content", "title": "阶段一：卵", "bullets": ["观察颜色和形状"], "note": "共同记录。"},
    ]}
    checked = _prefer_lesson_diagrams(draft, "请用图解")
    first, second = checked["slides"]
    assert "diagram" not in first and first["visualPreset"] == "silkworm-body"
    assert second["visualPreset"] == "silkworm-egg" and second["bullets"] == ["观察颜色和形状"]
    deck = parse_deck_spec(checked, expected_pages=2)
    assert "观察颜色和形状" in build_svg(deck.slides[1], 2, 2, deck)
    assert _visual_targets({"slides": [{"layout": layout} for layout in (
        "cover", "diagram", "content", "content", "content", "diagram", "record", "end",
    )]}) == [5]
