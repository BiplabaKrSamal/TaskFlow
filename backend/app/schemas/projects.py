import uuid
from datetime import datetime

from pydantic import BaseModel, field_validator

from app.models import Role
from app.schemas.auth import UserOut
from app.schemas.common import ORM, Email, UserRef


class ProjectIn(BaseModel):
    name: str
    description: str = ""

    @field_validator("name")
    @classmethod
    def _name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Project name is required")
        if len(value) > 120:
            raise ValueError("Project name must be 120 characters or fewer")
        return value

    @field_validator("description")
    @classmethod
    def _description(cls, value: str) -> str:
        value = value.strip()
        if len(value) > 2000:
            raise ValueError("Description must be 2000 characters or fewer")
        return value


class ProjectOut(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    role: Role  # the caller's role in this project
    member_count: int
    open_task_count: int
    created_at: datetime


class MemberOut(ORM):
    user: UserOut
    role: Role
    joined_at: datetime


class ProjectDetail(BaseModel):
    id: uuid.UUID
    name: str
    description: str
    role: Role
    created_at: datetime
    owner: UserRef
    members: list[MemberOut]


class InviteIn(BaseModel):
    email: Email
