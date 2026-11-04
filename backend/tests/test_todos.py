import os
from secrets import token_urlsafe

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import inspect, text
from sqlalchemy.engine import make_url
from sqlalchemy.orm import Session

from backend.config import ROOT, Settings
from backend.database import make_engine
from backend.main import create_app, password_hash
from backend.models import User

API = "/api/v1"
TODAY = "2026-11-04"
TOMORROW = "2026-11-05"


@pytest.fixture(scope="module")
def server(tmp_path_factory):
    url = os.getenv("WORKBENCH_TEST_DATABASE_URL") or f"sqlite:///{tmp_path_factory.mktemp('todo') / 'test.sqlite3'}"
    parsed = make_url(url)
    if parsed.get_backend_name() != "sqlite":
        assert parsed.database and parsed.database.endswith("_test"), "测试必须使用独立的 *_test 数据库"
    engine = make_engine(url)
    tables = set(inspect(engine).get_table_names())
    assert not tables - {"alembic_version"}, "测试数据库必须为空"
    if "alembic_version" in tables:
        with engine.connect() as connection:
            assert not connection.scalar(text("SELECT COUNT(*) FROM alembic_version")), "测试数据库必须回滚到初始状态"
    config = Config(str(ROOT / "alembic.ini"))
    old = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = url
    try:
        command.upgrade(config, "head")
        password = token_urlsafe(24)
        hashed = password_hash.hash(password)
        with Session(engine) as db:
            db.add_all([
                User(username="teacher_a", name="教师甲", password_hash=hashed),
                User(username="teacher_b", name="教师乙", password_hash=hashed),
            ])
            db.commit()
        settings = Settings(url, token_urlsafe(48), serve_frontend=False)
        with TestClient(create_app(settings)) as client:
            yield client, settings, password
    finally:
        command.downgrade(config, "base")
        engine.dispose()
        if old is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = old


def auth(client, username, password):
    response = client.post(API + "/auth/login", json={"username": username, "password": password})
    assert response.status_code == 200, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def test_auth_and_crud_persist_after_restart(server):
    client, settings, password = server
    assert client.get(API + "/health").json()["status"] == "ok"
    assert client.get(API + "/todos", params={"date": TODAY}).status_code == 401
    assert client.post(API + "/auth/login", json={"username": "teacher_a", "password": "wrong"}).status_code == 401
    headers = auth(client, "teacher_a", password)
    other = auth(client, "teacher_b", password)
    assert client.get(API + "/auth/me", headers=headers).json()["name"] == "教师甲"
    created = client.post(API + "/todos", headers=headers, json={"content": "  准备浮力实验 🧪  ", "priority": "high", "date": TODAY})
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["content"] == "准备浮力实验 🧪"
    route = API + "/todos/" + str(item["id"])
    assert client.get(route, headers=other).status_code == 404
    assert client.patch(route, headers=other, json={"done": True}).status_code == 404
    assert client.delete(route, headers=other).status_code == 404
    assert client.patch(route, headers=headers, json={"content": "   "}).status_code == 422
    assert client.patch(route, headers=headers, json={"done": None}).status_code == 422
    updated = client.patch(route, headers=headers, json={"content": "更新实验清单", "done": True, "date": TOMORROW})
    assert updated.status_code == 200
    assert client.get(API + "/todos", params={"date": TODAY}, headers=headers).json() == []
    with TestClient(create_app(settings)) as restarted:
        assert restarted.get(route, headers=headers).json()["content"] == "更新实验清单"
        assert restarted.get(API + "/todos", params={"date": TOMORROW}, headers=headers).json()[0]["done"] is True
        assert restarted.delete(route, headers=headers).status_code == 204
        assert restarted.get(route, headers=headers).status_code == 404


def test_batch_operations_and_import_are_scoped(server):
    client, _, password = server
    headers = auth(client, "teacher_a", password)
    other = auth(client, "teacher_b", password)
    imported = {"items": [{"legacy_key": "2026-11-04:1", "date": TODAY, "content": "导入的实验准备", "priority": "low"}]}
    assert client.post(API + "/todos/import", json=imported, headers=headers).json() == {"imported": 1}
    assert client.post(API + "/todos/import", json=imported, headers=headers).json() == {"imported": 0}
    assert client.post(API + "/todos/import", json=imported, headers=other).json() == {"imported": 1}
    assert client.post(API + "/todos", headers=headers, json={"date": TOMORROW, "content": "明日备课"}).status_code == 201
    assert client.post(API + "/todos/complete", params={"date": TODAY}, headers=headers).json() == {"updated": 1}
    assert client.delete(API + "/todos/completed", params={"date": TODAY}, headers=headers).json() == {"deleted": 1}
    assert client.get(API + "/todos", params={"date": TODAY}, headers=other).json()[0]["done"] is False
    assert client.get(API + "/todos", params={"date": TOMORROW}, headers=headers).json()[0]["done"] is False
