import uuid
from datetime import timedelta

import pytest
from sqlalchemy import func, select, update
from sqlalchemy.exc import IntegrityError

from app.clock import today_utc, utcnow
from app.models import Activity, Comment, Project, ProjectMember, Task


def project_with(owner, *members, name="Launch") -> str:
    pid = owner.post("/projects", json={"name": name}).json()["id"]
    for member in members:
        assert owner.post(f"/projects/{pid}/members", json={"email": member.email}).status_code == 201
    return pid


def add_task(person, pid, **fields) -> dict:
    response = person.post(f"/projects/{pid}/tasks", json={"title": "Write docs", **fields})
    assert response.status_code == 201, response.text
    return response.json()


def url(pid, task) -> str:
    return f"/projects/{pid}/tasks/{task['id']}"


def titles(page_or_list) -> list[str]:
    items = page_or_list["items"] if isinstance(page_or_list, dict) else page_or_list
    return [t["title"] for t in items]


# ---------------------------------------------------------------- creating


def test_a_task_gets_sensible_defaults(alice):
    pid = project_with(alice)
    task = add_task(alice, pid, title="  Ship it  ")
    assert task["title"] == "Ship it"
    assert (task["status"], task["priority"]) == ("todo", "medium")
    assert task["assignee"] is None and task["due_date"] is None and task["completed_at"] is None
    assert task["creator"]["name"] == "Alice" and task["comment_count"] == 0
    assert task["project"]["id"] == pid


@pytest.mark.parametrize(
    ("body", "field", "message"),
    [
        ({}, "title", "This field is required"),
        ({"title": ""}, "title", "Title cannot be empty"),
        ({"title": "   "}, "title", "Title cannot be empty"),
        ({"title": "x" * 201}, "title", "200 characters"),
        ({"title": "ok", "due_date": str(today_utc() - timedelta(days=1))}, "due_date", "cannot be in the past"),
        ({"title": "ok", "due_date": "next tuesday"}, "due_date", "date"),
        ({"title": "ok", "priority": "urgent"}, "priority", "Input should be"),
        ({"title": "ok", "status": "blocked"}, "status", "Input should be"),
    ],
)
def test_invalid_tasks_are_rejected_with_a_clear_field_error(alice, body, field, message):
    pid = project_with(alice)
    response = alice.post(f"/projects/{pid}/tasks", json=body)
    assert response.status_code == 422
    assert message in response.json()["fields"][field]


def test_due_today_is_fine_but_yesterday_is_not(alice):
    pid = project_with(alice)
    assert add_task(alice, pid, due_date=str(today_utc()))["due_date"] == str(today_utc())


def test_only_members_can_be_assigned(alice, bob, carol):
    pid = project_with(alice, bob)
    assert add_task(alice, pid, assignee_id=bob.id)["assignee"]["name"] == "Bob"
    response = alice.post(f"/projects/{pid}/tasks", json={"title": "x", "assignee_id": carol.id})
    assert response.status_code == 422
    assert response.json()["code"] == "assignee_not_member"
    assert "assignee_id" in response.json()["fields"]


def test_the_database_itself_refuses_a_non_member_assignee(alice, carol, db):
    pid = project_with(alice)
    task = add_task(alice, pid)
    with pytest.raises(IntegrityError):
        db.execute(update(Task).where(Task.id == uuid.UUID(task["id"])).values(assignee_id=uuid.UUID(carol.id)))
        db.commit()


# ---------------------------------------------------------------- access


def test_non_members_cannot_touch_a_projects_tasks(client, alice, carol):
    pid = project_with(alice)
    task = add_task(alice, pid)
    attempts = [
        ("get", f"/projects/{pid}/tasks", {}),
        ("get", f"/projects/{pid}/board", {}),
        ("post", f"/projects/{pid}/tasks", {"json": {"title": "x"}}),
        ("get", url(pid, task), {}),
        ("patch", url(pid, task), {"json": {"title": "hacked"}}),
        ("delete", url(pid, task), {}),
        ("get", f"{url(pid, task)}/comments", {}),
        ("post", f"{url(pid, task)}/comments", {"json": {"body": "hi"}}),
    ]
    for method, path, kwargs in attempts:
        assert getattr(carol, method)(path, **kwargs).status_code == 404, (method, path)
    assert client.get(f"/api/projects/{pid}/tasks").status_code == 401
    assert alice.get(url(pid, task)).json()["title"] == "Write docs"


