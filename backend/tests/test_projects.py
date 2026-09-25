from sqlalchemy import func, select

from app.models import Activity, ActivityType, Project, ProjectMember


def make_project(owner, name="Launch"):
    response = owner.post("/projects", json={"name": name, "description": "Ship it"})
    assert response.status_code == 201, response.text
    return response.json()


def invite(owner, project, person):
    response = owner.post(f"/projects/{project['id']}/members", json={"email": person.email})
    assert response.status_code == 201, response.text
    return response.json()


def test_creating_a_project_makes_you_the_owner(alice):
    project = make_project(alice)
    assert project["role"] == "owner"
    assert project["member_count"] == 1
    assert project["open_task_count"] == 0

    listed = alice.get("/projects").json()
    assert [p["id"] for p in listed] == [project["id"]]


def test_project_validation_gives_field_errors(alice):
    response = alice.post("/projects", json={"name": "   "})
    assert response.status_code == 422
    assert response.json()["fields"]["name"] == "Project name is required"


def test_people_only_see_projects_they_belong_to(alice, bob):
    project = make_project(alice)
    assert bob.get("/projects").json() == []
    # a project you are not in looks exactly like one that does not exist
    assert bob.get(f"/projects/{project['id']}").status_code == 404
    assert bob.get(f"/projects/{project['id']}/activity").status_code == 404
    assert bob.get("/projects/00000000-0000-0000-0000-000000000000").status_code == 404


def test_the_owner_can_invite_a_registered_user_by_email(alice, bob):
    project = make_project(alice)
    member = invite(alice, project, bob)
    assert member["role"] == "member"
    assert member["user"]["email"] == "bob@example.com"

    seen_by_bob = bob.get("/projects").json()
    assert seen_by_bob[0]["role"] == "member"
    assert seen_by_bob[0]["member_count"] == 2

    detail = bob.get(f"/projects/{project['id']}").json()
    assert [(m["user"]["name"], m["role"]) for m in detail["members"]] == [("Alice", "owner"), ("Bob", "member")]


def test_invite_errors_are_specific(alice, bob):
    project = make_project(alice)
    unknown = alice.post(f"/projects/{project['id']}/members", json={"email": "nobody@example.com"})
    assert unknown.status_code == 404 and "email" in unknown.json()["fields"]

    invite(alice, project, bob)
    again = alice.post(f"/projects/{project['id']}/members", json={"email": "BOB@example.com"})
    assert again.status_code == 409 and again.json()["code"] == "already_member"

    bad = alice.post(f"/projects/{project['id']}/members", json={"email": "nope"})
    assert bad.status_code == 422


def test_members_cannot_manage_membership_or_delete_the_project(alice, bob, carol):
    project = make_project(alice)
    invite(alice, project, bob)
    pid = project["id"]

    assert bob.post(f"/projects/{pid}/members", json={"email": carol.email}).status_code == 403
    assert bob.delete(f"/projects/{pid}/members/{alice.id}").status_code == 403
    denied = bob.delete(f"/projects/{pid}")
    assert denied.status_code == 403 and denied.json()["code"] == "owner_only"
    assert alice.get(f"/projects/{pid}").status_code == 200


def test_removing_a_member_revokes_their_access(alice, bob):
    project = make_project(alice)
    invite(alice, project, bob)
    pid = project["id"]
    assert bob.get(f"/projects/{pid}").status_code == 200

    assert alice.delete(f"/projects/{pid}/members/{bob.id}").status_code == 204
    # the token is still valid, membership is what changed: access ends immediately
    assert bob.get(f"/projects/{pid}").status_code == 404
    assert bob.get("/projects").json() == []
    assert alice.get(f"/projects/{pid}").json()["members"][0]["user"]["name"] == "Alice"


def test_the_owner_cannot_be_removed_and_strangers_are_not_found(alice, bob):
    project = make_project(alice)
    pid = project["id"]
    assert alice.delete(f"/projects/{pid}/members/{alice.id}").json()["code"] == "cannot_remove_owner"
    assert alice.delete(f"/projects/{pid}/members/{bob.id}").status_code == 404


def test_deleting_a_project_removes_everything_that_hung_off_it(alice, bob, db):
    project = make_project(alice)
    invite(alice, project, bob)
    pid = project["id"]

    assert alice.delete(f"/projects/{pid}").status_code == 204
    assert alice.get(f"/projects/{pid}").status_code == 404

    assert db.scalar(select(func.count()).select_from(Project)) == 0
    assert db.scalar(select(func.count()).select_from(ProjectMember)) == 0
    assert db.scalar(select(func.count()).select_from(Activity)) == 0


def test_membership_changes_land_in_the_activity_feed_newest_first(alice, bob, carol):
    project = make_project(alice)
    pid = project["id"]
    invite(alice, project, bob)
    invite(alice, project, carol)
    alice.delete(f"/projects/{pid}/members/{bob.id}")

    feed = bob_feed = alice.get(f"/projects/{pid}/activity").json()
    assert [(i["type"], i["meta"]["member_name"]) for i in feed["items"]] == [
        ("member_removed", "Bob"),
        ("member_invited", "Carol"),
        ("member_invited", "Bob"),
    ]
    assert feed["items"][0]["actor"]["name"] == "Alice"
    assert bob_feed["next_before"] is None


def test_the_activity_feed_pages_with_a_cursor(alice, make_user):
    project = make_project(alice)
    pid = project["id"]
    for i in range(5):
        invite(alice, project, make_user(f"Guest{i}"))

    first = alice.get(f"/projects/{pid}/activity", params={"limit": 2}).json()
    assert len(first["items"]) == 2 and first["next_before"] is not None
    second = alice.get(f"/projects/{pid}/activity", params={"limit": 2, "before": first["next_before"]}).json()
    third = alice.get(f"/projects/{pid}/activity", params={"limit": 2, "before": second["next_before"]}).json()

    ids = [i["id"] for page in (first, second, third) for i in page["items"]]
    assert len(ids) == 5 and ids == sorted(ids, reverse=True) and len(set(ids)) == 5
    assert third["next_before"] is None
    assert {i["type"] for i in first["items"]} == {ActivityType.member_invited.value}
