import logging
from contextlib import asynccontextmanager
from datetime import date as CalendarDate, datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, FastAPI, HTTPException, Path, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from pwdlib import PasswordHash
from sqlalchemy import delete, select, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker

from .chat import ChatReply, ChatRequest, complete_chat
from .config import ROOT, Settings
from .database import make_engine
from .models import Todo, User
from .schemas import LegacyImport, Login, LoginResult, TodoCreate, TodoUpdate, TodoView, UserView

password_hash = PasswordHash.recommended()
log = logging.getLogger(__name__)
ISSUER = "science-workbench"
AUDIENCE = "science-workbench-api"


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

    @api.post("/chat/completions", response_model=ChatReply)
    async def chat(payload: ChatRequest, _user: Teacher):
        return await complete_chat(payload, settings.deepseek_api_key)

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

    app.include_router(api)
    if settings.serve_frontend and (ROOT / "dist" / "index.html").is_file():
        app.mount("/", StaticFiles(directory=ROOT / "dist", html=True), name="frontend")
    return app
