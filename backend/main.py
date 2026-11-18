import json
import logging
import os
from contextlib import asynccontextmanager
from datetime import date as CalendarDate, datetime, timedelta, timezone
from pathlib import Path as FilePath
from typing import Annotated

import jwt
from fastapi import APIRouter, Body, Depends, FastAPI, HTTPException, Path, Query, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pwdlib import PasswordHash
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .artifacts import ArtifactNotFound, artifact_path, artifact_root
from .artifact_preview import preview_slide
from .chat import ChatReply, ChatRequest, chat_events, complete_chat
from .config import ROOT, Settings
from .database import make_engine
from .models import Todo, User
from .prep import build_prep_router
from .prep_materials import build_material_router
from .schemas import LegacyImport, Login, LoginResult, TodoCreate, TodoUpdate, TodoView, UserView
from .skill_registry import SkillRegistry
from .skill_runtime.media import MediaService
from .skill_runtime.ppt_master import PptMasterService
from .weekly_schedule import build_schedule_router

password_hash = PasswordHash.recommended()
log = logging.getLogger(__name__)
ISSUER = "science-workbench"
AUDIENCE = "science-workbench-api"
DOWNLOAD_AUDIENCE = "science-workbench-artifact"
DOWNLOAD_COOKIE = "chat_artifact_download"
DOWNLOAD_LIFETIME = 120


