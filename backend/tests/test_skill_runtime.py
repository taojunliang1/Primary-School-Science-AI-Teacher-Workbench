import json

import pytest

from backend.artifacts import ArtifactNotFound, artifact_path
from backend.chat import requested_pages, requested_title
from backend.skill_registry import SkillRegistry
from backend.skill_runtime.media import MediaService
from backend.skill_runtime.ppt_master import DeckSpecError, parse_deck_spec


def write_skill(root, folder, name, description):
    path = root / folder
    path.mkdir()
    (path / "SKILL.md").write_text(
        f"---\nname: {name}\ndescription: {description}\n---\n\n# {name}\n",
        encoding="utf-8",
    )


def test_registry_reads_skill_folders(tmp_path):
    write_skill(tmp_path, "alpha-skill", "alpha-skill", "第一个技能")
    write_skill(tmp_path, "beta-skill", "beta-skill", "第二个技能")
    (tmp_path / "not-a-skill").mkdir()
    registry = SkillRegistry(tmp_path)
    assert [skill.name for skill in registry.all()] == ["alpha-skill", "beta-skill"]
    assert "alpha-skill" in registry.catalog_text()
    assert "第二个技能" in registry.read("beta-skill")
    assert registry.get("ALPHA-SKILL").name == "alpha-skill"


def test_registry_ignores_broken_frontmatter(tmp_path):
    broken = tmp_path / "broken"
    broken.mkdir()
    (broken / "SKILL.md").write_text("# no frontmatter\n", encoding="utf-8")
    assert SkillRegistry(tmp_path).all() == []


def test_deck_spec_adds_cover_and_ending():
    deck = parse_deck_spec({
        "title": "水的三态变化",
        "slides": [
            {"layout": "content", "title": "水有三种状态", "bullets": ["固态", "液态", "气态"]},
        ],
    })
    assert [slide.layout for slide in deck.slides] == ["cover", "content", "end"]
    assert deck.slides[0].title == "水的三态变化"


def test_requested_pages_reads_arabic_and_chinese_numbers():
    assert requested_pages("请做 3 页课件") == 3
    assert requested_pages("做八页，包含封面") == 8
    assert requested_pages("十二页的微课") == 12
    assert requested_pages("第 2 页配图，共 8 页") == 8
    assert requested_pages("第二页配图") is None
    assert requested_pages("帮我做个课件") is None


def test_requested_title_reads_book_title():
    assert requested_title("请用 ppt-master 把《水的三态变化》做成 3 页") == "水的三态变化"
    assert requested_title("帮我做个课件") is None


def test_deck_spec_enforces_requested_title():
    with pytest.raises(DeckSpecError, match="标题必须使用"):
        parse_deck_spec({
            "title": "猜一猜",
            "slides": [{"layout": "cover", "title": "猜一猜"}],
        }, expected_title="水的三态变化")


def test_deck_spec_enforces_requested_page_count():
    with pytest.raises(DeckSpecError, match="用户要求 5 页"):
        parse_deck_spec({
            "title": "测试",
            "slides": [
                {"layout": "cover", "title": "封面"},
                {"layout": "content", "title": "内容"},
                {"layout": "end", "title": "结束"},
            ],
        }, expected_pages=5)


def test_media_local_draw_saves_user_asset(tmp_path):
    media = MediaService(tmp_path)
    asset = media.draw("水的三态变化", 7, ["固态", "液态", "气态"], "三态示意图")
    assert asset.source == "diagram"
    assert asset.path.is_file()
    assert asset.width == 1200 and asset.height == 900
    assert media.resolve(7, asset.id).caption == "三态示意图"
    with pytest.raises(Exception):
        media.resolve(8, asset.id)


def test_deck_spec_accepts_image_on_content_slide():
    asset_id = "a" * 32
    deck = parse_deck_spec({
        "title": "测试",
        "slides": [{
            "layout": "content",
            "title": "配图页",
            "bullets": ["要点"],
            "image": {"assetId": asset_id, "caption": "示意图", "fit": "contain"},
        }],
    })
    assert deck.slides[1].image_asset_id == asset_id
    assert deck.slides[1].image_caption == "示意图"
    assert deck.slides[1].image_fit == "contain"


def test_deck_spec_rejects_image_on_comparison():
    with pytest.raises(DeckSpecError, match="图片可用于"):
        parse_deck_spec({
            "title": "测试",
            "slides": [{
                "layout": "compare",
                "title": "对比",
                "image": {"assetId": "a" * 32},
            }],
        })


def test_deck_supports_one_page_and_validates_layout_items():
    payload = {"title": "固态与液态", "slides": [{
        "layout": "compare", "title": "固态与液态",
        "items": [{"label": "固态", "detail": "保持形状"}, {"label": "液态", "detail": "随容器改变形状"}],
    }]}
    deck = parse_deck_spec(payload, expected_pages=1)
    assert len(deck.slides) == 1
    assert deck.slides[0].items[1].detail == "随容器改变形状"
    payload["slides"][0]["items"].pop()
    with pytest.raises(DeckSpecError, match="compare"):
        parse_deck_spec(payload, expected_pages=1)


def test_exact_page_count_preserves_final_activity():
    deck = parse_deck_spec({"title": "水循环", "slides": [
        {"layout": "cover", "title": "水循环"},
        {"layout": "quote", "title": "说出你的解释", "bullets": ["镜子上的水滴从哪里来？"]},
    ]}, expected_pages=2)
    assert [slide.layout for slide in deck.slides] == ["cover", "quote"]


def test_deck_spec_rejects_too_many_bullets():
    with pytest.raises(DeckSpecError):
        parse_deck_spec({
            "title": "测试",
            "slides": [{
                "layout": "content",
                "title": "太多了",
                "bullets": ["1", "2", "3", "4", "5", "6", "7"],
            }],
        })


def test_artifact_path_is_user_scoped(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_ARTIFACT_DIR", str(tmp_path))
    user_dir = tmp_path / "7"
    user_dir.mkdir()
    artifact_id = "a" * 32
    (user_dir / f"{artifact_id}.pptx").write_bytes(b"pptx")
    (user_dir / f"{artifact_id}.json").write_text(
        json.dumps({"filename": "测试.pptx"}), encoding="utf-8"
    )
    path, meta = artifact_path(7, artifact_id)
    assert path.read_bytes() == b"pptx"
    assert meta["filename"] == "测试.pptx"
    with pytest.raises(ArtifactNotFound):
        artifact_path(8, artifact_id)
    with pytest.raises(ArtifactNotFound):
        artifact_path(7, "../escape")
