import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.access import Access
from app.clock import today_utc, utcnow
from app.errors import AppError
from app.models import ActivityType, Comment, Priority, ProjectMember, Task, TaskStatus, User
from app.realtime import Event
from app.schemas.common import Page
from app.schemas.tasks import BoardOut, TaskCreate, TaskOut, TaskUpdate
from app.services import activity

DONE_DENIED = "Only the assignee or the project owner can mark a task as Done"
NOT_A_MEMBER = "Assignee must be a member of this project"

Sort = Literal["priority", "due_date", "created_at"]
Order = Literal["asc", "desc"]


@dataclass
class Filters:
    status: TaskStatus | None = None
    priority: Priority | None = None
    assignee: uuid.UUID | Literal["unassigned"] | None = None
    q: str | None = None


def _like(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _apply(stmt, filters: Filters):
    """The same filters drive the count, the page and the board, so they can never disagree."""
    if filters.status is not None:
        stmt = stmt.where(Task.status == filters.status)
    if filters.priority is not None:
        stmt = stmt.where(Task.priority == filters.priority)
    if filters.assignee == "unassigned":
        stmt = stmt.where(Task.assignee_id.is_(None))
    elif filters.assignee is not None:
        stmt = stmt.where(Task.assignee_id == filters.assignee)
    if filters.q:
        stmt = stmt.where(Task.title.ilike(_like(filters.q), escape="\\"))
    return stmt


def _ordering(sort: Sort, order: Order) -> list:
    descending = order == "desc"
    if sort == "priority":  # a Postgres enum, so this sorts low < medium < high
        primary = Task.priority.desc() if descending else Task.priority.asc()
    elif sort == "due_date":  # tasks without a due date always go last
        primary = Task.due_date.desc().nulls_last() if descending else Task.due_date.asc().nulls_last()
    else:
        primary = Task.created_at.desc() if descending else Task.created_at.asc()
    # id as the final tie-break keeps pages stable when the sort key repeats
    return [primary, Task.created_at.desc(), Task.id]


def list_tasks(
    db: Session, project_id: uuid.UUID, filters: Filters, sort: Sort, order: Order, page: int, page_size: int
) -> Page[TaskOut]:
    scope = Task.project_id == project_id
    total = db.scalar(_apply(select(func.count(Task.id)).where(scope), filters)) or 0
    rows = db.scalars(
        _apply(select(Task).where(scope), filters)
        .order_by(*_ordering(sort, order))
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return Page[TaskOut](
        items=[TaskOut.model_validate(t) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, -(-total // page_size)),
    )


def board(db: Session, project_id: uuid.UUID, filters: Filters) -> BoardOut:
    rows = db.scalars(
        _apply(select(Task).where(Task.project_id == project_id), filters).order_by(
            Task.priority.desc(), Task.due_date.asc().nulls_last(), Task.created_at, Task.id
        )
    )
    columns: dict[TaskStatus, list[TaskOut]] = {status: [] for status in TaskStatus}
    for task in rows:
        columns[task.status].append(TaskOut.model_validate(task))
    return BoardOut(columns=columns)


def assigned_to(
    db: Session, user_id: uuid.UUID, status: TaskStatus | None, page: int, page_size: int
) -> Page[TaskOut]:
    filters = Filters(status=status)
    scope = Task.assignee_id == user_id
    total = db.scalar(_apply(select(func.count(Task.id)).where(scope), filters)) or 0
    rows = db.scalars(
        _apply(select(Task).where(scope), filters)
        .order_by(
            case((Task.status == TaskStatus.done, 1), else_=0),  # open work first
            Task.due_date.asc().nulls_last(),
            Task.priority.desc(),
            Task.created_at,
            Task.id,
        )
        .limit(page_size)
        .offset((page - 1) * page_size)
    )
    return Page[TaskOut](
        items=[TaskOut.model_validate(t) for t in rows],
        total=total,
        page=page,
        page_size=page_size,
        pages=max(1, -(-total // page_size)),
    )


def resolve_assignee(db: Session, project_id: uuid.UUID, assignee_id: uuid.UUID | None) -> User | None:
    if assignee_id is None:
        return None
    user = db.scalar(
        select(User)
        .join(ProjectMember, ProjectMember.user_id == User.id)
        .where(ProjectMember.project_id == project_id, User.id == assignee_id)
    )
    if user is None:
        raise AppError(422, "assignee_not_member", NOT_A_MEMBER, fields={"assignee_id": NOT_A_MEMBER})
    return user


def _meta(task: Task, **extra) -> dict:
    return {"task_id": str(task.id), "task_title": task.title, **extra}


def _assignment_meta(task: Task, previous: User | None, current: User | None) -> dict:
    return _meta(
        task,
        assignee_id=str(current.id) if current else None,
        assignee_name=current.name if current else None,
        previous_assignee_id=str(previous.id) if previous else None,
        previous_assignee_name=previous.name if previous else None,
    )


def _deny_done() -> AppError:
    return AppError(403, "not_allowed_to_complete", DONE_DENIED, fields={"status": DONE_DENIED})


def create_task(db: Session, access: Access, data: TaskCreate) -> tuple[Task, list[Event]]:
    assignee = resolve_assignee(db, access.project.id, data.assignee_id)
    finished = data.status == TaskStatus.done
    if finished and not (access.is_owner or (assignee is not None and assignee.id == access.user.id)):
        raise _deny_done()

    task = Task(
        project_id=access.project.id,
        title=data.title,
        description=data.description,
        status=data.status,
        priority=data.priority,
        due_date=data.due_date,
        completed_at=utcnow() if finished else None,
        creator=access.user,
        assignee=assignee,
    )
    db.add(task)
    db.flush()

    subject = assignee.id if assignee else None
    events = [activity.log(db, access, ActivityType.task_created, _meta(task), task_id=task.id, subject_user_id=subject)]
    if assignee is not None:
        events.append(
            activity.log(
                db,
                access,
                ActivityType.task_assigned,
                _assignment_meta(task, None, assignee),
                task_id=task.id,
                subject_user_id=assignee.id,
            )
        )
    return task, events


def update_task(db: Session, access: Access, task: Task, data: TaskUpdate) -> tuple[Task, list[Event]]:
    changes = data.model_dump(exclude_unset=True)
    previous = task.assignee

    # Validate everything first, then change anything, so a rejected request changes nothing.
    new_assignee = previous
    if "assignee_id" in changes:
        new_assignee = resolve_assignee(db, access.project.id, changes["assignee_id"])

    new_status = changes.get("status", task.status)
    if new_status == TaskStatus.done and task.status != TaskStatus.done:
        # judged against who the task belonged to when the request arrived
        if not (access.is_owner or task.assignee_id == access.user.id):
            raise _deny_done()

    new_due = changes.get("due_date", task.due_date)
    if new_due is not None and new_due != task.due_date and new_due < today_utc():
        # an existing overdue date can stay; moving a date into the past is what is refused
        raise AppError(
            422, "due_date_in_past", "Due date cannot be in the past", fields={"due_date": "Due date cannot be in the past"}
        )

    edited = [
        name
        for name in ("title", "description", "priority", "due_date")
        if name in changes and changes[name] != getattr(task, name)
    ]
    for name in edited:
        setattr(task, name, changes[name])

    old_status = task.status
    moved = new_status != old_status
    if moved:
        task.status = new_status
        task.completed_at = utcnow() if new_status == TaskStatus.done else None

    reassigned = (new_assignee.id if new_assignee else None) != task.assignee_id
    if reassigned:
        task.assignee = new_assignee

    db.flush()

    events: list[Event] = []
    if edited:
        events.append(activity.event(access, "task_updated", _meta(task, fields=edited)))
    if moved:
        events.append(
            activity.log(
                db,
                access,
                ActivityType.task_moved,
                _meta(task, from_status=old_status.value, to_status=new_status.value),
                task_id=task.id,
                subject_user_id=task.assignee_id,
            )
        )
    if reassigned:
        events.append(
            activity.log(
                db,
                access,
                ActivityType.task_assigned,
                _assignment_meta(task, previous, new_assignee),
                task_id=task.id,
                subject_user_id=new_assignee.id if new_assignee else None,
            )
        )
    return task, events


def delete_task(db: Session, access: Access, task: Task) -> list[Event]:
    events = [
        activity.log(
            db, access, ActivityType.task_deleted, _meta(task), task_id=task.id, subject_user_id=task.assignee_id
        )
    ]
    db.delete(task)  # its comments go with it via ON DELETE CASCADE
    return events


def list_comments(db: Session, task: Task) -> list[Comment]:
    return list(db.scalars(select(Comment).where(Comment.task_id == task.id).order_by(Comment.created_at, Comment.id)))


def add_comment(db: Session, access: Access, task: Task, body: str) -> tuple[Comment, list[Event]]:
    comment = Comment(task_id=task.id, author=access.user, body=body)
    db.add(comment)
    db.flush()
    events = [
        activity.log(
            db,
            access,
            ActivityType.comment_added,
            _meta(task, comment_id=str(comment.id)),
            task_id=task.id,
            subject_user_id=task.assignee_id,
        )
    ]
    return comment, events
