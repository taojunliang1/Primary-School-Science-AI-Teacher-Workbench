from datetime import date as calendar_date
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator

Username = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=3, max_length=64, pattern=r"^[a-z0-9_.-]+$")]
Content = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Priority = Literal["normal", "high", "low"]


class Login(BaseModel):
    username: Username
    password: Annotated[str, Field(min_length=1, max_length=128)]


class UserView(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    name: str


class LoginResult(BaseModel):
    access_token: str
    token_type: Literal["bearer"] = "bearer"
    user: UserView


class TodoCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: Content
    priority: Priority = "normal"
    date: calendar_date
    done: bool = False


class TodoUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    content: Content | None = None
    priority: Priority | None = None
    date: calendar_date | None = None
    done: bool | None = None

    @model_validator(mode="after")
    def require_values(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("至少提供一项有效的修改")
        return self


class TodoView(TodoCreate):
    model_config = ConfigDict(from_attributes=True)
    id: int


class LegacyTodo(TodoCreate):
    legacy_key: Annotated[str, StringConstraints(min_length=1, max_length=128)]


class LegacyImport(BaseModel):
    items: Annotated[list[LegacyTodo], Field(min_length=1, max_length=500)]