def test_a_task_id_from_another_project_is_not_reachable(alice, bob):
    open_project = project_with(alice, bob, name="Open")
    private = project_with(alice, name="Private")
    secret = add_task(alice, private, title="secret")
    assert alice.get(url(open_project, secret)).status_code == 404  # right person, wrong project
    assert bob.get(url(private, secret)).status_code == 404  # right project, not a member
    assert bob.patch(url(open_project, secret), json={"title": "x"}).status_code == 404


# ---------------------------------------------------------------- editing


def test_patch_changes_only_what_is_sent(alice):
    pid = project_with(alice)
    task = add_task(alice, pid, title="Original", description="Keep me", priority="high", due_date=str(today_utc()))
    changed = alice.patch(url(pid, task), json={"title": "Renamed"}).json()
    assert (changed["title"], changed["description"], changed["priority"]) == ("Renamed", "Keep me", "high")
    assert changed["due_date"] == str(today_utc())

    cleared = alice.patch(url(pid, task), json={"due_date": None}).json()
    assert cleared["due_date"] is None and cleared["title"] == "Renamed"


def test_patch_rejects_nulls_and_unknown_fields(alice):
    pid = project_with(alice)
    task = add_task(alice, pid)
    assert alice.patch(url(pid, task), json={"title": None}).status_code == 422
    assert alice.patch(url(pid, task), json={"title": "  "}).json()["fields"]["title"] == "Title cannot be empty"
    assert alice.patch(url(pid, task), json={"colour": "red"}).status_code == 422


def test_an_existing_overdue_date_can_stay_but_cannot_be_moved_into_the_past(alice, db):
    pid = project_with(alice)
    task = add_task(alice, pid, due_date=str(today_utc() + timedelta(days=3)))
    yesterday = today_utc() - timedelta(days=1)
    db.execute(update(Task).where(Task.id == uuid.UUID(task["id"])).values(due_date=yesterday))
    db.commit()

    assert alice.patch(url(pid, task), json={"title": "still fine"}).status_code == 200
    assert alice.patch(url(pid, task), json={"due_date": str(yesterday)}).status_code == 200
    refused = alice.patch(url(pid, task), json={"due_date": str(today_utc() - timedelta(days=5))})
    assert refused.status_code == 422 and refused.json()["code"] == "due_date_in_past"


def test_deleting_a_task_removes_it_and_its_comments(alice, db):
    pid = project_with(alice)
    task = add_task(alice, pid)
    alice.post(f"{url(pid, task)}/comments", json={"body": "note"})
    assert alice.delete(url(pid, task)).status_code == 204
    assert alice.get(url(pid, task)).status_code == 404
    assert db.scalar(select(func.count()).select_from(Comment)) == 0


# ---------------------------------------------------------------- status rules


def test_completed_at_is_recorded_on_done_and_cleared_when_it_moves_back(alice):
    pid = project_with(alice)
    task = add_task(alice, pid)
    started = alice.patch(url(pid, task), json={"status": "in_progress"}).json()
    assert started["status"] == "in_progress" and started["completed_at"] is None

    done = alice.patch(url(pid, task), json={"status": "done"}).json()
    assert done["status"] == "done" and done["completed_at"] is not None

    reopened = alice.patch(url(pid, task), json={"status": "in_progress"}).json()
    assert reopened["completed_at"] is None


def test_only_the_assignee_or_the_owner_can_mark_a_task_done(alice, bob, carol):
    pid = project_with(alice, bob, carol)
    task = add_task(alice, pid, assignee_id=bob.id)

    denied = carol.patch(url(pid, task), json={"status": "done"})
    assert denied.status_code == 403
    assert denied.json()["code"] == "not_allowed_to_complete"
    assert "assignee or the project owner" in denied.json()["detail"]
    assert alice.get(url(pid, task)).json()["status"] == "todo"

    # anyone can move it along, only "Done" is protected
    assert carol.patch(url(pid, task), json={"status": "in_progress"}).status_code == 200

    assert bob.patch(url(pid, task), json={"status": "done"}).status_code == 200  # the assignee
    assert alice.patch(url(pid, task), json={"status": "in_progress"}).status_code == 200
    assert alice.patch(url(pid, task), json={"status": "done"}).status_code == 200  # the owner


def test_a_task_with_no_assignee_can_only_be_finished_by_the_owner(alice, bob):
    pid = project_with(alice, bob)
    task = add_task(alice, pid)
    assert bob.patch(url(pid, task), json={"status": "done"}).status_code == 403
    assert alice.patch(url(pid, task), json={"status": "done"}).status_code == 200


