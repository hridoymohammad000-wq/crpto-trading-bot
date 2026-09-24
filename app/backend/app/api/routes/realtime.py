from typing import cast

from fastapi import APIRouter, WebSocket

from app.realtime import RealtimeHub

router = APIRouter()


@router.websocket("/ws/live")
async def live_socket(websocket: WebSocket) -> None:
    hub = cast(RealtimeHub, websocket.app.state.realtime_hub)
    await hub.connect(websocket)
    try:
        await hub.publish("system_event", {"level": "success", "message": "Live WebSocket connected"})
        while True:
            await websocket.receive_text()
    except Exception:
        pass
    finally:
        await hub.disconnect(websocket)
