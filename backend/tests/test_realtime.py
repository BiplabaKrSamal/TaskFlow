import time
from contextlib import contextmanager

import pytest
from starlette.websockets import WebSocketDisconnect

from app.config import settings


def project_with(owner, *members, name="Launch") -> str:
    pid = owner.post("/projects", json={"name": name}).json()["id"]
    for member in members:
        assert owner.post(f"/projects/{pid}/members", json={"email": member.email}).status_code == 201
    return pid


@contextmanager
def live(client, person):
    """An authenticated socket, already past the 'ready' message."""
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "auth", "token": person.token})
        ready = ws.receive_json()
        assert ready["type"] == "ready", ready
        ws.ready = ready
        yield ws


def next_event(ws, expected_type):
    message = ws.receive_json()
    assert message["type"] == expected_type, message
    return message


def assert_quiet(ws):
    """Nothing else is waiting: the next thing that arrives is the answer to our own ping."""
    ws.send_json({"type": "ping"})
    assert ws.receive_json() == {"type": "pong"}


def closed_with(ws) -> WebSocketDisconnect:
    with pytest.raises(WebSocketDisconnect) as info:
        ws.receive_json()
    return info.value


# ------------------------------------------------------------------ authentication


def test_a_bad_token_is_refused_and_the_socket_closed(client):
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "auth", "token": "not-a-token"})
        closed = closed_with(ws)
    assert closed.code == 4401 and closed.reason == "invalid_token"


def test_the_first_message_has_to_be_auth(client, alice):
    with client.websocket_connect("/api/ws") as ws:
        ws.send_json({"type": "ping"})
        assert closed_with(ws).code == 4401


def test_a_socket_that_never_authenticates_is_dropped(client, monkeypatch):
    monkeypatch.setattr(settings, "ws_auth_timeout_seconds", 0.3)
    with client.websocket_connect("/api/ws") as ws:
        closed = closed_with(ws)
    assert closed.code == 4401 and closed.reason == "auth_timeout"


def test_the_socket_ends_when_its_access_token_expires(client, make_user, monkeypatch):
    monkeypatch.setattr(settings, "access_token_ttl_seconds", 2)
    dana = make_user("Dana")
    started = time.time()
    with live(client, dana) as ws:
        closed = closed_with(ws)
    assert closed.code == 4401 and closed.reason == "token_expired"
    assert time.time() - started < 5


# ------------------------------------------------------------------ what gets delivered


def test_members_see_task_changes_live(client, alice, bob):
    pid = project_with(alice, bob)
    with live(client, bob) as bob_ws, live(client, alice) as alice_ws:
        assert bob_ws.ready["projects"] == [pid]

        task = alice.post(f"/projects/{pid}/tasks", json={"title": "Draft copy", "assignee_id": bob.id}).json()
        created = next_event(bob_ws, "task_created")
        assert created["project_id"] == pid and created["actor"]["name"] == "Alice"
        assert created["meta"]["task_title"] == "Draft copy"
        assigned = next_event(bob_ws, "task_assigned")
        assert assigned["meta"]["assignee_id"] == bob.id  # the "Assigned to me" trigger
        next_event(alice_ws, "task_created")
        next_event(alice_ws, "task_assigned")

        path = f"/projects/{pid}/tasks/{task['id']}"
        bob.patch(path, json={"status": "in_progress"})
        moved = next_event(alice_ws, "task_moved")
        assert (moved["meta"]["from_status"], moved["meta"]["to_status"]) == ("todo", "in_progress")
        assert moved["actor"]["name"] == "Bob"
        next_event(bob_ws, "task_moved")

        alice.patch(path, json={"title": "Draft the copy", "priority": "high"})
        updated = next_event(bob_ws, "task_updated")
        assert sorted(updated["meta"]["fields"]) == ["priority", "title"]
        next_event(alice_ws, "task_updated")

        bob.post(f"{path}/comments", json={"body": "on it"})
        assert next_event(alice_ws, "comment_added")["actor"]["name"] == "Bob"
        next_event(bob_ws, "comment_added")

        alice.delete(path)
        assert next_event(bob_ws, "task_deleted")["meta"]["task_title"] == "Draft the copy"
        next_event(alice_ws, "task_deleted")


def test_a_failed_request_sends_nothing(client, alice, bob):
    pid = project_with(alice, bob)
    task = alice.post(f"/projects/{pid}/tasks", json={"title": "Protected"}).json()
    with live(client, alice) as ws:
        denied = bob.patch(f"/projects/{pid}/tasks/{task['id']}", json={"status": "done"})
        assert denied.status_code == 403
        assert_quiet(ws)


def test_events_never_cross_into_projects_you_are_not_in(client, alice, bob, carol):
    shared = project_with(alice, bob, name="Shared")
    hers = project_with(carol, name="Hers")
    with live(client, carol) as carol_ws, live(client, bob) as bob_ws:
        assert carol_ws.ready["projects"] == [hers]

        alice.post(f"/projects/{shared}/tasks", json={"title": "Alice's task"})
        next_event(bob_ws, "task_created")
        assert_quiet(carol_ws)

        carol.post(f"/projects/{hers}/tasks", json={"title": "Carol's task"})
        assert_quiet(bob_ws)
        next_event(carol_ws, "task_created")


def test_a_client_cannot_ask_to_join_a_room(client, alice, carol):
    pid = project_with(alice)
    with live(client, carol) as ws:
        ws.send_json({"type": "subscribe", "project_id": pid})
        ws.send_json({"type": "auth", "token": alice.token})  # a second auth does not switch identity either
        alice.post(f"/projects/{pid}/tasks", json={"title": "Private"})
        assert_quiet(ws)


# ------------------------------------------------------------------ membership changes


def test_invites_and_removals_move_open_sockets_in_and_out_of_the_room(client, alice, bob):
    pid = project_with(alice)
    with live(client, bob) as bob_ws, live(client, alice) as alice_ws:
        assert bob_ws.ready["projects"] == []

        alice.post(f"/projects/{pid}/members", json={"email": bob.email})
        invited = next_event(bob_ws, "member_invited")  # Bob hears about his own invite
        assert invited["meta"]["member_id"] == bob.id
        next_event(alice_ws, "member_invited")

        alice.post(f"/projects/{pid}/tasks", json={"title": "Now visible"})
        next_event(bob_ws, "task_created")
        next_event(alice_ws, "task_created")

        alice.delete(f"/projects/{pid}/members/{bob.id}")
        gone = next_event(bob_ws, "removed_from_project")
        assert gone["project_id"] == pid
        assert next_event(alice_ws, "member_removed")["meta"]["member_name"] == "Bob"

        alice.post(f"/projects/{pid}/tasks", json={"title": "Bob must not see this"})
        next_event(alice_ws, "task_created")
        assert_quiet(bob_ws)


def test_reconnecting_picks_up_memberships_changed_while_away(client, alice, bob):
    pid = project_with(alice)
    with live(client, bob) as ws:
        assert ws.ready["projects"] == []
    alice.post(f"/projects/{pid}/members", json={"email": bob.email})
    with live(client, bob) as ws:
        assert ws.ready["projects"] == [pid]


def test_deleting_a_project_tells_its_members(client, alice, bob):
    pid = project_with(alice, bob)
    with live(client, bob) as ws:
        alice.delete(f"/projects/{pid}")
        gone = next_event(ws, "project_deleted")
        assert gone["project_id"] == pid and gone["project_name"] == "Launch"
        assert_quiet(ws)