def test_a_rejected_edit_changes_nothing_and_the_rule_holds_at_creation_too(alice, bob):
    pid = project_with(alice, bob)
    task = add_task(alice, pid)
    refused = bob.patch(url(pid, task), json={"title": "Sneaky", "status": "done"})
    assert refused.status_code == 403
    assert alice.get(url(pid, task)).json()["title"] == "Write docs"

    assert bob.post(f"/projects/{pid}/tasks", json={"title": "x", "status": "done"}).status_code == 403
    own = bob.post(f"/projects/{pid}/tasks", json={"title": "x", "status": "done", "assignee_id": bob.id})
    assert own.status_code == 201 and own.json()["completed_at"] is not None


# ---------------------------------------------------------------- assignment


def test_assigned_to_me_spans_projects(alice, bob):
    one = project_with(alice, bob, name="One")
    two = project_with(alice, bob, name="Two")
    private = project_with(alice, name="Alice only")
    add_task(alice, one, title="A", assignee_id=bob.id)
    add_task(alice, two, title="B", assignee_id=bob.id)
    add_task(alice, one, title="not bob's")
    add_task(alice, private, title="private")

    mine = bob.get("/me/tasks").json()
    assert sorted(titles(mine)) == ["A", "B"] and mine["total"] == 2
    assert {t["project"]["name"] for t in mine["items"]} == {"One", "Two"}
    assert titles(alice.get("/me/tasks").json()) == []

    moved = alice.patch(url(one, mine["items"][0] if mine["items"][0]["title"] == "A" else mine["items"][1]),
                        json={"assignee_id": None})
    assert moved.json()["assignee"] is None
    assert titles(bob.get("/me/tasks").json()) == ["B"]


def test_removing_a_member_keeps_what_they_made_and_unassigns_what_they_held(alice, bob):
    pid = project_with(alice, bob)
    add_task(bob, pid, title="Bob made this")
    held = add_task(alice, pid, title="For Bob", assignee_id=bob.id)
    assert alice.delete(f"/projects/{pid}/members/{bob.id}").status_code == 204

    board = {t["title"]: t for t in alice.get(f"/projects/{pid}/board").json()["columns"]["todo"]}
    assert set(board) == {"Bob made this", "For Bob"}
    assert board["Bob made this"]["creator"]["name"] == "Bob"
    assert board["For Bob"]["assignee"] is None

    again = alice.patch(url(pid, held), json={"assignee_id": bob.id})
    assert again.status_code == 422 and again.json()["code"] == "assignee_not_member"

    feed = alice.get(f"/projects/{pid}/activity").json()["items"]
    unassigned = [i for i in feed if i["type"] == "task_assigned" and i["meta"].get("reason") == "member_removed"]
    assert len(unassigned) == 1 and unassigned[0]["meta"]["previous_assignee_name"] == "Bob"


# ---------------------------------------------------------------- filters, paging, sorting


@pytest.fixture()
def filter_project(alice, bob):
    pid = project_with(alice, bob)
    add_task(alice, pid, title="Fix login bug", priority="high", assignee_id=bob.id)
    add_task(alice, pid, title="Fix signup bug", priority="low", assignee_id=bob.id)
    add_task(alice, pid, title="Write docs", priority="high", assignee_id=alice.id)
    add_task(alice, pid, title="Polish 100% UI_kit", priority="medium")
    return pid


def test_assignee_and_priority_filters_apply_together(alice, bob, filter_project):
    pid = filter_project

    def found(**params):
        return titles(alice.get(f"/projects/{pid}/tasks", params=params).json())

    assert found(assignee=bob.id, priority="high") == ["Fix login bug"]
    assert found(assignee=bob.id, priority="high", q="signup") == []
    assert sorted(found(assignee=bob.id)) == ["Fix login bug", "Fix signup bug"]
    assert sorted(found(priority="high")) == ["Fix login bug", "Write docs"]
    assert found(assignee="unassigned") == ["Polish 100% UI_kit"]


def test_a_bad_assignee_filter_is_a_validation_error(alice, filter_project):
    response = alice.get(f"/projects/{filter_project}/tasks", params={"assignee": "not-a-uuid-or-unassigned"})
    assert response.status_code == 422 and "assignee" in response.json()["fields"]


