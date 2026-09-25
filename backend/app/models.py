import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    Uuid,
    func,
    select,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, column_property, mapped_column, relationship

from app.clock import utcnow


class Base(DeclarativeBase):
    pass


class Role(str, enum.Enum):
    owner = "owner"
    member = "member"


# Declaration order matters: Postgres sorts enums by it, which is what makes
# ORDER BY priority come out low < medium < high.
class TaskStatus(str, enum.Enum):
    todo = "todo"
    in_progress = "in_progress"
    done = "done"


class Priority(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"


class ActivityType(str, enum.Enum):
    task_created = "task_created"
    task_moved = "task_moved"
    task_assigned = "task_assigned"
    task_deleted = "task_deleted"
    member_invited = "member_invited"
    member_removed = "member_removed"
    comment_added = "comment_added"


def pg_enum(cls: type[enum.Enum], name: str) -> SAEnum:
    return SAEnum(cls, name=name, values_callable=lambda e: [m.value for m in e], create_type=False)


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(80))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Project(Base):
    __tablename__ = "projects"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(120))
    description: Mapped[str] = mapped_column(Text, default="")
    owner_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    owner: Mapped[User] = relationship(lazy="joined")


class ProjectMember(Base):
    """The many-to-many between users and projects, carrying the role."""

    __tablename__ = "project_members"
    __table_args__ = (Index("ix_project_members_user", "user_id"),)

    project_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    role: Mapped[Role] = mapped_column(pg_enum(Role, "project_role"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    user: Mapped[User] = relationship(lazy="joined")


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        # An assignee must be a member of the task's own project. The service layer
        # gives friendly errors; this makes the rule hold even under a race.
        ForeignKeyConstraint(
            ["project_id", "assignee_id"],
            ["project_members.project_id", "project_members.user_id"],
            name="fk_tasks_assignee_is_member",
        ),
        Index("ix_tasks_project_status", "project_id", "status"),
        Index("ix_tasks_assignee_status", "assignee_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[TaskStatus] = mapped_column(pg_enum(TaskStatus, "task_status"), default=TaskStatus.todo)
    priority: Mapped[Priority] = mapped_column(pg_enum(Priority, "task_priority"), default=Priority.medium)
    due_date: Mapped[date | None] = mapped_column(Date)
    # created by a user, not by a membership: removing a member never touches their tasks
    creator_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    assignee_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    project: Mapped[Project] = relationship(lazy="joined", innerjoin=True)
    creator: Mapped[User] = relationship(foreign_keys=[creator_id], lazy="joined")
    assignee: Mapped[User | None] = relationship(foreign_keys=[assignee_id], lazy="joined")


class Comment(Base):
    __tablename__ = "comments"
    __table_args__ = (Index("ix_comments_task_created", "task_id", "created_at"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    task_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    author_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    body: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    author: Mapped[User] = relationship(lazy="joined")


class Activity(Base):
    __tablename__ = "activity_log"
    __table_args__ = (
        Index("ix_activity_project_id", "project_id", "id"),
        Index("ix_activity_actor", "actor_id"),
        Index("ix_activity_subject", "subject_user_id"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"))
    actor_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id"))
    type: Mapped[ActivityType] = mapped_column(pg_enum(ActivityType, "activity_type"))
    # The user the event is about (assignee, invited or removed member), so it can
    # show up in that person's own feed.
    subject_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id"))
    # No foreign key on purpose: the history line outlives a deleted task.
    task_id: Mapped[uuid.UUID | None] = mapped_column(Uuid)
    meta: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)

    actor: Mapped[User] = relationship(foreign_keys=[actor_id], lazy="joined")
    project: Mapped[Project] = relationship(lazy="joined", innerjoin=True)


class RefreshToken(Base):
    """Opaque refresh tokens, stored only as a SHA-256 hash. A family is one login."""

    __tablename__ = "refresh_tokens"
    __table_args__ = (Index("ix_refresh_tokens_family", "family_id"),)

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[uuid.UUID] = mapped_column(Uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    rotated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


Task.comment_count = column_property(
    select(func.count(Comment.id)).where(Comment.task_id == Task.id).correlate_except(Comment).scalar_subquery()
)
