"""initial workbench schema"""
from alembic import op
import sqlalchemy as sa


revision = '0001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'users',
        sa.Column('username', sa.String(length=64), nullable=False),
        sa.Column('password_hash', sa.String(length=255), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('avatar', sa.String(length=512), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_users')),
        sa.UniqueConstraint('username', name=op.f('uq_users_username')),
    )
    op.create_table(
        'ai_generations',
        sa.Column('type', sa.String(length=32), nullable=False),
        sa.Column('prompt', sa.Text(), nullable=False),
        sa.Column('result_url', sa.String(length=512), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_ai_generations_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_ai_generations')),
    )
    op.create_index(op.f('ix_ai_generations_user_id'), 'ai_generations', ['user_id'], unique=False)
    op.create_table(
        'classes',
        sa.Column('class_name', sa.String(length=80), nullable=False),
        sa.Column('grade', sa.String(length=24), nullable=False),
        sa.Column('student_count', sa.Integer(), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_classes_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_classes')),
    )
    op.create_index(op.f('ix_classes_user_id'), 'classes', ['user_id'], unique=False)
    op.create_table(
        'courses',
        sa.Column('day_of_week', sa.Integer(), nullable=False),
        sa.Column('period', sa.String(length=32), nullable=False),
        sa.Column('class_name', sa.String(length=80), nullable=False),
        sa.Column('course_name', sa.String(length=120), nullable=False),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_courses_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_courses')),
    )
    op.create_index(op.f('ix_courses_user_id'), 'courses', ['user_id'], unique=False)
    op.create_table(
        'todos',
        sa.Column('content', sa.String(length=80), nullable=False),
        sa.Column('priority', sa.String(length=8), nullable=False),
        sa.Column('done', sa.Boolean(), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('legacy_key', sa.String(length=128), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.CheckConstraint("priority IN ('normal', 'high', 'low')", name=op.f('ck_todos_priority')),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], name=op.f('fk_todos_user_id_users'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_todos')),
        sa.UniqueConstraint('user_id', 'legacy_key', name='uq_todos_user_legacy_key'),
    )
    op.create_index('ix_todos_user_date', 'todos', ['user_id', 'date'], unique=False)
    op.create_index(op.f('ix_todos_user_id'), 'todos', ['user_id'], unique=False)
    op.create_table(
        'students',
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('group_name', sa.String(length=80), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_students_class_id_classes'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_students')),
    )
    op.create_index(op.f('ix_students_class_id'), 'students', ['class_id'], unique=False)
    op.create_table(
        'experiment_reports',
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('class_id', sa.Integer(), nullable=False),
        sa.Column('experiment_name', sa.String(length=120), nullable=False),
        sa.Column('report_url', sa.String(length=512), nullable=False),
        sa.Column('ai_feedback', sa.Text(), nullable=True),
        sa.Column('score', sa.Integer(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['class_id'], ['classes.id'], name=op.f('fk_experiment_reports_class_id_classes'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_experiment_reports_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_experiment_reports')),
    )
    op.create_index(op.f('ix_experiment_reports_class_id'), 'experiment_reports', ['class_id'], unique=False)
    op.create_index(op.f('ix_experiment_reports_student_id'), 'experiment_reports', ['student_id'], unique=False)
    op.create_table(
        'student_works',
        sa.Column('student_id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=120), nullable=False),
        sa.Column('description', sa.Text(), nullable=False),
        sa.Column('image_url', sa.String(length=512), nullable=True),
        sa.Column('award_level', sa.String(length=40), nullable=True),
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['student_id'], ['students.id'], name=op.f('fk_student_works_student_id_students'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_student_works')),
    )
    op.create_index(op.f('ix_student_works_student_id'), 'student_works', ['student_id'], unique=False)


def downgrade():
    op.drop_table('student_works')
    op.drop_table('experiment_reports')
    op.drop_table('students')
    op.drop_table('todos')
    op.drop_table('courses')
    op.drop_table('classes')
    op.drop_table('ai_generations')
    op.drop_table('users')
