"""Demo data: three people, a shared project with work in every column, and a private one.

Idempotent, so it is safe to run on every start:  python -m app.seed
Everyone gets the password below.
"""
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import Access
from app.clock import today_utc
from app.db import SessionLocal
from app.models import Priority, Role, TaskStatus, User
from app.schemas.tasks import TaskCreate, TaskUpdate
from app.security import hash_password
from app.services import projects, tasks

PASSWORD = "Password123"
PEOPLE = [
    ("Alice Rao", "alice@taskflow.dev"),
    ("Bob Mehta", "bob@taskflow.dev"),
    ("Carol Nair", "carol@taskflow.dev"),
]


def _user(db: Session, name: str, email: str) -> User:
    user = User(name=name, email=email, password_hash=hash_password(PASSWORD))
    db.add(user)
    db.flush()
    return user


def seed(db: Session) -> bool:
    if db.scalar(select(User.id).where(User.email == PEOPLE[0][1])):
        return False

    alice, bob, carol = (_user(db, name, email) for name, email in PEOPLE)
    today = today_utc()

    relaunch = projects.create_project(
        db, alice, "Website relaunch", "Rebuild the marketing site ahead of the autumn launch."
    )
    owner = Access(alice, relaunch, Role.owner)
    projects.invite_member(db, owner, bob.email)
    member = Access(bob, relaunch, Role.member)

    def add(access: Access, title: str, **fields):
        task, _ = tasks.create_task(db, access, TaskCreate(title=title, **fields))
        return task

    def move(access: Access, task, status: TaskStatus):
        tasks.update_task(db, access, task, TaskUpdate(status=status))

    audit = add(
        owner,
        "Audit the current homepage",
        description="List what to keep, what to cut and what nobody clicks.",
        priority=Priority.high,
        assignee_id=alice.id,
    )
    move(owner, audit, TaskStatus.done)

    copy = add(
        owner,
        "Draft the new landing page copy",
        description="Hero, three proof points and a closing call to action.",
        priority=Priority.high,
        due_date=today + timedelta(days=3),
        assignee_id=bob.id,  # created by Alice, assigned to Bob
    )
    move(member, copy, TaskStatus.in_progress)
    tasks.add_comment(db, member, copy, "First pass is in the doc. Can we cut the hero down to one sentence?")
    tasks.add_comment(db, owner, copy, "Yes, one sentence. Keep the proof points as they are.")

    add(
        owner,
        "Fix the mobile nav overflow",
        priority=Priority.low,
        due_date=today + timedelta(days=5),
        assignee_id=bob.id,
    )
    add(
        owner,
        "Design the pricing page",
        priority=Priority.medium,
        due_date=today + timedelta(days=7),
        assignee_id=alice.id,
    )
    add(member, "Set up analytics events", description="Page views, sign-up clicks and pricing toggles.")

    sandbox = projects.create_project(db, carol, "Carol's sandbox", "Only Carol is in here.")
    add(Access(carol, sandbox, Role.owner), "Try the board out", priority=Priority.low)
    return True


def main() -> None:
    with SessionLocal() as db:
        created = seed(db)
        db.commit()
    if created:
        print(f"Seeded demo data. Sign in as any of {', '.join(e for _, e in PEOPLE)} with password {PASSWORD}.")
    else:
        print("Demo data already present, nothing to do.")


if __name__ == "__main__":
    main()