def create_app(settings: Settings | None = None):
    settings = settings or Settings.from_env()
    engine = make_engine(settings.database_url)
    sessions = sessionmaker(engine, expire_on_commit=False)
    dummy_hash = password_hash.hash("not-a-valid-account-password")

    @asynccontextmanager
    async def lifespan(_app):
        yield
        engine.dispose()

    app = FastAPI(title="小学科学 AI 教师工作台 API", version="0.1.0", lifespan=lifespan)
    api = APIRouter(prefix="/api/v1")
    bearer = HTTPBearer(auto_error=False)
    skill_registry = SkillRegistry(ROOT / "backend" / "skills")
    media_dir = FilePath(os.getenv("SKILL_MEDIA_DIR", str(ROOT / "backend" / "media")))
    media = MediaService(media_dir)
    ppt_master = PptMasterService(artifact_dir=artifact_root(), media=media)

    def get_db():
        with sessions() as session:
            yield session

    DB = Annotated[Session, Depends(get_db)]
    TodoId = Annotated[int, Path(ge=1, le=2147483647)]

    def unauthorized(detail="请登录后继续"):
        return HTTPException(401, detail, headers={"WWW-Authenticate": "Bearer"})

    def current_user(db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if not credentials:
            raise unauthorized()
        try:
            claims = jwt.decode(
                credentials.credentials, settings.jwt_secret, algorithms=["HS256"],
                issuer=ISSUER, audience=AUDIENCE, options={"require": ["exp", "iat", "sub"]},
            )
            user_id = int(claims["sub"])
            if not 1 <= user_id <= 2147483647:
                raise ValueError
        except (jwt.InvalidTokenError, ValueError, TypeError):
            raise unauthorized("登录已失效，请重新登录")
        user = db.get(User, user_id)
        if not user:
            raise unauthorized("登录已失效，请重新登录")
        return user

    Teacher = Annotated[User, Depends(current_user)]

    @app.exception_handler(RequestValidationError)
    async def invalid_request(_request, _error):
        return JSONResponse(status_code=422, content={"detail": "提交内容格式不正确，请检查后重试"})

    @app.exception_handler(SQLAlchemyError)
    async def database_error(_request, error):
        log.error("Database operation failed: %s", type(error).__name__)
        return JSONResponse(status_code=503, content={"detail": "数据库暂不可用，请稍后再试"})

    @api.get("/health")
    def health(db: DB):
        db.execute(text("SELECT 1"))
        return {"status": "ok", "database": engine.dialect.name}

    @api.post("/auth/login", response_model=LoginResult)
    def login(payload: Login, response: Response, db: DB):
        user = db.scalar(select(User).where(User.username == payload.username))
        verified = password_hash.verify(payload.password, user.password_hash if user else dummy_hash)
        if not user or not verified:
            raise unauthorized("用户名或密码不正确")
        now = datetime.now(timezone.utc)
        token = jwt.encode({
            "sub": str(user.id), "iat": now, "exp": now + timedelta(hours=8),
            "iss": ISSUER, "aud": AUDIENCE,
        }, settings.jwt_secret, algorithm="HS256")
        response.headers["Cache-Control"] = "no-store"
        return LoginResult(access_token=token, user=UserView.model_validate(user))

    @api.get("/auth/me", response_model=UserView)
    def me(user: Teacher):
        return user

    @api.get("/chat/skills")
    def chat_skills(_user: Teacher):
        return {
            "skills": [
                {"name": skill.name, "description": skill.description}
                for skill in skill_registry.all()
            ],
            "pptMasterReady": True,
        }

    @api.post("/chat/completions", response_model=ChatReply)
    async def chat(payload: ChatRequest, user: Teacher):
        return await complete_chat(payload, settings.deepseek_api_key, skill_registry,
                                   ppt_master, media, user.id)

    @api.post("/chat/stream")
    def stream_chat(payload: ChatRequest, user: Teacher, db: DB):
        user_id = user.id
        db.close()
        if not settings.deepseek_api_key:
            raise HTTPException(503, "DeepSeek 尚未配置，请在后端设置 API 密钥")

        async def events():
            try:
                async for event in chat_events(payload, settings.deepseek_api_key, skill_registry,
                                               ppt_master, media, user_id):
                    yield json.dumps(event, ensure_ascii=False) + "\n"
            except HTTPException as exc:
                yield json.dumps({"type": "error", "message": exc.detail}, ensure_ascii=False) + "\n"

        return StreamingResponse(events(), media_type="application/x-ndjson", headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
        })

    def find_artifact(user_id, artifact_id):
        try:
            return artifact_path(user_id, artifact_id)
        except ArtifactNotFound:
            raise HTTPException(404, "文件已不存在，请从对话中重新生成")

    @api.post("/chat/artifacts/lookup")
    def lookup_artifacts(ids: Annotated[list[str], Body(max_length=32)], user: Teacher, response: Response):
        response.headers["Cache-Control"] = "private, no-store"
        files = []
        for artifact_id in dict.fromkeys(ids):
            try:
                path, meta = artifact_path(user.id, artifact_id)
            except ArtifactNotFound:
                continue
            files.append({
                "id": artifact_id,
                "filename": meta.get("filename") or path.name,
                "slideCount": meta.get("slides"),
            })
        return files

    @api.post("/chat/artifacts/{artifact_id}/download")
    def authorize_artifact_download(artifact_id: str, request: Request, response: Response, user: Teacher):
        find_artifact(user.id, artifact_id)
        url = request.url.path.removesuffix("/download")
        now = datetime.now(timezone.utc)
        ticket = jwt.encode({
            "sub": str(user.id), "artifact": artifact_id, "iat": now,
            "exp": now + timedelta(seconds=DOWNLOAD_LIFETIME),
            "iss": ISSUER, "aud": DOWNLOAD_AUDIENCE,
        }, settings.jwt_secret, algorithm="HS256")
        response.set_cookie(DOWNLOAD_COOKIE, ticket, max_age=DOWNLOAD_LIFETIME,
                            path=url, httponly=True, samesite="strict", secure=request.url.scheme == "https")
        response.headers["Cache-Control"] = "private, no-store"
        return {"url": url}

    @api.get("/chat/artifacts/{artifact_id}/preview")
    def chat_artifact_preview(artifact_id: str, user: Teacher, slide: Annotated[int, Query(ge=1, le=24)] = 1):
        path, _ = find_artifact(user.id, artifact_id)
        try:
            svg, count = preview_slide(path, slide)
        except IndexError as exc:
            raise HTTPException(404, "找不到这张幻灯片") from exc
        except ValueError as exc:
            raise HTTPException(422, "暂时无法预览，可直接下载 PowerPoint 文件") from exc
        return Response(svg, media_type="image/svg+xml", headers={
            "Cache-Control": "private, no-store",
            "Content-Security-Policy": "default-src 'none'; img-src data:; sandbox",
            "X-Content-Type-Options": "nosniff",
            "X-Slide-Count": str(count),
        })

    @api.get("/chat/artifacts/{artifact_id}")
    def chat_artifact(artifact_id: str, request: Request, db: DB,
                      credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials:
            user_id = current_user(db, credentials).id
        else:
            try:
                claims = jwt.decode(
                    request.cookies.get(DOWNLOAD_COOKIE, ""), settings.jwt_secret, algorithms=["HS256"],
                    issuer=ISSUER, audience=DOWNLOAD_AUDIENCE, options={"require": ["exp", "sub", "artifact"]},
                )
                if claims["artifact"] != artifact_id:
                    raise ValueError
                user_id = int(claims["sub"])
            except (jwt.InvalidTokenError, ValueError, TypeError):
                raise unauthorized("下载链接已过期，请在文件卡片上重新点击下载")
        path, meta = find_artifact(user_id, artifact_id)
        return FileResponse(
            path,
            media_type="application/vnd.openxmlformats-officedocument.presentationml.presentation",
            filename=meta.get("filename") or path.name,
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

    def owned_todo(todo_id: int, user: User, db: Session):
        todo = db.scalar(select(Todo).where(Todo.id == todo_id, Todo.user_id == user.id))
        if not todo:
            raise HTTPException(404, "找不到该待办")
        return todo

    @api.get("/todos", response_model=list[TodoView])
    def list_todos(date: CalendarDate, user: Teacher, db: DB):
        return db.scalars(select(Todo).where(Todo.user_id == user.id, Todo.date == date).order_by(Todo.id.desc())).all()

    @api.post("/todos", response_model=TodoView, status_code=201)
    def create_todo(payload: TodoCreate, user: Teacher, db: DB):
        todo = Todo(user_id=user.id, **payload.model_dump())
        db.add(todo)
        db.commit()
        return todo

    @api.post("/todos/complete")
    def complete_todos(date: CalendarDate, user: Teacher, db: DB):
        result = db.execute(update(Todo).where(Todo.user_id == user.id, Todo.date == date, Todo.done.is_(False)).values(done=True))
        db.commit()
        return {"updated": result.rowcount}

    @api.delete("/todos/completed")
    def clear_completed(date: CalendarDate, user: Teacher, db: DB):
        result = db.execute(delete(Todo).where(Todo.user_id == user.id, Todo.date == date, Todo.done.is_(True)))
        db.commit()
        return {"deleted": result.rowcount}

    @api.post("/todos/import")
    def import_todos(payload: LegacyImport, user: Teacher, db: DB):
        # Lock this teacher's row so two tabs importing the same data stay idempotent.
        db.execute(select(User.id).where(User.id == user.id).with_for_update()).scalar_one()
        keys = {item.legacy_key for item in payload.items}
        seen = set(db.scalars(
            select(Todo.legacy_key).where(Todo.user_id == user.id, Todo.legacy_key.in_(keys)).with_for_update()
        ))
        imported = 0
        for item in payload.items:
            if item.legacy_key not in seen:
                db.add(Todo(user_id=user.id, **item.model_dump()))
                seen.add(item.legacy_key)
                imported += 1
        db.commit()
        return {"imported": imported}

    @api.get("/todos/{todo_id}", response_model=TodoView)
    def get_todo(todo_id: TodoId, user: Teacher, db: DB):
        return owned_todo(todo_id, user, db)

    @api.patch("/todos/{todo_id}", response_model=TodoView)
    def patch_todo(todo_id: TodoId, payload: TodoUpdate, user: Teacher, db: DB):
        todo = owned_todo(todo_id, user, db)
        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(todo, field, value)
        db.commit()
        return todo

    @api.delete("/todos/{todo_id}", status_code=204, response_class=Response)
    def delete_todo(todo_id: TodoId, user: Teacher, db: DB):
        db.delete(owned_todo(todo_id, user, db))
        db.commit()
        return Response(status_code=204)

    api.include_router(build_prep_router(get_db, current_user, ppt_master, settings.deepseek_api_key))
    api.include_router(build_schedule_router(get_db, current_user))
    api.include_router(build_material_router(current_user, settings.deepseek_api_key))
    app.include_router(api)
    if settings.serve_frontend and (ROOT / "dist" / "index.html").is_file():
        app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="frontend")
    return app
