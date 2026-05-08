import json
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter(prefix="/ws", tags=["ws"])


@router.websocket("/dashboard")
async def websocket_endpoint(websocket: WebSocket):
    room = "dashboard"
    ws_manager = getattr(websocket.app.state, "ws_manager", None)
    if not ws_manager:
        await websocket.close(code=1011, reason="WS Manager not initialized")
        return

    await ws_manager.connect(websocket, room)

    try:
        await websocket.send_json({
            "type": "hello",
            "ws_id": uuid.uuid4().hex,
            "server_ts": datetime.now(timezone.utc).isoformat(),
        })
    except Exception:
        await ws_manager.disconnect(websocket, room)
        return

    try:
        while True:
            text = await websocket.receive_text()
            try:
                data = json.loads(text)
            except json.JSONDecodeError:
                continue

            if data.get("type") == "pong":
                await ws_manager.update_pong(websocket)
            elif data.get("type") == "subscribe":
                pass  # reserved for multi-room extension

    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket, room)
    except Exception:
        await ws_manager.disconnect(websocket, room)
