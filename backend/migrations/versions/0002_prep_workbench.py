"""Add teacher-scoped lessons, timetable links, and editable courseware."""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.mysql import VARCHAR


revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "lesson_units",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("grade", sa.String(24), nullable=False),
        sa.Column("semester", sa.String(40), nullable=False),
        sa.Column("title", sa.String(80), nullable=False),
        sa.Column("duration", sa.Integer(), nullable=False),
        sa.Column("objectives", sa.Text(), nullable=False),
        sa.Column("materials", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_lesson_units_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_lesson_units"),
        sa.UniqueConstraint("user_id", "grade", "semester", "title", name="uq_lesson_units_identity"),
    )
    op.create_index("ix_lesson_units_user_id", "lesson_units", ["user_id"])
    op.create_table(
        "prep_slot_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("slot_key", sa.String(260).with_variant(VARCHAR(260, charset="ascii", collation="ascii_bin"), "mysql"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_prep_slot_links_user_id_users", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["lesson_id"], ["lesson_units.id"], name="fk_prep_slot_links_lesson_id_lesson_units", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_prep_slot_links"),
        sa.UniqueConstraint("user_id", "slot_key", name="uq_prep_slot_links_slot"),
    )
    op.create_index("ix_prep_slot_links_user_id", "prep_slot_links", ["user_id"])
    op.create_index("ix_prep_slot_links_lesson_id", "prep_slot_links", ["lesson_id"])
    op.create_table(
        "courseware_projects",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("lesson_id", sa.Integer(), nullable=False),
        sa.Column("slides_json", sa.JSON(), nullable=False),
        sa.Column("artifact_id", sa.String(32), nullable=False),
        sa.Column("slide_count", sa.Integer(), nullable=False),
        sa.Column("revision", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["lesson_id"], ["lesson_units.id"], name="fk_courseware_projects_lesson_id_lesson_units", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_courseware_projects"),
        sa.UniqueConstraint("lesson_id", name="uq_courseware_projects_lesson"),
    )


def downgrade():
    op.drop_table("courseware_projects")
    op.drop_table("prep_slot_links")
    op.drop_table("lesson_units")
