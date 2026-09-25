import uuid

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.access import Access
from app.models import Activity, ActivityType, ProjectMember
from app.realtime import Event
from app.schemas.activity import ActivityOut, ActivityPage
from app.schemas.common import ProjectRef, UserRef


def event(access: Access, type: str, meta: dict) -> Event:
    """The websocket message for something that just happened in this project."""
    return Event(
        access.project.id,
        {
            "type": type,
            "project_id": str(access.project.id),
            "project_name": access.project.name,
            "actor": {"id": str(access.user.id), "name": access.user.name},
            "meta": meta,
        },
    )


def add(
    db: Session,
    access: Access,
    type: ActivityType,
    meta: dict,
    *,
    task_id: uuid.UUID | None = None,
    subject_user_id: uuid.UUID | None = None,
) -> None:
    db.add(
        Activity(
            project_id=access.project.id,
            actor_id=access.user.id,
            type=type,
            task_id=task_id,
            subject_user_id=subject_user_id,
            meta=meta,
        )
    )


def log(
    db: Session,
    access: Access,
    type: ActivityType,
    meta: dict,
    *,
    task_id: uuid.UUID | None = None,
    subject_user_id: uuid.UUID | None = None,
) -> Event:
    """Write the history line and return the matching live event, in one go."""
    add(db, access, type, meta, task_id=task_id, subject_user_id=subject_user_id)
    return event(access, type.value, meta)


def to_out(activity: Activity, with_project: bool = False) -> ActivityOut:
    return ActivityOut(
        id=activity.id,
        type=activity.type,
        actor=UserRef.model_validate(activity.actor),
        meta=activity.meta,
        created_at=activity.created_at,
        project=ProjectRef.model_validate(activity.project) if with_project else None,
    )


def project_feed(db: Session, project_id: uuid.UUID, limit: int, before: int | None) -> ActivityPage:
    # Keyset pagination on the id: new events arriving at the top never shift older pages.
    stmt = select(Activity).where(Activity.project_id == project_id).order_by(Activity.id.desc()).limit(limit + 1)
    if before is not None:
        stmt = stmt.where(Activity.id < before)
    rows = list(db.scalars(stmt))
    more = len(rows) > limit
    rows = rows[:limit]
    return ActivityPage(items=[to_out(a) for a in rows], next_before=rows[-1].id if more else None)


def personal_feed(db: Session, user_id: uuid.UUID, limit: int) -> list[ActivityOut]:
    """What I did, plus what happened to me or to my tasks, across the projects I am still in."""
    stmt = (
        select(Activity)
        .join(
            ProjectMember,
            and_(ProjectMember.project_id == Activity.project_id, ProjectMember.user_id == user_id),
        )
        .where(or_(Activity.actor_id == user_id, Activity.subject_user_id == user_id))
        .order_by(Activity.id.desc())
        .limit(limit)
    )
    return [to_out(a, with_project=True) for a in db.scalars(stmt)]
