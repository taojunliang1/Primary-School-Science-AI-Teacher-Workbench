from datetime import date as CalendarDate, datetime

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Index, Integer, MetaData, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    })


class Record:
    id: Mapped[int] = mapped_column(primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class TeacherOwned:
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class User(Record, Base):
    __tablename__ = "users"
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    name: Mapped[str] = mapped_column(String(80))
    avatar: Mapped[str | None] = mapped_column(String(512))


class Todo(Record, TeacherOwned, Base):
    __tablename__ = "todos"
    __table_args__ = (
        Index("ix_todos_user_date", "user_id", "date"),
        UniqueConstraint("user_id", "legacy_key", name="uq_todos_user_legacy_key"),
        CheckConstraint("priority IN ('normal', 'high', 'low')", name="priority"),
    )
    content: Mapped[str] = mapped_column(String(80))
    priority: Mapped[str] = mapped_column(String(8), default="normal")
    done: Mapped[bool] = mapped_column(Boolean, default=False)
    date: Mapped[CalendarDate] = mapped_column(Date)
    legacy_key: Mapped[str | None] = mapped_column(String(128))


class Course(Record, TeacherOwned, Base):
    __tablename__ = "courses"
    day_of_week: Mapped[int] = mapped_column(Integer)
    period: Mapped[str] = mapped_column(String(32))
    class_name: Mapped[str] = mapped_column(String(80))
    course_name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="scheduled")


class AIGeneration(Record, TeacherOwned, Base):
    __tablename__ = "ai_generations"
    type: Mapped[str] = mapped_column(String(32))
    prompt: Mapped[str] = mapped_column(Text)
    result_url: Mapped[str | None] = mapped_column(String(512))
    status: Mapped[str] = mapped_column(String(20), default="pending")


class SchoolClass(Record, TeacherOwned, Base):
    __tablename__ = "classes"
    class_name: Mapped[str] = mapped_column(String(80))
    grade: Mapped[str] = mapped_column(String(24))
    student_count: Mapped[int] = mapped_column(Integer, default=0)


class Student(Record, Base):
    __tablename__ = "students"
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    group_name: Mapped[str | None] = mapped_column(String(80))


class ExperimentReport(Record, Base):
    __tablename__ = "experiment_reports"
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    class_id: Mapped[int] = mapped_column(ForeignKey("classes.id", ondelete="CASCADE"), index=True)
    experiment_name: Mapped[str] = mapped_column(String(120))
    report_url: Mapped[str] = mapped_column(String(512))
    ai_feedback: Mapped[str | None] = mapped_column(Text)
    score: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")


class StudentWork(Record, Base):
    __tablename__ = "student_works"
    student_id: Mapped[int] = mapped_column(ForeignKey("students.id", ondelete="CASCADE"), index=True)
    title: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text)
    image_url: Mapped[str | None] = mapped_column(String(512))
    award_level: Mapped[str | None] = mapped_column(String(40))
