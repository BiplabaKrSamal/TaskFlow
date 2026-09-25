import uuid
from typing import Annotated

from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access
from app.db import get_db
from app.errors import AppError
from app.models import Project, ProjectMember, Task, User
from app.security import BEARER, decode_access_token

DbDep = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)], db: DbDep
) -> User:
    if credentials is None:
        raise AppError(401, "not_authenticated", "Sign in to continue", headers=BEARER)
    claims = decode_access_token(credentials.credentials)
    user = db.get(User, claims.user_id)
    if user is None:
        raise AppError(401, "invalid_token", "Invalid authentication token", headers=BEARER)
    return user


UserDep = Annotated[User, Depends(current_user)]


def project_access(project_id: uuid.UUID, user: UserDep, db: DbDep) -> Access:
    """Membership is checked in the database on every request, so removal takes effect at once.

    A project you are not in answers 404, the same as one that does not exist.
    """
    row = db.execute(
        select(Project, ProjectMember.role)
        .join(ProjectMember, ProjectMember.project_id == Project.id)
        .where(Project.id == project_id, ProjectMember.user_id == user.id)
    ).first()
    if row is None:
        raise AppError(404, "project_not_found", "Project not found")
    return Access(user=user, project=row[0], role=row[1])


AccessDep = Annotated[Access, Depends(project_access)]


def owner_access(access: AccessDep) -> Access:
    if not access.is_owner:
        raise AppError(403, "owner_only", "Only the project owner can do this")
    return access


OwnerDep = Annotated[Access, Depends(owner_access)]


def task_of(task_id: uuid.UUID, access: AccessDep, db: DbDep) -> Task:
    """Looked up inside the project from the URL, so a task id from another project is a 404."""
    task = db.scalar(select(Task).where(Task.id == task_id, Task.project_id == access.project.id))
    if task is None:
        raise AppError(404, "task_not_found", "Task not found")
    return task


TaskDep = Annotated[Task, Depends(task_of)]
