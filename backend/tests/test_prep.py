from secrets import token_urlsafe

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from backend.config import ROOT, Settings
from backend.database import make_engine
from backend.main import create_app, password_hash
from backend.models import User
from backend.skill_runtime.ppt_master import PptMasterService

LESSONS = "/api/v1/prep/lessons"
LINKS = "/api/v1/prep/links"
LESSON = {"grade": "三年级", "semester": "2026 秋", "title": "空气占据空间", "duration": 40}
DECK = {
    "title": "空气占据空间",
    "slides": [
        {"layout": "content", "title": "观察纸巾", "bullets": ["记录纸巾干湿"], "note": "引导观察"},
        {"layout": "quote", "title": "课堂问题", "bullets": ["空气从哪里出来？"], "note": "请学生说明证据"},
    ],
}


@pytest.fixture
def prep_server(tmp_path, monkeypatch):
    url = f"sqlite:///{(tmp_path / 'prep.sqlite3').as_posix()}"
    monkeypatch.setenv("DATABASE_URL", url)
    artifact_dir = tmp_path / "artifacts"
    monkeypatch.setenv("SKILL_ARTIFACT_DIR", str(artifact_dir))
    monkeypatch.setenv("SKILL_MEDIA_DIR", str(tmp_path / "media"))
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    engine = make_engine(url)
    password = token_urlsafe(24)
    with Session(engine) as db:
        hashed = password_hash.hash(password)
        teachers = [User(username=f"teacher_{suffix}", name=suffix, password_hash=hashed) for suffix in ("a", "b")]
        db.add_all(teachers)
        db.flush()
        owner_id = teachers[0].id
        db.commit()
    engine.dispose()
    settings = Settings(url, token_urlsafe(48), serve_frontend=False)
    with TestClient(create_app(settings)) as client:
        headers = []
        for suffix in ("a", "b"):
            login = client.post("/api/v1/auth/login", json={"username": f"teacher_{suffix}", "password": password})
            assert login.status_code == 200
            headers.append({"Authorization": "Bearer " + login.json()["access_token"]})
        yield client, settings, headers[0], headers[1], artifact_dir, owner_id


def test_parallel_classes_share_one_teacher_owned_lesson(prep_server):
    client, settings, owner, other, _, _ = prep_server
    assert client.get(LESSONS).status_code == 401
    lesson = client.post(LESSONS, headers=owner, json=LESSON)
    assert lesson.status_code == 201
    lesson_id = lesson.json()["id"]
    assert client.post(LESSONS, headers=owner, json=LESSON).status_code == 409
    assert client.patch(f"{LESSONS}/{lesson_id}", headers=other, json={"duration": 55}).status_code == 404
    assert client.patch(f"{LESSONS}/{lesson_id}", headers=owner, json={"duration": 55}).json()["duration"] == 55
    keys = ["mon:2:ClassB", "wed:3:ClassA"]
    for key in keys:
        assert client.put(f"{LINKS}/{key}", headers=owner, json={"lessonId": lesson_id}).status_code == 200
    assert client.put(f"{LINKS}/{keys[0]}", headers=other, json={"lessonId": lesson_id}).status_code == 404
    assert client.get(LINKS, headers=other).json() == []
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(LINKS, headers=owner).json() == [
            {"slotKey": key, "lessonId": lesson_id} for key in keys
        ]
        assert restarted.put(f"{LINKS}/{keys[0]}", headers=owner, json={"lessonId": None}).status_code == 200
        assert restarted.get(LINKS, headers=owner).json() == [{"slotKey": keys[1], "lessonId": lesson_id}]


def test_editing_one_slide_keeps_other_pages_and_previous_download(prep_server):
    client, _, owner, other, artifact_dir, owner_id = prep_server
    result = PptMasterService(artifact_dir).create(DECK, owner_id, expected_pages=2)
    api = LESSONS + "/" + str(client.post(LESSONS, headers=owner, json=LESSON).json()["id"])
    payload = {"artifactId": result.artifact_id}
    assert client.post(api + "/attach", headers=other, json=payload).status_code == 404
    attached = client.post(api + "/attach", headers=owner, json=payload)
    assert attached.status_code == 200
    assert attached.json()["revision"] == 1
    assert client.post(api + "/attach", headers=owner, json=payload).json()["revision"] == 1

    deck = attached.json()["deck"]
    untouched_page = deck["slides"][1].copy()
    deck["slides"][0]["title"] = "先预测纸巾干湿"
    saved = client.put(api + "/deck", headers=owner, json={"deck": deck, "revision": 1})
    assert saved.status_code == 200
    latest = saved.json()
    assert latest["revision"] == 2
    assert latest["artifact"]["id"] != result.artifact_id
    assert latest["deck"]["slides"][0]["title"] == "先预测纸巾干湿"
    assert latest["deck"]["slides"][1] == untouched_page
    assert client.put(api + "/deck", headers=owner, json={"deck": deck, "revision": 1}).status_code == 409

    deck["slides"][0]["title"] = ""
    assert client.put(api + "/deck", headers=owner, json={"deck": deck, "revision": 2}).status_code == 422
    assert client.get(api + "/deck", headers=owner).json() == latest
    old_download = f"/api/v1/chat/artifacts/{result.artifact_id}"
    assert client.get(old_download, headers=owner).status_code == 200


