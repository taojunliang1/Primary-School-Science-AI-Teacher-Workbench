"""Teacher-owned lesson plans and revisioned PowerPoint source."""

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, ConfigDict, Field, StringConstraints, model_validator
from sqlalchemy import delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .artifacts import ArtifactNotFound, artifact_path, load_artifact_source
from .models import CoursewareProject, LessonUnit, PrepSlotLink, User
from .prep_ai import EquipmentList, extract_equipment, suggest_slide
from .skill_runtime.media import MediaUnavailable
from .skill_runtime.ppt_master import MAX_SLIDES, DeckSpecError, SkillUnavailable

LessonId = Annotated[int, Path(ge=1, le=2147483647)]
SlotKey = Annotated[str, Path(pattern=r"^[A-Za-z0-9_.:-]{1,260}$")]
Grade = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=24)]
Semester = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
Title = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=4000)]
Duration = Annotated[int, Field(ge=1, le=240)]
Revision = Annotated[int, Field(ge=1, le=2147483647)]
MAX_REVISION = 2147483647
MAX_DECK_BYTES = 256_000


class LessonFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: Grade
    semester: Semester
    title: Title
    duration: Duration = 40
    objectives: Description = ""
    materials: Description = ""


class LessonUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    grade: Grade | None = None
    semester: Semester | None = None
    title: Title | None = None
    duration: Duration | None = None
    objectives: Description | None = None
    materials: Description | None = None

    @model_validator(mode="after")
    def require_values(self):
        if not self.model_fields_set or any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("至少提供一项有效的修改")
        return self


class LessonView(LessonFields):
    id: int
    artifactId: str | None
    slideCount: int | None
    revision: Revision | None


class LinkChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lessonId: Annotated[int, Field(ge=1, le=2147483647)] | None


class LinkView(LinkChange):
    slotKey: str


class DeckAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")

    artifactId: Annotated[str, Field(pattern=r"^[a-f0-9]{32}$")]
    revision: Revision | None = None


class DeckUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    deck: dict
    revision: Revision

    @model_validator(mode="after")
    def cap_source(self):
        pages = self.deck.get("slides")
        if not isinstance(pages, list) or not 1 <= len(pages) <= MAX_SLIDES:
            raise ValueError(f"课件需包含 1 至 {MAX_SLIDES} 页")
        if len(json.dumps(self.deck, ensure_ascii=False, allow_nan=False).encode("utf-8")) > MAX_DECK_BYTES:
            raise ValueError("课件内容过长")
        return self


class DeckArtifact(BaseModel):
    id: str
    filename: str
    slideCount: int
    size: int


class DeckView(BaseModel):
    deck: dict
    revision: Revision
    artifact: DeckArtifact


class SlideAiEdit(BaseModel):
    model_config = ConfigDict(extra="forbid")
    revision: Revision
    instruction: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=600)]


class SlideSuggestion(BaseModel):
    page: int
    revision: Revision
    slide: dict


def lesson_view(lesson, project):
    return {
        "id": lesson.id,
        "grade": lesson.grade,
        "semester": lesson.semester,
        "title": lesson.title,
        "duration": lesson.duration,
        "objectives": lesson.objectives,
        "materials": lesson.materials,
        "artifactId": project.artifact_id if project else None,
        "slideCount": project.slide_count if project else None,
        "revision": project.revision if project else None,
    }


def deck_view(user_id, deck, revision, artifact_id, slide_count):
    try:
        _, metadata = artifact_path(user_id, artifact_id)
    except ArtifactNotFound:
        # The database source remains available for re-export after a file is moved.
        metadata = {}
    return {
        "deck": deck,
        "revision": revision,
        "artifact": {
            "id": artifact_id,
            "filename": metadata.get("filename") or f'{deck.get("title") or "课件"}.pptx',
            "slideCount": slide_count,
            "size": metadata.get("size") or 0,
        },
    }


def version_conflict():
    return HTTPException(409, "这份课件已有更新，请重新载入后再保存")


