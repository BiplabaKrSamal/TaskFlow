import uuid
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Query, Response, status

from app.deps import AccessDep, DbDep, OwnerDep, UserDep
from app.realtime import hub
from app.schemas.activity import ActivityPage
from app.schemas.projects import InviteIn, MemberOut, ProjectDetail, ProjectIn, ProjectOut
from app.services import activity, projects

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[ProjectOut])
def list_projects(user: UserDep, db: DbDep):
    return projects.summaries(db, user.id)


@router.post("", status_code=status.HTTP_201_CREATED, response_model=ProjectOut)
def create_project(payload: ProjectIn, user: UserDep, db: DbDep, background: BackgroundTasks):
    project = projects.create_project(db, user, payload.name, payload.description)
    db.commit()
    background.add_task(hub.join, project.id, user.id)
    return projects.summaries(db, user.id, project.id)[0]


@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(access: AccessDep, db: DbDep):
    return projects.detail(db, access)


@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(access: OwnerDep, db: DbDep, background: BackgroundTasks):
    notice = projects.delete_project(db, access)
    project_id = access.project.id
    db.commit()
    background.add_task(hub.publish, [notice])
    background.add_task(hub.drop_project, project_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/{project_id}/members", status_code=status.HTTP_201_CREATED, response_model=MemberOut)
def invite_member(payload: InviteIn, access: OwnerDep, db: DbDep, background: BackgroundTasks):
    member, events = projects.invite_member(db, access, payload.email)
    user_id = member.user_id
    db.commit()
    # join first, so the invitee's own open tabs receive the "invited" event too
    background.add_task(hub.join, access.project.id, user_id)
    background.add_task(hub.publish, events)
    return MemberOut.model_validate(member)


@router.delete("/{project_id}/members/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def remove_member(user_id: uuid.UUID, access: OwnerDep, db: DbDep, background: BackgroundTasks):
    events = projects.remove_member(db, access, user_id)
    project_id = access.project.id
    db.commit()
    # evict first, so the removed person is not told about their own removal as a member event
    background.add_task(hub.evict, project_id, user_id)
    background.add_task(hub.publish, events)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/activity", response_model=ActivityPage)
def project_activity(
    access: AccessDep,
    db: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 30,
    before: Annotated[int | None, Query(ge=1)] = None,
):
    return activity.project_feed(db, access.project.id, limit, before)
