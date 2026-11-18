"""add optional weekly schedule fields to courses"""

from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("courses", sa.Column("course_type", sa.String(12), nullable=True))
    op.add_column("courses", sa.Column("important", sa.Boolean(), nullable=True))


def downgrade():
    op.drop_column("courses", "important")
    op.drop_column("courses", "course_type")
