from sqlalchemy import func, select

from app.models import Project, ProjectMember, Task, User
from app.seed import PEOPLE, seed


def test_seeding_builds_the_demo_world_once(db):
    assert seed(db) is True
    db.commit()
    assert seed(db) is False  # safe to run on every start

    assert db.scalar(select(func.count()).select_from(User)) == len(PEOPLE)
    shared = db.scalar(select(Project).where(Project.name == "Website relaunch"))
    members = db.scalars(select(ProjectMember).where(ProjectMember.project_id == shared.id)).all()
    assert sorted(m.role.value for m in members) == ["member", "owner"]

    tasks = db.scalars(select(Task).where(Task.project_id == shared.id)).all()
    assert len(tasks) >= 4
    assert any(t.assignee_id and t.assignee_id != t.creator_id for t in tasks)  # assigned across users
    assert {t.status.value for t in tasks} == {"todo", "in_progress", "done"}
