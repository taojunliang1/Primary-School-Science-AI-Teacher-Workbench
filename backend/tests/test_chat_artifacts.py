import json
import os
import re
from secrets import token_urlsafe
from urllib.parse import unquote

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session
from pptx import Presentation

from backend.chat import ChatReply
from backend.config import ROOT, Settings
from backend.database import make_engine
from backend.main import create_app, password_hash
from backend.models import User

API = "/api/v1"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    url = f"sqlite:///{tmp_path_factory.mktemp('chat') / 'test.sqlite3'}"
    parsed = make_url(url)
    assert parsed.get_backend_name() == "sqlite"
    engine = make_engine(url)
    assert not set(inspect(engine).get_table_names()) - {"alembic_version"}
    config = Config(str(ROOT / "alembic.ini"))
    old_db = os.environ.get("DATABASE_URL")
    old_artifact = os.environ.get("SKILL_ARTIFACT_DIR")
    artifact_dir = tmp_path_factory.mktemp("artifacts")
    os.environ["DATABASE_URL"] = url
    os.environ["SKILL_ARTIFACT_DIR"] = str(artifact_dir)
    try:
        command.upgrade(config, "head")
        password = token_urlsafe(16)
        with Session(engine) as db:
            user = User(username="chat_teacher", name="对话教师", password_hash=password_hash.hash(password))
            db.add(user)
            db.commit()
            user_id = user.id
        settings = Settings(url, token_urlsafe(48), serve_frontend=False, deepseek_api_key="test-key")
        with TestClient(create_app(settings)) as client:
            yield client, password, user_id, artifact_dir
    finally:
        command.downgrade(config, "base")
        engine.dispose()
        if old_db is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old_db
        if old_artifact is None:
            os.environ.pop("SKILL_ARTIFACT_DIR", None)
        else:
            os.environ["SKILL_ARTIFACT_DIR"] = old_artifact


