"""Keep a web tab visible to the existing loopback server's browser-idle lifecycle."""
from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect

from . import context

router = APIRouter()
connected: set[WebSocket] = set()


@router.websocket('/presence')
async def presence(socket: WebSocket, source: str = ''):
    try:
        context.resolve(source)
    except HTTPException:
        await socket.close(code=1008)
        return
    await socket.accept()
    connected.add(socket)
    try:
        while True:
            await socket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        connected.discard(socket)
