import json
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation

from backend.artifacts import ArtifactNotFound, artifact_path, load_artifact_source
from backend.skill_runtime.media import MediaService
from backend.skill_runtime.ppt_master import DeckSpecError, PptMasterService


def test_generated_source_matches_published_deck_and_stays_editable(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_ARTIFACT_DIR", str(tmp_path))
    renderer = PptMasterService(tmp_path)
    deck = {
        "title": " 水循环 ",
        "theme": "field",
        "slides": [{
            "title": " 水蒸气 ",
            "layout": "diagram",
            "note": "观察\n引导解释",
            "takeaway": "观察水汽",
            "diagram": {
                "marks": [{"kind": "ellipse", "box": [160, 610, 580, 190], "fill": "soft"}],
                "labels": [{"text": "蒸发", "x": 390, "y": 150, "width": 160, "target": [450, 330]}],
            },
        }],
    }
    result = renderer.create(deck, user_id=1)
    source = load_artifact_source(1, result.artifact_id)
    assert source["title"] == "水循环"
    assert source["theme"] == "field"
    assert [slide["layout"] for slide in source["slides"]] == ["cover", "diagram", "end"]
    assert result.slide_count == len(source["slides"]) == 3
    editable = source["slides"][1]
    assert editable["title"] == "水蒸气"
    assert editable["note"] == "观察\n引导解释"
    assert editable["diagram"]["labels"][0]["target"] == [450, 330]

    editable["diagram"]["labels"][0]["text"] = "水蒸发"
    updated = renderer.create(source, user_id=1, expected_pages=result.slide_count)
    assert updated.artifact_id != result.artifact_id
    assert load_artifact_source(1, updated.artifact_id) == source
    assert load_artifact_source(1, result.artifact_id)["slides"][1]["diagram"]["labels"][0]["text"] == "蒸发"
    with pytest.raises(ArtifactNotFound):
        load_artifact_source(2, result.artifact_id)

    with pytest.raises(DeckSpecError, match="课件编号已存在"):
        renderer.create(source, user_id=1, artifact_id=result.artifact_id)
    assert load_artifact_source(1, result.artifact_id)["slides"][1]["diagram"]["labels"][0]["text"] == "蒸发"


def test_legacy_downloads_work_without_editable_source(tmp_path, monkeypatch):
    monkeypatch.setenv("SKILL_ARTIFACT_DIR", str(tmp_path))
    artifact_id = "c" * 32
    directory = tmp_path / "1"
    directory.mkdir()
    pptx = directory / f"{artifact_id}.pptx"
    pptx.touch()
    (directory / f"{artifact_id}.json").write_text(json.dumps({"filename": "legacy.pptx"}))
    assert artifact_path(1, artifact_id)[0] == pptx
    with pytest.raises(ArtifactNotFound):
        load_artifact_source(1, artifact_id)


def test_source_retains_owned_image_reference_for_local_rerender(tmp_path, monkeypatch):
    artifacts = tmp_path / "artifacts"
    monkeypatch.setenv("SKILL_ARTIFACT_DIR", str(artifacts))
    media_root = tmp_path / "media"
    media = MediaService(media_root)
    directory = media_root / "1"
    directory.mkdir()
    asset = "f" * 32
    filename = f"{asset}.png"
    Image.new("RGB", (32, 24), "blue").save(directory / filename)
    (directory / f"{asset}.json").write_text(json.dumps({
        "filename": filename, "source": "web", "caption": "水滴", "attribution": "example.test",
    }), encoding="utf-8")
    image = {"assetId": asset, "caption": "露水", "fit": "contain"}
    deck = {"title": "水循环", "slides": [
        {"title": "水滴", "layout": "figure", "image": image, "note": "找一找水滴"},
    ]}
    renderer = PptMasterService(artifacts, media)
    original = renderer.create(deck, user_id=1, expected_pages=1)
    source = load_artifact_source(1, original.artifact_id)
    assert source["slides"][0]["image"] == image
    assert source["slides"][0]["note"] == "找一找水滴"
    updated = renderer.create(source, user_id=1, expected_pages=1)
    pptx = Presentation(updated.path)
    assert len(pptx.slides) == 1
    assert pptx.slides[0].notes_slide.notes_text_frame.text == "找一找水滴\n配图来源：example.test"


def test_failed_publish_cleans_unpublished_presentation(tmp_path, monkeypatch):
    artifact_id = "a" * 32
    real_replace = Path.replace

    def reject_metadata(path, target):
        if target.name == f"{artifact_id}.json":
            raise OSError("metadata publication failed")
        return real_replace(path, target)

    monkeypatch.setattr(Path, "replace", reject_metadata)
    renderer = PptMasterService(tmp_path)
    with pytest.raises(OSError, match="metadata publication failed"):
        renderer.create({"title": "水循环", "slides": [{"title": "蒸发"}]}, user_id=1, artifact_id=artifact_id)
    assert not list((tmp_path / "1").iterdir())
