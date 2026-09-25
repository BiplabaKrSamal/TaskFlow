import uuid

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from app.access import Access
from app.errors import AppError
from app.models import ActivityType, Project, ProjectMember, Role, Task, TaskStatus, User
from app.realtime import Event
from app.schemas.projects import ProjectDetail, ProjectOut
from app.services import activity


def create_project(db: Session, user: User, name: str, description: str) -> Project:
    project = Project(name=name, description=description, owner_id=user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=user.id, role=Role.owner))
    db.flush()
    return project


def summaries(db: Session, user_id: uuid.UUID, project_id: uuid.UUID | None = None) -> list[ProjectOut]:
    """The caller's projects with a role, headcount and open-task count, in one query."""
    members = (
        select(func.count())
        .select_from(ProjectMember)
        .where(ProjectMember.project_id == Project.id)
        .correlate(Project)
        .scalar_subquery()
    )
    open_tasks = (
        select(func.count())
        .select_from(Task)
        .where(Task.project_id == Project.id, Task.status != TaskStatus.done)
        .correlate(Project)
        .scalar_subquery()
    )
    stmt = (
        select(Project, ProjectMember.role, members, open_tasks)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(ProjectMember.user_id == user_id)
        .order_by(Project.created_at.desc(), Project.id)
    )
    if project_id is not None:
        stmt = stmt.where(Project.id == project_id)
    return [
        ProjectOut(
            id=p.id,
            name=p.name,
            description=p.description,
            role=role,
            member_count=member_count,
            open_task_count=open_count,
            created_at=p.created_at,
        )
        for p, role, member_count, open_count in db.execute(stmt)
    ]


def detail(db: Session, access: Access) -> ProjectDetail:
    members = db.scalars(
        select(ProjectMember)
        .where(ProjectMember.project_id == access.project.id)
        .order_by(ProjectMember.role, ProjectMember.joined_at)  # owner first, then by join date
    ).all()
    project = access.project
    return ProjectDetail.model_validate(
        {
            "id": project.id,
            "name": project.name,
            "description": project.description,
            "role": access.role,
            "created_at": project.created_at,
            "owner": project.owner,
            "members": members,
        },
        from_attributes=True,
    )


def member_project_ids(db: Session, user_id: uuid.UUID) -> list[uuid.UUID]:
    return list(db.scalars(select(ProjectMember.project_id).where(ProjectMember.user_id == user_id)))


def invite_member(db: Session, access: Access, email: str) -> tuple[ProjectMember, list[Event]]:
    invitee = db.scalar(select(User).where(User.email == email))
    if invitee is None:
        raise AppError(
            404,
            "user_not_found",
            "No registered user has that email. Ask them to sign up first.",
            fields={"email": "No registered user with this email"},
        )
    if db.get(ProjectMember, (access.project.id, invitee.id)) is not None:
        raise AppError(
            409,
            "already_member",
            "That person is already a member of this project",
            fields={"email": "Already a member"},
        )
    member = ProjectMember(project_id=access.project.id, user_id=invitee.id, role=Role.member)
    db.add(member)
    events = [
        activity.log(
            db,
            access,
            ActivityType.member_invited,
            {"member_id": str(invitee.id), "member_name": invitee.name},
            subject_user_id=invitee.id,
        )
    ]
    db.flush()
    return member, events


def remove_member(db: Session, access: Access, user_id: uuid.UUID) -> list[Event]:
    """Revoke a member's access. What they created stays; what was assigned to them is unassigned."""
    target = db.get(ProjectMember, (access.project.id, user_id))
    if target is None:
        raise AppError(404, "member_not_found", "That person is not a member of this project")
    if target.role == Role.owner:
        raise AppError(409, "cannot_remove_owner", "The project owner cannot be removed")

    assigned = db.scalars(select(Task).where(Task.project_id == access.project.id, Task.assignee_id == user_id)).all()
    for task in assigned:
        task.assignee = None
        activity.add(
            db,
            access,
            ActivityType.task_assigned,
            {
                "task_id": str(task.id),
                "task_title": task.title,
                "assignee_id": None,
                "assignee_name": None,
                "previous_assignee_id": str(user_id),
                "previous_assignee_name": target.user.name,
                "reason": "member_removed",
            },
            task_id=task.id,
        )
    db.flush()  # tasks must be unassigned before the membership row can go

    removed_name = target.user.name
    db.execute(delete(ProjectMember).where(ProjectMember.project_id == access.project.id, ProjectMember.user_id == user_id))
    return [
        activity.log(
            db,
            access,
            ActivityType.member_removed,
            {"member_id": str(user_id), "member_name": removed_name, "unassigned_tasks": len(assigned)},
            subject_user_id=user_id,
        )
    ]


def delete_project(db: Session, access: Access) -> Event:
    """One DELETE; the database cascades to members, tasks, comments and activity."""
    notice = activity.event(access, "project_deleted", {})
    db.execute(delete(Project).where(Project.id == access.project.id))
    return notice