def next_revision(current):
    if current >= MAX_REVISION:
        raise HTTPException(409, "课件版本已达上限，请新建备课项目")
    return current + 1


def build_prep_router(get_db, current_user, ppt_master, deepseek_key):
    router = APIRouter(prefix="/prep", tags=["AI 备课项目"])
    DB = Annotated[Session, Depends(get_db)]
    Teacher = Annotated[User, Depends(current_user)]

    def own_lesson(db, user_id, lesson_id):
        lesson = db.scalar(select(LessonUnit).where(LessonUnit.id == lesson_id, LessonUnit.user_id == user_id))
        if lesson is None:
            raise HTTPException(404, "找不到备课项目")
        return lesson

    def get_project(db, lesson_id):
        return db.scalar(select(CoursewareProject).where(CoursewareProject.lesson_id == lesson_id))

    def commit_lesson(db):
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "同一学期和年级已有同名备课项目") from exc

    def update_project(db, project_id, expected_revision, **fields):
        result = db.execute(
            update(CoursewareProject)
            .where(CoursewareProject.id == project_id, CoursewareProject.revision == expected_revision)
            .values(**fields)
        )
        if result.rowcount != 1:
            raise version_conflict()

    @router.get("/lessons", response_model=list[LessonView])
    def list_lessons(db: DB, user: Teacher):
        rows = db.execute(
            select(LessonUnit, CoursewareProject)
            .outerjoin(CoursewareProject, LessonUnit.id == CoursewareProject.lesson_id)
            .where(LessonUnit.user_id == user.id)
            .order_by(LessonUnit.id.desc())
        )
        return [lesson_view(lesson, project) for lesson, project in rows]

    @router.post("/lessons", response_model=LessonView, status_code=201)
    def create_lesson(payload: LessonFields, db: DB, user: Teacher):
        lesson = LessonUnit(user_id=user.id, **payload.model_dump())
        db.add(lesson)
        commit_lesson(db)
        return lesson_view(lesson, None)

    @router.patch("/lessons/{lesson_id}", response_model=LessonView)
    def change_lesson(lesson_id: LessonId, payload: LessonUpdate, db: DB, user: Teacher):
        lesson = own_lesson(db, user.id, lesson_id)
        for key, value in payload.model_dump(exclude_unset=True).items():
            setattr(lesson, key, value)
        commit_lesson(db)
        return lesson_view(lesson, get_project(db, lesson.id))

    @router.post("/lessons/{lesson_id}/equipment", response_model=EquipmentList)
    async def suggest_equipment(lesson_id: LessonId, db: DB, user: Teacher):
        materials = own_lesson(db, user.id, lesson_id).materials
        db.rollback()
        return await extract_equipment(deepseek_key, materials)

    @router.get("/links", response_model=list[LinkView])
    def list_links(db: DB, user: Teacher):
        links = db.scalars(
            select(PrepSlotLink).where(PrepSlotLink.user_id == user.id).order_by(PrepSlotLink.slot_key)
        )
        return [{"slotKey": link.slot_key, "lessonId": link.lesson_id} for link in links]

    @router.put("/links/{slot_key}", response_model=LinkView)
    def set_link(slot_key: SlotKey, payload: LinkChange, db: DB, user: Teacher):
        lesson_id = payload.lessonId
        where = (PrepSlotLink.user_id == user.id, PrepSlotLink.slot_key == slot_key)
        if lesson_id is None:
            db.execute(delete(PrepSlotLink).where(*where))
        else:
            own_lesson(db, user.id, lesson_id)
            link = db.scalar(select(PrepSlotLink).where(*where))
            if link is None:
                db.add(PrepSlotLink(user_id=user.id, slot_key=slot_key, lesson_id=lesson_id))
            else:
                link.lesson_id = lesson_id
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise HTTPException(409, "关联已更新，请刷新后重试") from exc
        return {"slotKey": slot_key, "lessonId": lesson_id}

    @router.post("/lessons/{lesson_id}/attach", response_model=DeckView)
    def attach_deck(lesson_id: LessonId, payload: DeckAttach, db: DB, user: Teacher):
        own_lesson(db, user.id, lesson_id)
        project = get_project(db, lesson_id)
        try:
            source = load_artifact_source(user.id, payload.artifactId)
        except ArtifactNotFound as exc:
            raise HTTPException(404, "找不到可编辑的课件源文件，请使用新生成的课件") from exc
        if project and project.artifact_id == payload.artifactId:
            return deck_view(user.id, project.slides_json, project.revision, project.artifact_id, project.slide_count)
        slide_count = len(source["slides"])
        fields = {"slides_json": source, "artifact_id": payload.artifactId, "slide_count": slide_count}
        if project:
            if payload.revision != project.revision:
                raise version_conflict()
            revision = next_revision(project.revision)
            update_project(db, project.id, project.revision, revision=revision, **fields)
        else:
            if payload.revision is not None:
                raise version_conflict()
            revision = 1
            db.add(CoursewareProject(lesson_id=lesson_id, revision=revision, **fields))
        try:
            db.commit()
        except IntegrityError as exc:
            db.rollback()
            raise version_conflict() from exc
        return deck_view(user.id, source, revision, payload.artifactId, slide_count)

    @router.get("/lessons/{lesson_id}/deck", response_model=DeckView)
    def read_deck(lesson_id: LessonId, db: DB, user: Teacher):
        own_lesson(db, user.id, lesson_id)
        project = get_project(db, lesson_id)
        if project is None:
            raise HTTPException(404, "该备课项目还没有生成课件")
        return deck_view(user.id, project.slides_json, project.revision, project.artifact_id, project.slide_count)

    @router.put("/lessons/{lesson_id}/deck", response_model=DeckView)
    def save_deck(lesson_id: LessonId, payload: DeckUpdate, db: DB, user: Teacher):
        own_lesson(db, user.id, lesson_id)
        project = get_project(db, lesson_id)
        if project is None:
            raise HTTPException(404, "该备课项目还没有生成课件")
        revision = next_revision(payload.revision)
        update_project(db, project.id, payload.revision, revision=revision)
        try:
            result = ppt_master.create(payload.deck, user.id, expected_pages=len(payload.deck["slides"]))
            source = load_artifact_source(user.id, result.artifact_id)
        except (DeckSpecError, MediaUnavailable, SkillUnavailable) as exc:
            db.rollback()
            raise HTTPException(422, str(exc)) from exc
        except (ArtifactNotFound, OSError) as exc:
            db.rollback()
            raise HTTPException(503, "课件导出未完成，请稍后重试") from exc
        db.execute(
            update(CoursewareProject)
            .where(CoursewareProject.id == project.id)
            .values(slides_json=source, artifact_id=result.artifact_id, slide_count=result.slide_count)
        )
        db.commit()
        return deck_view(user.id, source, revision, result.artifact_id, result.slide_count)

    @router.post("/lessons/{lesson_id}/deck/slides/{page}/ai-edit", response_model=SlideSuggestion)
    async def suggest_page_edit(lesson_id: LessonId, page: Annotated[int, Path(ge=1, le=MAX_SLIDES)],
                                payload: SlideAiEdit, db: DB, user: Teacher):
        own_lesson(db, user.id, lesson_id)
        project = get_project(db, lesson_id)
        if project is None or page > len(project.slides_json["slides"]):
            raise HTTPException(404, "没有找到可改写的课件页面")
        if project.revision != payload.revision:
            raise version_conflict()
        project_id, revision, deck = project.id, project.revision, project.slides_json
        db.rollback()
        suggestion = await suggest_slide(deepseek_key, deck, page, payload.instruction)
        current = get_project(db, lesson_id)
        if current is None or current.id != project_id or current.revision != revision:
            raise version_conflict()
        return {"page": page, "revision": revision, "slide": suggestion}

    return router