def test_ai_edit_proposes_one_page_without_saving(prep_server, monkeypatch):
    client, _, owner, other, artifact_dir, owner_id = prep_server
    result = PptMasterService(artifact_dir).create(DECK, owner_id, expected_pages=2)
    api = LESSONS + "/" + str(client.post(LESSONS, headers=owner, json=LESSON).json()["id"])
    original = client.post(api + "/attach", headers=owner, json={"artifactId": result.artifact_id}).json()
    suggestion = {"title": "预测纸巾干湿", "bullets": ["先写下你的预测"]}
    call_count = 0

    async def fake_provider(_key, model, messages, **_options):
        nonlocal call_count
        call_count += 1
        assert model == "deepseek-v4-pro"
        assert "课堂问题" in messages[1]["content"]
        assert messages[-1]["content"] == "把这页改成预测问题"
        return suggestion

    monkeypatch.setattr("backend.prep_ai.request_deepseek_json", fake_provider)
    route = api + "/deck/slides/1/ai-edit"
    payload = {"revision": 1, "instruction": "把这页改成预测问题"}
    assert client.post(route, headers=other, json=payload).status_code == 404
    assert client.post(route, headers=owner, json={**payload, "revision": 2}).status_code == 409
    assert call_count == 0
    response = client.post(route, headers=owner, json=payload)
    assert response.status_code == 200, response.text
    proposed = response.json()
    assert (proposed["revision"], proposed["page"]) == (1, 1)
    assert proposed["slide"]["title"] == "预测纸巾干湿"
    assert proposed["slide"]["note"] == original["deck"]["slides"][0]["note"]
    assert client.get(api + "/deck", headers=owner).json() == original

    deck = original["deck"]
    deck["slides"][0] = proposed["slide"]
    saved = client.put(api + "/deck", headers=owner, json={"deck": deck, "revision": 1})
    assert saved.status_code == 200, saved.text
    assert saved.json()["deck"]["slides"][1] == deck["slides"][1]
    suggestion = {"layout": "end"}
    assert client.post(route, headers=owner, json={**payload, "revision": 2}).status_code == 502
    assert client.get(api + "/deck", headers=owner).json() == saved.json()


def test_equipment_requires_own_sources_and_only_saves_once_confirmed(prep_server, monkeypatch):
    client, _, owner, other, _, _ = prep_server
    lesson = client.post(LESSONS, headers=owner, json=LESSON).json()
    route = f"{LESSONS}/{lesson['id']}/equipment"
    assert client.post(route).status_code == 401
    assert client.post(route, headers=other).status_code == 404
    assert client.post(route, headers=owner).json() == {"items": []}
    material = "每组使用透明杯2个，纸巾若干。"
    item = {"name": "透明杯", "quantity": "2个", "evidence": "透明杯2个"}
    async def equipment_provider(_key, _model, messages, **_options):
        assert messages[-1]["content"] == material
        return {"items": [item, item]}
    monkeypatch.setattr("backend.prep_ai.request_deepseek_json", equipment_provider)
    assert client.patch(f"{LESSONS}/{lesson['id']}", headers=owner, json={"materials": material}).status_code == 200
    assert client.post(route, headers=owner).json() == {"items": [item]}
    todos = '/api/v1/todos'
    day = {"date": "2026-11-18"}
    assert client.get(todos, headers=owner, params=day).json() == []
    item['quantity'] = '12个'
    assert client.post(route, headers=owner).json()['items'][0]['quantity'] == ''
    item.update(quantity='若干', evidence=material)
    assert client.post(route, headers=owner).json()['items'][0]['quantity'] == ''
    item['name'] = '量筒'
    assert client.post(route, headers=owner).status_code == 422
    selection = {"items": [{**day, "content": "准备透明杯（2个）", "legacy_key": "equipment:sample"}]}
    assert client.post(todos + '/import', headers=owner, json=selection).json() == {"imported": 1}
    assert client.post(todos + '/import', headers=owner, json=selection).json() == {"imported": 0}
    assert len(client.get(todos, headers=owner, params=day).json()) == 1
    assert client.get(todos, headers=other, params=day).json() == []
