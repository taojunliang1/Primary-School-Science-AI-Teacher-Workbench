"""Store the recurring weekly timetable without mixing it with lesson plans."""

import hashlib
import json
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, StringConstraints, model_validator
from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session

from .models import Course, User

WEEKLY_STATUS = "weekly_template"


class CourseCell(BaseModel):
    day: Annotated[int, Field(ge=1, le=5)]
    period: Annotated[str, StringConstraints(pattern=r"^\d{2}:\d{2}–\d{2}:\d{2}$")]
    text: Annotated[str, StringConstraints(max_length=60)] = ""
    courseType: Literal["regular", "contest", "event", "empty"]
    important: bool = False

    @model_validator(mode="after")
    def check_cell(self):
        if bool(self.text.strip()) == (self.courseType == "empty"):
            raise ValueError("课表分类与课程内容不匹配")
        if self.important and self.courseType not in {"regular", "contest"}:
            raise ValueError("仅课程可添加标记")
        return self


class ScheduleSave(BaseModel):
    version: Annotated[str, StringConstraints(pattern=r"^[a-f0-9]{64}$")] | None
    cells: Annotated[list[CourseCell], Field(min_length=1, max_length=80)]

    @model_validator(mode="after")
    def check_unique_slots(self):
        if len({(cell.day, cell.period) for cell in self.cells}) != len(self.cells):
            raise ValueError("课表包含重复时间格")
        return self


def read_schedule(db: Session, user_id: int, *, lock: bool = False):
    statement = select(Course).where(
        Course.user_id == user_id, Course.status == WEEKLY_STATUS,
    ).order_by(Course.day_of_week, Course.period)
    courses = db.scalars(statement.with_for_update() if lock else statement).all()
    cells = [
        CourseCell(day=course.day_of_week, period=course.period,
                   text=course.course_name, courseType=course.course_type,
                   important=bool(course.important)).model_dump()
        for course in courses
    ]
    version = hashlib.sha256(json.dumps(cells, sort_keys=True).encode()).hexdigest() if cells else None
    return {"version": version, "cells": cells}


def build_schedule_router(get_db, current_user):
    router = APIRouter()
    Database = Annotated[Session, Depends(get_db)]
    Teacher = Annotated[User, Depends(current_user)]

    @router.get("/courses")
    def get_courses(db: Database, user: Teacher):
        return read_schedule(db, user.id)

    @router.put("/courses")
    def put_courses(payload: ScheduleSave, db: Database, user: Teacher):
        # Serialize concurrent saves, including when an account has no schedule rows.
        db.execute(update(User).where(User.id == user.id).values(id=User.id))
        if read_schedule(db, user.id, lock=True)["version"] != payload.version:
            raise HTTPException(409, "另一处已更新账号课表。请刷新课表后再提交")
        db.execute(delete(Course).where(Course.user_id == user.id, Course.status == WEEKLY_STATUS))
        db.add_all(Course(
            user_id=user.id, day_of_week=cell.day, period=cell.period,
            class_name=cell.text if cell.courseType == "regular" else "",
            course_name=cell.text, status=WEEKLY_STATUS, course_type=cell.courseType,
            important=cell.important,
        ) for cell in payload.cells)
        db.flush()
        result = read_schedule(db, user.id, lock=True)
        db.commit()
        return result

    return router
