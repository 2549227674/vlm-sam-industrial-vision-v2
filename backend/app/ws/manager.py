import asyncio
import logging
from datetime import datetime, timezone

from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def connect(self, websocket: WebSocket, room: str = "dashboard") -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(room, set()).add(websocket)
        logger.info("WS connected to room=%s (total=%d)", room, self._count())

    async def disconnect(self, websocket: WebSocket, room: str = "dashboard") -> None:
        async with self._lock:
            conns = self._rooms.get(room)
            if conns:
                conns.discard(websocket)
                if not conns:
                    del self._rooms[room]
        logger.info("WS disconnected from room=%s (total=%d)", room, self._count())

    async def broadcast(self, room: str, message: dict) -> None:
        async with self._lock:
            conns = self._rooms.get(room)
            if not conns:
                return
            snapshot = list(conns)

        tasks = [ws.send_json(message) for ws in snapshot]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for ws, result in zip(snapshot, results):
            if isinstance(result, Exception):
                logger.warning("broadcast send error: %s", result)
                async with self._lock:
                    room_conns = self._rooms.get(room)
                    if room_conns:
                        room_conns.discard(ws)

    async def start_heartbeat(self, interval: float = 30.0) -> None:
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop(interval))

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self, interval: float) -> None:
        while True:
            await asyncio.sleep(interval)
            ping_msg = {"type": "ping", "ts": datetime.now(timezone.utc).isoformat()}
            for room in list(self._rooms.keys()):
                await self.broadcast(room, ping_msg)

    def _count(self) -> int:
        return sum(len(c) for c in self._rooms.values())