def test_title_search_is_case_insensitive_and_treats_wildcards_literally(alice, filter_project):
    def found(q):
        return titles(alice.get(f"/projects/{filter_project}/tasks", params={"q": q}).json())

    assert sorted(found("FIX")) == ["Fix login bug", "Fix signup bug"]
    assert found("100%") == ["Polish 100% UI_kit"]
    assert found("%") == ["Polish 100% UI_kit"]  # not "match everything"
    assert found("_") == ["Polish 100% UI_kit"]
    assert found("   ") != []  # blank search means no search


def test_status_filter_on_the_list(alice, bob, filter_project):
    task = alice.get(f"/projects/{filter_project}/tasks", params={"q": "docs"}).json()["items"][0]
    alice.patch(url(filter_project, task), json={"status": "done"})
    done = alice.get(f"/projects/{filter_project}/tasks", params={"status": "done"}).json()
    assert titles(done) == ["Write docs"] and done["total"] == 1


def test_pagination_is_done_by_the_database(alice):
    pid = project_with(alice)
    for i in range(25):
        add_task(alice, pid, title=f"Task {i:02d}")

    def page(n, size=10):
        return alice.get(
            f"/projects/{pid}/tasks", params={"page": n, "page_size": size, "sort": "created_at", "order": "asc"}
        ).json()

    first, last = page(1), page(3)
    assert (first["total"], first["pages"], first["page"], first["page_size"]) == (25, 3, 1, 10)
    assert titles(first)[0] == "Task 00" and len(first["items"]) == 10
    assert len(last["items"]) == 5 and titles(last)[-1] == "Task 24"
    beyond = page(4)
    assert beyond["items"] == [] and beyond["total"] == 25

    seen = [t for n in (1, 2, 3) for t in titles(page(n))]
    assert len(seen) == len(set(seen)) == 25  # no repeats or gaps across pages

    assert alice.get(f"/projects/{pid}/tasks", params={"page_size": 500}).status_code == 422
    assert alice.get(f"/projects/{pid}/tasks", params={"page": 0}).status_code == 422


def test_sorting_by_priority_due_date_and_created(alice):
    pid = project_with(alice)
    soon, later = today_utc() + timedelta(days=1), today_utc() + timedelta(days=5)
    add_task(alice, pid, title="A", priority="low", due_date=str(later))
    add_task(alice, pid, title="B", priority="high")
    add_task(alice, pid, title="C", priority="medium", due_date=str(soon))

    def order(sort, direction):
        params = {"sort": sort, "order": direction}
        return "".join(titles(alice.get(f"/projects/{pid}/tasks", params=params).json()))

    assert order("priority", "desc") == "BCA"
    assert order("priority", "asc") == "ACB"
    assert order("due_date", "asc") == "CAB"  # no due date goes last...
    assert order("due_date", "desc") == "ACB"  # ...in both directions
    assert order("created_at", "asc") == "ABC"
    assert titles(alice.get(f"/projects/{pid}/tasks").json()) == ["C", "B", "A"]  # newest first by default
    assert alice.get(f"/projects/{pid}/tasks", params={"sort": "title"}).status_code == 422


def test_the_board_groups_by_status_and_takes_the_same_filters(alice, bob, filter_project):
    board = alice.get(f"/projects/{filter_project}/board").json()["columns"]
    assert set(board) == {"todo", "in_progress", "done"}
    assert len(board["todo"]) == 4 and board["in_progress"] == [] and board["done"] == []
    assert titles(board["todo"])[0] in {"Fix login bug", "Write docs"}  # high priority first

    login = next(t for t in board["todo"] if t["title"] == "Fix login bug")
    bob.patch(url(filter_project, login), json={"status": "in_progress"})
    filtered = alice.get(f"/projects/{filter_project}/board", params={"assignee": bob.id}).json()["columns"]
    assert titles(filtered["in_progress"]) == ["Fix login bug"]
    assert titles(filtered["todo"]) == ["Fix signup bug"]


# ---------------------------------------------------------------- comments and activity


def test_comments_show_who_and_when_to_every_member(alice, bob, carol):
    pid = project_with(alice, bob)
    task = add_task(alice, pid)
    posted = bob.post(f"{url(pid, task)}/comments", json={"body": "  On it  "})
    assert posted.status_code == 201
    assert posted.json()["body"] == "On it" and posted.json()["author"]["name"] == "Bob"
    assert posted.json()["created_at"]

    bob.post(f"{url(pid, task)}/comments", json={"body": "Second"})
    seen = alice.get(f"{url(pid, task)}/comments").json()
    assert [(c["author"]["name"], c["body"]) for c in seen] == [("Bob", "On it"), ("Bob", "Second")]
    assert alice.get(url(pid, task)).json()["comment_count"] == 2

    assert bob.post(f"{url(pid, task)}/comments", json={"body": "  "}).json()["fields"]["body"] == "Comment cannot be empty"
    assert carol.get(f"{url(pid, task)}/comments").status_code == 404


