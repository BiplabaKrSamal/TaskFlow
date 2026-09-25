import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, field_validator

from app.clock import today_utc
from app.models import Priority, TaskStatus
from app.schemas.common import ORM, ProjectRef, UserRef


def _clean_title(value: str) -> str:
    value = value.strip()
    if not value:
        raise ValueError("Title cannot be empty")
    if len(value) > 200:
        raise ValueError("Title must be 200 characters or fewer")
    return value


def _clean_description(value: str) -> str:
    value = value.strip()
    if len(value) > 5000:
        raise ValueError("Description must be 5000 characters or fewer")
    return value


class TaskCreate(BaseModel):
    title: str
    description: str = ""
    status: TaskStatus = TaskStatus.todo
    priority: Priority = Priority.medium
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None

    @field_validator("title")
    @classmethod
    def _title(cls, value: str) -> str:
        return _clean_title(value)

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        return _clean_description(value)

    @field_validator("due_date")
    @classmethod
    def _not_in_the_past(cls, value: date | None) -> date | None:
        if value is not None and value < today_utc():
            raise ValueError("Due date cannot be in the past")
        return value


class TaskUpdate(BaseModel):
    """Only the fields that are sent change. An explicit null clears due_date or assignee_id."""

    model_config = ConfigDict(extra="forbid")

    title: str | None = None
    description: str | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None
    assignee_id: uuid.UUID | None = None

    @field_validator("title", "description", "status", "priority", mode="before")
    @classmethod
    def _cannot_be_null(cls, value, info):
        if value is None:
            raise ValueError(f"{info.field_name.capitalize()} cannot be empty")
        return value

    @field_validator("title")
    @classmethod
    def _title(cls, value: str | None) -> str | None:
        return _clean_title(value) if value is not None else value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str | None) -> str | None:
        return _clean_description(value) if value is not None else value


class TaskOut(ORM):
    id: uuid.UUID
    project: ProjectRef
    title: str
    description: str
    status: TaskStatus
    priority: Priority
    due_date: date | None
    assignee_id: uuid.UUID | None
    assignee: UserRef | None
    creator: UserRef
    completed_at: datetime | None
    created_at: datetime
    updated_at: datetime
    comment_count: int


class BoardOut(BaseModel):
    columns: dict[TaskStatus, list[TaskOut]]


class CommentIn(BaseModel):
    body: str

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Comment cannot be empty")
        if len(value) > 2000:
            raise ValueError("Comment must be 2000 characters or fewer")
        return value


class CommentOut(ORM):
    id: uuid.UUID
    task_id: uuid.UUID
    author: UserRef
    body: str
    created_at: datetime
