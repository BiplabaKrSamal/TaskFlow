import uuid
from datetime import datetime, time, timedelta, timezone

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from app.clock import today_utc
from app.models import Project, ProjectMember, Task, TaskStatus
from app.schemas.dashboard import BusiestProject, DashboardOut
from app.services import activity


def week_start() -> datetime:
    """Monday 00:00 UTC of the current week."""
    today = today_utc()
    return datetime.combine(today - timedelta(days=today.weekday()), time.min, tzinfo=timezone.utc)


def build(db: Session, user_id: uuid.UUID) -> DashboardOut:
    project_count = db.scalar(select(func.count()).select_from(ProjectMember).where(ProjectMember.user_id == user_id))

    by_status = dict(
        db.execute(select(Task.status, func.count()).where(Task.assignee_id == user_id).group_by(Task.status)).all()
    )

    completed = db.scalar(
        select(func.count())
        .select_from(Task)
        .where(Task.assignee_id == user_id, Task.status == TaskStatus.done, Task.completed_at >= week_start())
    )

    open_tasks = func.count(Task.id)
    busiest = db.execute(
        select(Project.id, Project.name, open_tasks.label("open_tasks"))
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .join(Task, and_(Task.project_id == Project.id, Task.status != TaskStatus.done))
        .where(ProjectMember.user_id == user_id)
        .group_by(Project.id, Project.name)
        .order_by(open_tasks.desc(), Project.name)
        .limit(1)
    ).first()

    return DashboardOut(
        project_count=project_count or 0,
        assigned={status: by_status.get(status, 0) for status in TaskStatus},
        completed_this_week=completed or 0,
        busiest_project=BusiestProject(id=busiest.id, name=busiest.name, open_tasks=busiest.open_tasks) if busiest else None,
        recent_activity=activity.personal_feed(db, user_id, limit=15),
    )
