"""
WebSocket：演示实时推送（趋势点 + 标量），供前端图表增量更新。
生产环境应对 /ws 做鉴权（query token 或首包鉴权），勿长期留在 jwt 白名单。
"""

from __future__ import annotations

import asyncio
import json
import random
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws")
async def realtime_feed(websocket: WebSocket):
    await websocket.accept()
    tick = 0
    try:
        while True:
            await asyncio.sleep(2)
            tick += 1
            label = datetime.now(timezone.utc).strftime("%H:%M:%S")
            await websocket.send_text(
                json.dumps(
                    {
                        "type": "trend_point",
                        "data": {"label": label, "value": random.randint(50, 160)},
                    },
                    ensure_ascii=False,
                )
            )
            if tick % 2 == 0:
                await websocket.send_text(
                    json.dumps({"type": "update", "data": {"value": tick * 7}}, ensure_ascii=False)
                )
    except WebSocketDisconnect:
        pass
