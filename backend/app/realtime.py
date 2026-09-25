import asyncio
import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass

from fastapi import WebSocket

from app.config import settings

log = logging.getLogger("taskflow.realtime")


@dataclass(frozen=True)
class Event:
    """Something that happened in a project. Only members of that project should hear it."""

    project_id: uuid.UUID
    payload: dict


class Client:
    def __init__(self, ws: WebSocket, user_id: uuid.UUID):
        self.ws = ws
        self.user_id = user_id
        self.projects: set[uuid.UUID] = set()

    async def send(self, payload: dict) -> bool:
        try:
            await asyncio.wait_for(self.ws.send_json(payload), settings.ws_send_timeout_seconds)
            return True
        except Exception:  # closed socket or a consumer too slow to keep up: caller drops it
            return False


class Hub:
    """Which sockets hear about which project.

    Every method runs on the event loop and nowhere else, so the sets need no locks.
    Sync route code never calls the hub directly; it schedules these as background tasks
    after its transaction has committed.
    """

    def __init__(self) -> None:
        self._rooms: dict[uuid.UUID, set[Client]] = defaultdict(set)
        self._by_user: dict[uuid.UUID, set[Client]] = defaultdict(set)

    def register(self, ws: WebSocket, user_id: uuid.UUID) -> Client:
        client = Client(ws, user_id)
        self._by_user[user_id].add(client)
        return client

    def unregister(self, client: Client) -> None:
        for project_id in list(client.projects):
            self._leave(client, project_id)
        clients = self._by_user.get(client.user_id)
        if clients is not None:
            clients.discard(client)
            if not clients:
                del self._by_user[client.user_id]

    def join_all(self, client: Client, project_ids: list[uuid.UUID]) -> None:
        for project_id in project_ids:
            self._join(client, project_id)

    async def join(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """A user became a member: their open sockets start hearing about the project."""
        for client in list(self._by_user.get(user_id, ())):
            self._join(client, project_id)

    async def evict(self, project_id: uuid.UUID, user_id: uuid.UUID) -> None:
        """A user lost access: stop their sockets hearing about the project, and tell them."""
        for client in list(self._by_user.get(user_id, ())):
            self._leave(client, project_id)
            await client.send({"type": "removed_from_project", "project_id": str(project_id)})

    async def drop_project(self, project_id: uuid.UUID) -> None:
        for client in list(self._rooms.get(project_id, ())):
            self._leave(client, project_id)

    async def publish(self, events: list[Event]) -> None:
        for event in events:
            clients = list(self._rooms.get(event.project_id, ()))
            delivered = await asyncio.gather(*(client.send(event.payload) for client in clients))
            for client, ok in zip(clients, delivered):
                if not ok:
                    log.info("dropping unreachable websocket for user %s", client.user_id)
                    self.unregister(client)

    def _join(self, client: Client, project_id: uuid.UUID) -> None:
        self._rooms[project_id].add(client)
        client.projects.add(project_id)

    def _leave(self, client: Client, project_id: uuid.UUID) -> None:
        room = self._rooms.get(project_id)
        if room is not None:
            room.discard(client)
            if not room:
                del self._rooms[project_id]
        client.projects.discard(project_id)


hub = Hub()