def login(client, password):
    response = client.post(API + "/auth/login", json={"username": "chat_teacher", "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_chat_skills_endpoint_reports_catalog(server):
    client, password, _, _ = server
    headers = login(client, password)
    response = client.get(API + "/chat/skills", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data["skills"], list)
    assert isinstance(data["pptMasterReady"], bool)


def test_chat_returns_tool_trace_and_artifact(server, monkeypatch):
    client, password, user_id, _ = server
    headers = login(client, password)
    artifact = {
        "id": "b" * 32,
        "filename": "测试课件.pptx",
        "size": 12,
        "slideCount": 6,
        "downloadUrl": "/api/v1/chat/artifacts/" + "b" * 32,
    }

    async def fake_complete(payload, key, registry, ppt_master, media, current_user):
        assert current_user == user_id
        return ChatReply(model="deepseek-flash", text="已生成", tool_trace=[
            {"name": "create_ppt_with_ppt_master", "status": "ok", "summary": "已生成 6 页 PPTX"}
        ], artifacts=[artifact])

    monkeypatch.setattr("backend.main.complete_chat", fake_complete)
    response = client.post(API + "/chat/completions", headers=headers, json={
        "model": "science",
        "messages": [{"role": "user", "content": "做一个课件"}],
    })
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["text"] == "已生成"
    assert data["artifacts"][0]["filename"] == "测试课件.pptx"


def test_artifact_download_is_user_scoped(server):
    client, password, user_id, artifact_dir = server
    headers = login(client, password)
    artifact_id = "c" * 32
    user_dir = artifact_dir / str(user_id)
    user_dir.mkdir()
    (user_dir / f"{artifact_id}.pptx").write_bytes(b"fake-pptx")
    (user_dir / f"{artifact_id}.json").write_text(
        json.dumps({"filename": "课堂课件.pptx"}), encoding="utf-8"
    )
    response = client.get(API + "/chat/artifacts/" + artifact_id, headers=headers)
    assert response.status_code == 200
    assert response.content == b"fake-pptx"
    assert "课堂课件.pptx" in unquote(response.headers.get("content-disposition", ""))
    assert client.get(API + "/chat/artifacts/" + "d" * 32, headers=headers).status_code == 404
    path = API + "/chat/artifacts/" + artifact_id
    assert client.get(path).status_code == 401
    assert client.post(path + "/download").status_code == 401
    lookup = API + "/chat/artifacts/lookup"
    assert client.post(lookup, json=[artifact_id]).status_code == 401
    assert client.post(lookup, headers=headers, json=[artifact_id, "d" * 32]).json() == [
        {"id": artifact_id, "filename": "课堂课件.pptx", "slideCount": None}
    ]
    try:
        prepared = client.post(path + "/download", headers=headers)
        assert prepared.json()["url"] == path
        assert "HttpOnly" in prepared.headers["set-cookie"]
        assert f"Path={path}" in prepared.headers["set-cookie"]
        assert client.get(path).content == b"fake-pptx"
        assert client.get(path + "/preview").status_code == 401
        wrong_artifact = API + "/chat/artifacts/" + "d" * 32
        cookie = prepared.headers["set-cookie"].split(";", 1)[0]
        assert client.get(wrong_artifact, headers={"Cookie": cookie}).status_code == 401
    finally:
        client.cookies.clear()


@pytest.mark.parametrize("empty_first_passes", [False, True])
def test_stream_exports_editable_deck_without_external_skills(server, monkeypatch, empty_first_passes):
    client, password, user_id, artifact_dir = server
    monkeypatch.setenv("DSH_SKILLS_DIR", str(artifact_dir / "missing"))
    deck = {"title": "水循环", "theme": "field", "slides": [
        {"layout": "cover", "title": "水循环", "note": "先看湿地面"},
        {"layout": "diagram", "title": "蒸发", "takeaway": "液态水变成水蒸气", "diagram": {
            "marks": [
                {"kind": "ellipse", "box": [160, 610, 580, 190], "fill": "soft"},
                {"kind": "line", "points": [[450, 590], [450, 330]]},
            ],
            "labels": [{"text": "水蒸气", "x": 390, "y": 150, "width": 160, "target": [450, 330]}],
        }},
        {"layout": "end", "title": "回顾", "note": "让学生描述证据"},
    ]}
    stages = []

    async def fake_stream(_client, _key, model, messages, tools, max_tokens=4096, *,
                          thinking=False, json_output=False):
        assert tools is None
        stages.append((thinking, json_output))
        if not json_output:
            text = "" if empty_first_passes and thinking else "先观察蒸发，再用证据解释水循环。"
        elif "版面及字段检查结果" not in messages[-1]["content"]:
            assert "先观察蒸发" in messages[-1]["content"]
            text = json.dumps(deck, ensure_ascii=False)
        else:
            assert "第 2 页缺少教师备注" in messages[-1]["content"]
            repaired = {**deck["slides"][1], "note": "引导观察水滴"}
            text = "" if empty_first_passes and thinking else json.dumps(
                {"replacements": [{"page": 2, "slide": repaired}]}, ensure_ascii=False,
            )
        yield {"model": model, "choices": [{"delta": {"content": text}}]}

    monkeypatch.setattr("backend.chat._stream_deepseek", fake_stream)
    body = {"messages": [{"role": "user", "content": "制作《水循环》3 页 PPT"}]}
    assert client.post(API + "/chat/stream", json=body).status_code == 401
    headers = login(client, password)
    response = client.post(API + "/chat/stream", headers=headers, json=body)
    assert response.status_code == 200
    events = [json.loads(line) for line in response.iter_lines()]
    assert [event["type"] for event in events] == ["tool_start"] * (5 if empty_first_passes else 4) + [
        "tool_result", "done",
    ]
    expected_stages = [(True, False), (False, True), (True, True)]
    if empty_first_passes:
        expected_stages.insert(1, (False, False))
        expected_stages.append((False, True))
    assert stages == expected_stages
    assert "3 页可编辑课件" in events[-1]["reply"]["text"]
    artifact = events[-1]["reply"]["artifacts"][0]
    assert client.get(artifact["downloadUrl"], headers=headers).status_code == 200
    presentation = Presentation(artifact_dir / str(user_id) / f'{artifact["id"]}.pptx')
    assert len(presentation.slides) == 3
    assert any(shape.has_text_frame and "液态水变成水蒸气" in shape.text for shape in presentation.slides[1].shapes)
    assert presentation.slides[1].notes_slide.notes_text_frame.text == "引导观察水滴"
    preview_url = artifact["downloadUrl"] + "/preview"
    preview = client.get(preview_url, headers=headers, params={"slide": 2})
    assert preview.status_code == 200
    assert preview.headers["x-slide-count"] == "3"
    assert "液态水变成水蒸气" in preview.text
    assert "<ellipse" in preview.text and "<line" in preview.text
    assert "引导观察水滴" not in preview.text
    assert "<ellipse" in client.get(preview_url, headers=headers, params={"slide": 1}).text
    assert "<ellipse" not in client.get(preview_url, headers=headers, params={"slide": 3}).text
    assert client.get(preview_url, headers=headers, params={"slide": 4}).status_code == 404


def test_targeted_repair_keeps_good_pages_and_reports_all_issues(server, monkeypatch):
    client, password, user_id, artifact_dir = server
    original = {"layout": "content", "title": "观察原始证据",
                "bullets": ["比较水滴出现的位置"], "note": "先让学生描述观察结果。"}
    deck = {"title": "水滴从哪里来", "slides": [
        {"layout": "cover", "title": "水滴从哪里来", "note": "观察杯壁上的水滴。"},
        {"layout": "compare", "title": "杯子的变化", "items": [{"label": "冷杯", "detail": "出现水滴"}]},
        original,
        {"layout": "end", "title": "解释另一个现象"},
    ]}
    requests = []

    async def fake_stream(_client, _key, _model, messages, tools, max_tokens=4096, *,
                          thinking=False, json_output=False):
        assert tools is None
        prompt = messages[0]["content"]
        final = messages[-1]["content"]
        if not json_output:
            reply = "看见现象，提出解释，再迁移。"
        elif "本次只修订以下原始页码" in final:
            requests.append("targeted")
            pages = json.loads(final.split("\n本次只修订以下原始页码：\n", 1)[1])
            assert [item["page"] for item in pages] == [2, 4]
            reply = json.dumps({"replacements": [
                {"page": 2, "slide": {"items": [
                    {"label": "冷杯", "detail": "外壁可见水滴"}, {"label": "常温杯", "detail": "外壁暂未见水滴"},
                ], "note": "提醒学生对比相同时间内、相同位置的观察结果。"}},
                {"page": 4, "slide": {"note": "请学生说明浴室镜面水珠的来源。", "takeaway": "解释镜面上的水珠。"}},
                {"page": 3, "slide": {"title": "这是本次未指定的页面"}},
            ]}, ensure_ascii=False)
        elif "版面及字段检查结果" in final:
            requests.append("audit")
            assert "第 2 页缺少教师备注" in final and "第 4 页缺少教师备注" in final
            assert "每个替代页" in prompt
            reply = json.dumps({"replacements": [{"page": 3, "slide": {"bullets": []}}]}, ensure_ascii=False)
        else:
            reply = json.dumps(deck, ensure_ascii=False)
        yield {"choices": [{"delta": {"content": reply}}]}

    monkeypatch.setattr("backend.chat._stream_deepseek", fake_stream)
    response = client.post(API + "/chat/completions", headers=login(client, password), json={
        "messages": [{"role": "user", "content": "制作《水滴从哪里来》4 页 PPT"}],
    })
    assert response.status_code == 200, response.text
    assert requests == ["audit", "targeted"]
    file = response.json()["artifacts"][0]
    deck_source_path = artifact_dir / str(user_id) / f'{file["id"]}.source.json'
    result = json.loads(deck_source_path.read_text(encoding="utf-8"))
    assert all(result["slides"][2][field] == value for field, value in original.items())
    assert result["slides"][1]["layout"] == "compare"
    assert "浴室镜面" in result["slides"][3]["note"]


def test_long_deck_can_compose_sections_after_incomplete_generation(server, monkeypatch):
    client, password, user_id, artifact_dir = server
    parts = []
    draft_attempts = []

    async def fake_stream(_client, _key, _model, messages, tools, max_tokens=4096, *,
                          thinking=False, json_output=False):
        request = messages[0]["content"]
        if not json_output:
            output = "逐页设计正反观察和比较证据。"
        elif match := re.search(r"本次只制作第 (\d+)–(\d+) 页", request):
            start, end = map(int, match.groups())
            parts.append((start, end))
            slides = []
            for index in range(start, end + 1):
                slides.append({
                    "layout": "compare", "title": f"现象对照 {index}", "note": "观察两个样本并记录差异。",
                    "items": [{"label": "冷杯", "detail": "杯壁出现水滴"}, {"label": "常温杯", "detail": "杯壁没有水滴"}],
                })
            output = json.dumps({"title": "观察水滴", "slides": slides}, ensure_ascii=False)
        elif "版面及字段检查结果" in messages[-1]["content"]:
            output = '{"replacements":[]}'
        else:
            draft_attempts.append(max_tokens)
            output = '{"title":"观察水滴","slides":['
        yield {"choices": [{"delta": {"content": output}}]}

    monkeypatch.setattr("backend.chat._stream_deepseek", fake_stream)
    result = client.post(API + "/chat/completions", headers=login(client, password), json={
        "messages": [{"role": "user", "content": "制作《观察水滴》9 页 PPT"}],
    })
    assert result.status_code == 200, result.text
    assert len(draft_attempts) == 2
    assert sorted(parts) == [(1, 5), (6, 9)]
    file = result.json()["artifacts"][0]
    assert file["slideCount"] == 9
    source = json.loads((artifact_dir / str(user_id) / f'{file["id"]}.source.json').read_text(encoding="utf-8"))
    assert [slide["title"] for slide in source["slides"]] == [f"现象对照 {page}" for page in range(1, 10)]
