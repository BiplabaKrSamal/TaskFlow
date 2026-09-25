import uuid

from pydantic import BaseModel

from app.models import TaskStatus
from app.schemas.activity import ActivityOut


class BusiestProject(BaseModel):
    id: uuid.UUID
    name: str
    open_tasks: int


class DashboardOut(BaseModel):
    project_count: int
    assigned: dict[TaskStatus, int]  # tasks assigned to me, by status
    completed_this_week: int
    busiest_project: BusiestProject | None
    recent_activity: list[ActivityOut]