def test_the_activity_feed_records_the_key_events_newest_first(alice, bob):
    pid = project_with(alice, bob)
    task = add_task(alice, pid, title="Draft", assignee_id=bob.id)
    bob.patch(url(pid, task), json={"status": "in_progress"})
    bob.post(f"{url(pid, task)}/comments", json={"body": "hello"})
    alice.delete(url(pid, task))

    feed = alice.get(f"/projects/{pid}/activity").json()["items"]
    assert [(i["type"], i["actor"]["name"]) for i in feed] == [
        ("task_deleted", "Alice"),
        ("comment_added", "Bob"),
        ("task_moved", "Bob"),
        ("task_assigned", "Alice"),
        ("task_created", "Alice"),
        ("member_invited", "Alice"),
    ]
    moved = next(i for i in feed if i["type"] == "task_moved")
    assert (moved["meta"]["from_status"], moved["meta"]["to_status"]) == ("todo", "in_progress")
    assert all(i["meta"].get("task_title") in (None, "Draft") for i in feed)  # survives the task being deleted


# ---------------------------------------------------------------- dashboard, cascade


def test_the_dashboard_summarises_my_work(alice, bob, carol, db):
    big = project_with(alice, bob, name="Big")
    small = project_with(alice, name="Small")
    for title in ("T1", "T2"):
        add_task(alice, big, title=title, assignee_id=bob.id)
    add_task(alice, big, title="T3", assignee_id=bob.id, status="in_progress")
    add_task(alice, big, title="unassigned")
    add_task(alice, small, title="S1")
    add_task(alice, small, title="S2")
    finished = add_task(alice, big, title="T4", assignee_id=bob.id)
    assert bob.patch(url(big, finished), json={"status": "done"}).status_code == 200
    old = add_task(alice, big, title="T5", assignee_id=bob.id)
    bob.patch(url(big, old), json={"status": "done"})
    db.execute(update(Task).where(Task.id == uuid.UUID(old["id"])).values(completed_at=utcnow() - timedelta(days=10)))
    db.commit()
    carol_project = project_with(carol, name="Carol's")
    add_task(carol, carol_project, title="hers")

    mine = bob.get("/me/dashboard").json()
    assert mine["project_count"] == 1
    assert mine["assigned"] == {"todo": 2, "in_progress": 1, "done": 2}
    assert mine["completed_this_week"] == 1  # T5 was finished ten days ago
    assert mine["busiest_project"] == {"id": big, "name": "Big", "open_tasks": 4}
    assert mine["recent_activity"][0]["project"]["name"] == "Big"
    assert all(item["project"]["name"] != "Carol's" for item in mine["recent_activity"])

    owner = alice.get("/me/dashboard").json()
    assert owner["project_count"] == 2 and owner["assigned"] == {"todo": 0, "in_progress": 0, "done": 0}

    empty = carol.get("/me/dashboard").json()
    assert empty["busiest_project"]["name"] == "Carol's"
    fresh = carol.get("/me/dashboard")
    assert fresh.status_code == 200


def test_a_dashboard_for_someone_with_no_projects_is_empty_not_broken(make_user):
    newcomer = make_user("Newcomer")
    body = newcomer.get("/me/dashboard").json()
    assert body == {
        "project_count": 0,
        "assigned": {"todo": 0, "in_progress": 0, "done": 0},
        "completed_this_week": 0,
        "busiest_project": None,
        "recent_activity": [],
    }


def test_deleting_a_project_cascades_through_assigned_tasks_and_comments(alice, bob, db):
    pid = project_with(alice, bob)
    task = add_task(alice, pid, assignee_id=bob.id)
    add_task(bob, pid, title="Bob's own")
    alice.post(f"{url(pid, task)}/comments", json={"body": "note"})

    assert alice.delete(f"/projects/{pid}").status_code == 204
    for model in (Task, Comment, ProjectMember, Activity, Project):
        assert db.scalar(select(func.count()).select_from(model)) == 0, model.__name__
