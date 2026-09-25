"""initial schema

Revision ID: 0001
Revises:
"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001"
down_revision = None

ENUMS = {
    "project_role": ("owner", "member"),
    "task_status": ("todo", "in_progress", "done"),
    # declared low -> high on purpose: Postgres sorts enums by declaration order
    "task_priority": ("low", "medium", "high"),
    "activity_type": (
        "task_created",
        "task_moved",
        "task_assigned",
        "task_deleted",
        "member_invited",
        "member_removed",
        "comment_added",
    ),
}


def enum(name: str) -> postgresql.ENUM:
    return postgresql.ENUM(*ENUMS[name], name=name, create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for name, values in ENUMS.items():
        postgresql.ENUM(*values, name=name).create(bind, checkfirst=True)

    now = sa.text("now()")

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("email", sa.String(320), nullable=False, unique=True),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("owner_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )

    op.create_table(
        "project_members",
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role", enum("project_role"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_project_members_user", "project_members", ["user_id"])

    op.create_table(
        "tasks",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text, nullable=False, server_default=""),
        sa.Column("status", enum("task_status"), nullable=False, server_default="todo"),
        sa.Column("priority", enum("task_priority"), nullable=False, server_default="medium"),
        sa.Column("due_date", sa.Date),
        sa.Column("creator_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("assignee_id", sa.Uuid, sa.ForeignKey("users.id")),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
        sa.ForeignKeyConstraint(
            ["project_id", "assignee_id"],
            ["project_members.project_id", "project_members.user_id"],
            name="fk_tasks_assignee_is_member",
        ),
    )
    op.create_index("ix_tasks_project_status", "tasks", ["project_id", "status"])
    op.create_index("ix_tasks_assignee_status", "tasks", ["assignee_id", "status"])

    op.create_table(
        "comments",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("task_id", sa.Uuid, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("author_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("body", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_comments_task_created", "comments", ["task_id", "created_at"])

    op.create_table(
        "activity_log",
        sa.Column("id", sa.BigInteger, sa.Identity(), primary_key=True),
        sa.Column("project_id", sa.Uuid, sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("actor_id", sa.Uuid, sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", enum("activity_type"), nullable=False),
        sa.Column("subject_user_id", sa.Uuid, sa.ForeignKey("users.id")),
        sa.Column("task_id", sa.Uuid),
        sa.Column("meta", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_activity_project_id", "activity_log", ["project_id", "id"])
    op.create_index("ix_activity_actor", "activity_log", ["actor_id"])
    op.create_index("ix_activity_subject", "activity_log", ["subject_user_id"])

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid, primary_key=True),
        sa.Column("user_id", sa.Uuid, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("family_id", sa.Uuid, nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("rotated_at", sa.DateTime(timezone=True)),
        sa.Column("revoked_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=now),
    )
    op.create_index("ix_refresh_tokens_family", "refresh_tokens", ["family_id"])


def downgrade() -> None:
    for table in ("refresh_tokens", "activity_log", "comments", "tasks", "project_members", "projects", "users"):
        op.drop_table(table)
    bind = op.get_bind()
    for name in ENUMS:
        postgresql.ENUM(name=name).drop(bind, checkfirst=True)
