from xml.etree import ElementTree

from backend.skill_runtime.ppt_master import build_svg, parse_deck_spec


SVG = {"svg": "http://www.w3.org/2000/svg"}


def test_dense_process_keeps_projection_copy_and_takeaway():
    detail = "观察小组把同样大小的纸巾分别放在不同位置然后取出比较干湿记录看见的现象并用证据解释结果" * 2
    detail = detail[:85]
    takeaway = "请记录纸巾是否潮湿并说出判断依据" * 5
    takeaway = takeaway[:70]
    deck = parse_deck_spec({
        "title": "纸巾实验",
        "slides": [{
            "layout": "process",
            "title": "分步观察",
            "items": [
                {"label": f"第{index}步观察", "detail": detail} for index in range(1, 5)
            ],
            "takeaway": takeaway,
        }],
    }, expected_pages=1)
    svg = ElementTree.fromstring(build_svg(deck.slides[0], 1, 1, deck))
    copy = "".join(node.text or "" for node in svg.findall("svg:text", SVG))

    assert copy.count(detail) == 4
    assert takeaway in copy
    # Four steps remain distinct and readable instead of overlapping in narrow columns.
    numbers = [node for node in svg.findall("svg:text", SVG) if node.text in {"1", "2", "3", "4"}]
    assert len(numbers) == 4
    assert len({node.get("y") for node in numbers}) == 4


def test_six_points_flow_across_two_editable_columns():
    phrases = [f"现象{index}提示我们仔细观察变化" for index in range(1, 7)]
    deck = parse_deck_spec({
        "title": "观察现象",
        "slides": [{"layout": "content", "title": "观察提示", "bullets": phrases}],
    }, expected_pages=1)
    svg = ElementTree.fromstring(build_svg(deck.slides[0], 1, 1, deck))
    entries = [node for node in svg.findall("svg:text", SVG) if node.text in phrases]

    assert [node.text for node in entries] == phrases
    assert len({node.get("x") for node in entries}) == 2
    assert all(float(node.get("font-size")) >= 20 for node in entries)
