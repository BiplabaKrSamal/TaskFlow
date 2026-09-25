from datetime import datetime

from pydantic import BaseModel

from app.models import ActivityType
from app.schemas.common import ProjectRef, UserRef


class ActivityOut(BaseModel):
    id: int
    type: ActivityType
    actor: UserRef
    meta: dict
    created_at: datetime
    project: ProjectRef | None = None  # only filled in the cross-project (personal) feed


class ActivityPage(BaseModel):
    items: list[ActivityOut]
    next_before: int | None  # pass as ?before= to get the next, older page
