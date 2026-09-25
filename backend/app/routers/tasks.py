import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response, status

from app.deps import AccessDep, DbDep, TaskDep
from app.errors import AppError
from app.models import Priority, TaskStatus
from app.realtime import hub
from app.schemas.common import Page
from app.schemas.tasks import BoardOut, CommentIn, CommentOut, TaskCreate, TaskOut, TaskUpdate
from app.services import tasks
from app.services.tasks import Filters

router = APIRouter(prefix="/projects/{project_id}", tags=["tasks"])

PriorityQuery = Annotated[Priority | None, Query(description="Only tasks with this priority")]
AssigneeQuery = Annotated[str | None, Query(description="A member's user id, or 'unassigned'")]
SearchQuery = Annotated[str | None, Query(max_length=200, description="Case-insensitive match on the title")]


def _assignee(value: str | None) -> uuid.UUID | Literal["unassigned"] | None:
    if not value:
        return None
    if value == "unassigned":
        return "unassigned"
    try:
        return uuid.UUID(value)
    except ValueError:
        message = "Assignee must be a member's id or 'unassigned'"
        raise AppError(422, "validation_error", message, fields={"assignee": message}) from None


def board_filters(priority: PriorityQuery = None, assignee: AssigneeQuery = None, q: SearchQuery = None) -> Filters:
    return Filters(priority=priority, assignee=_assignee(assignee), q=(q or "").strip() or None)


def list_filters(
    status: Annotated[TaskStatus | None, Query(description="Only tasks in this column")] = None,
    priority: PriorityQuery = None,
    assignee: AssigneeQuery = None,
    q: SearchQuery = None,
) -> Filters:
    return Filters(status=status, priority=priority, assignee=_assignee(assignee), q=(q or "").strip() or None)


@router.get("/board", response_model=BoardOut)
def get_board(access: AccessDep, db: DbDep, filters: Annotated[Filters, Depends(board_filters)]):
    return tasks.board(db, access.project.id, filters)


@router.get("/tasks", response_model=Page[TaskOut])
def list_tasks(
    access: AccessDep,
    db: DbDep,
    filters: Annotated[Filters, Depends(list_filters)],
    sort: tasks.Sort = "created_at",
    order: tasks.Order = "desc",
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    return tasks.list_tasks(db, access.project.id, filters, sort, order, page, page_size)


@router.post("/tasks", status_code=status.HTTP_201_CREATED, response_model=TaskOut)
def create_task(payload: TaskCreate, access: AccessDep, db: DbDep, background: BackgroundTasks):
    task, events = tasks.create_task(db, access, payload)
    db.commit()
    background.add_task(hub.publish, events)
    return TaskOut.model_validate(task)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def get_task(task: TaskDep):
    return TaskOut.model_validate(task)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(payload: TaskUpdate, access: AccessDep, task: TaskDep, db: DbDep, background: BackgroundTasks):
    task, events = tasks.update_task(db, access, task, payload)
    db.commit()
    if events:
        background.add_task(hub.publish, events)
    return TaskOut.model_validate(task)


@router.delete("/tasks/{task_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_task(access: AccessDep, task: TaskDep, db: DbDep, background: BackgroundTasks):
    events = tasks.delete_task(db, access, task)
    db.commit()
    background.add_task(hub.publish, events)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/tasks/{task_id}/comments", response_model=list[CommentOut])
def list_comments(task: TaskDep, db: DbDep):
    return tasks.list_comments(db, task)


@router.post("/tasks/{task_id}/comments", status_code=status.HTTP_201_CREATED, response_model=CommentOut)
def add_comment(payload: CommentIn, access: AccessDep, task: TaskDep, db: DbDep, background: BackgroundTasks):
    comment, events = tasks.add_comment(db, access, task, payload.body)
    db.commit()
    background.add_task(hub.publish, events)
    return CommentOut.model_validate(comment)
