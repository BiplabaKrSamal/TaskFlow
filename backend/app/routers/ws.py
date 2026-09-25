import asyncio
import time
import uuid

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool

from app.config import settings
from app.db import SessionLocal
from app.errors import AppError
from app.models import User
from app.realtime import hub
from app.security import Claims, decode_access_token
from app.services import projects

router = APIRouter(tags=["realtime"])

UNAUTHORIZED = 4401  # application-defined close code: "authenticate again and reconnect"


def _memberships(user_id: uuid.UUID) -> list[uuid.UUID] | None:
    """Runs in a worker thread. None means the account no longer exists."""
    with SessionLocal() as db:
        if db.get(User, user_id) is None:
            return None
        return projects.member_project_ids(db, user_id)


async def _authenticate(ws: WebSocket) -> Claims | None:
    """The first message must be {"type": "auth", "token": <access token>}, and it must come quickly."""
    try:
        first = await asyncio.wait_for(ws.receive_json(), settings.ws_auth_timeout_seconds)
        if not isinstance(first, dict) or first.get("type") != "auth" or not isinstance(first.get("token"), str):
            raise ValueError("first message must be an auth message")
        return decode_access_token(first["token"])
    except WebSocketDisconnect:
        return None
    except TimeoutError:
        await ws.close(code=UNAUTHORIZED, reason="auth_timeout")
    except AppError as err:
        await ws.close(code=UNAUTHORIZED, reason=err.code)
    except (ValueError, KeyError):
        await ws.close(code=UNAUTHORIZED, reason="bad_first_message")
    return None


@router.websocket("/ws")
async def live(ws: WebSocket):
    """One socket per browser tab.

    Clients never ask to join anything. The server looks up which projects the user belongs
    to and puts the socket in those rooms, so there is no room name to guess or forge.
    """
    await ws.accept()
    claims = await _authenticate(ws)
    if claims is None:
        return

    # Registering before reading memberships means an invite that commits in between is
    # still applied: hub.join() will find this socket even if our read missed the new row.
    client = hub.register(ws, claims.user_id)
    try:
        project_ids = await run_in_threadpool(_memberships, claims.user_id)
        if project_ids is None:
            await ws.close(code=UNAUTHORIZED, reason="unknown_user")
            return
        hub.join_all(client, project_ids)
        await client.send({"type": "ready", "projects": [str(p) for p in project_ids]})

        while True:
            # The socket is only as authenticated as the token it arrived with:
            # when that token expires the connection ends and the client reconnects with a fresh one.
            remaining = claims.exp - time.time()
            try:
                message = await asyncio.wait_for(ws.receive_json(), timeout=max(remaining, 0))
            except TimeoutError:
                await ws.close(code=UNAUTHORIZED, reason="token_expired")
                return
            except (ValueError, KeyError):
                continue  # not JSON text; nothing sensible to do with it
            if isinstance(message, dict) and message.get("type") == "ping":
                await client.send({"type": "pong"})
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(client)
