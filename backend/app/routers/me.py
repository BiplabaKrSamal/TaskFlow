from typing import Annotated

from fastapi import APIRouter, Query

from app.deps import DbDep, UserDep
from app.models import TaskStatus
from app.schemas.common import Page
from app.schemas.dashboard import DashboardOut
from app.schemas.tasks import TaskOut
from app.services import dashboard, tasks

router = APIRouter(prefix="/me", tags=["me"])


@router.get("/tasks", response_model=Page[TaskOut])
def assigned_to_me(
    user: UserDep,
    db: DbDep,
    status: Annotated[TaskStatus | None, Query(description="Only tasks in this column")] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    """Everything assigned to the caller, across all of their projects."""
    return tasks.assigned_to(db, user.id, status, page, page_size)


@router.get("/dashboard", response_model=DashboardOut)
def my_dashboard(user: UserDep, db: DbDep):
    return dashboard.build(db, user.id)
