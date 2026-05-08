import asyncio
import logging
import time
from datetime import datetime, timezone

from fastapi import WebSocket

logger = logging.getLogger(__name__)


class ConnectionManager:
    def __init__(self) -> None:
        self._rooms: dict[str, set[WebSocket]] = {}
        self._last_pong: dict[WebSocket, float] = {}
        self._lock = asyncio.Lock()
        self._heartbeat_task: asyncio.Task[None] | None = None

    async def connect(self, websocket: WebSocket, room: str = "dashboard") -> None:
        await websocket.accept()
        async with self._lock:
            self._rooms.setdefault(room, set()).add(websocket)
            self._last_pong[websocket] = time.monotonic()
        logger.info("WS connected to room=%s (total=%d)", room, self._count())

    async def disconnect(self, websocket: WebSocket, room: str = "dashboard") -> None:
        async with self._lock:
            conns = self._rooms.get(room)
            if conns:
                conns.discard(websocket)
                if not conns:
                    del self._rooms[room]
            self._last_pong.pop(websocket, None)
        logger.info("WS disconnected from room=%s (total=%d)", room, self._count())

    async def update_pong(self, websocket: WebSocket) -> None:
        async with self._lock:
            if websocket in self._last_pong:
                self._last_pong[websocket] = time.monotonic()

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
                    self._last_pong.pop(ws, None)

    async def start_heartbeat(self) -> None:
        self._heartbeat_task = asyncio.create_task(self._heartbeat_loop())

    async def stop_heartbeat(self) -> None:
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            try:
                await self._heartbeat_task
            except asyncio.CancelledError:
                pass

    async def _heartbeat_loop(self) -> None:
        tick_interval = 5.0
        ping_interval = 30.0
        elapsed = 0.0

        while True:
            await asyncio.sleep(tick_interval)
            elapsed += tick_interval

            # every 5s: metrics_tick
            await self.broadcast("dashboard", {
                "type": "metrics_tick",
                "ws_clients": self._count(),
                "qps": 0.0,
            })

            # every 30s: ping + stale cleanup
            if elapsed >= ping_interval:
                elapsed = 0.0

                await self.broadcast("dashboard", {
                    "type": "ping",
                    "ts": datetime.now(timezone.utc).isoformat(),
                })

                # close connections that haven't ponged in 60s
                now = time.monotonic()
                stale: list[WebSocket] = []
                async with self._lock:
                    stale = [
                        ws for ws, t in self._last_pong.items()
                        if now - t > 60.0
                    ]
                for ws in stale:
                    try:
                        await ws.close(code=1008, reason="heartbeat timeout")
                    except Exception:
                        pass
                    # disconnect will be triggered by the WebSocketDisconnect
                    # exception in the route handler

    def _count(self) -> int:
        return sum(len(c) for c in self._rooms.values())
