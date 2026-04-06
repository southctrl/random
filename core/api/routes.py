import logging
from typing import *
from fastapi import APIRouter, HTTPException, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
import json
import asyncio

from core import api

logger = logging.getLogger(__name__)

public = APIRouter()

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self.status_callbacks: List[Callable[[str], None]] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
        
        def status_callback(new_status: str):
            asyncio.create_task(self.broadcast_status(new_status))
        
        if api.client and status_callback not in self.status_callbacks:
            api.client.add_status_callback(status_callback)
            self.status_callbacks.append(status_callback)

    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)

    async def broadcast_status(self, status: str):
        """Broadcast status change to all connected clients"""
        message = {"type": "status_change", "status": status}
        for connection in self.active_connections:
            try:
                await connection.send_text(json.dumps(message))
            except:
                self.active_connections.remove(connection)

manager = ConnectionManager()


class LoginRequest(BaseModel):
    token: str


class StatusUpdate(BaseModel):
    status: Literal["online", "idle", "dnd", "invisible"]


class RichPresenceRequest(BaseModel):
    platform: Optional[Literal["ps5", "xbox"]] = None
    name: str = "Custom Status"
    type: Optional[str] = None
    details: Optional[str] = None
    state: Optional[str] = None
    large_image_url: Optional[str] = None
    large_text: Optional[str] = None
    small_image_url: Optional[str] = None
    small_text: Optional[str] = None
    start: Optional[int] = None
    end: Optional[int] = None
    button1_label: Optional[str] = None
    button1_url: Optional[str] = None
    button2_label: Optional[str] = None
    button2_url: Optional[str] = None
    streaming_url: Optional[str] = None


class SpotifyRequest(BaseModel):
    title: str
    artists: list[str]
    album: str
    album_cover_url: str
    track_id: str
    duration_ms: int
    start_ms: int = 0


def _normalize_token(raw: str) -> str:
    t = raw.strip().strip('"').strip("'")
    if t.lower().startswith("bearer "):
        t = t[7:].strip()
    return t


@public.get("/platforms")
async def get_platforms():
    """Get available platforms"""
    return {
        "platforms": [
            {"value": "", "label": "None"},
            {"value": "ps5", "label": "Playstation"},
            {"value": "xbox", "label": "Xbox"}
        ]
    }


@public.get("/")
async def root():
    return {"service": "Expel Selfbot API", "health": "ok", "docs": "/docs"}


@public.post("/login")
async def login(request: LoginRequest):
    token = _normalize_token(request.token)
    logger.info("Processing token of length: %d", len(token))
    
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    if len(token) < 20:
        raise HTTPException(
            status_code=400,
            detail="Token looks too short. Paste the full user token from Discord.",
        )

    try:
        result = await api.login(token)
        return {
            "message": "Logged in successfully",
            **result
        }
    except Exception as e:
        logger.exception("Login failed")
        raise HTTPException(status_code=401, detail="Invalid Discord token") from e


@public.post("/logout")
async def logout():
    await api.logout()
    return {"message": "Logged out"}


@public.get("/status")
async def get_status():
    return await api.get_status()


@public.post("/status/update")
async def update_status(request: StatusUpdate):
    try:
        return await api.update_status(request.status)
    except Exception as e:
        if str(e) == "Client not connected":
            raise HTTPException(status_code=400, detail="login first") from e
        logger.exception("Status update failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@public.post("/rpc/set-rich-presence")
async def set_rich_presence(request: Request):
    try:
        presence_data = await request.json()
        if not isinstance(presence_data, dict):
            raise HTTPException(status_code=400, detail="Body must be a JSON object")

        for k, v in list(presence_data.items()):
            if isinstance(v, str) and v.strip() == "":
                presence_data[k] = None

        if "type" in presence_data and presence_data["type"]:
            activity_type_map = {
                "Playing": 0,
                "Streaming": 1,
                "Listening": 2,
                "Watching": 3,
                "Competing": 5
            }
            presence_data["type"] = activity_type_map.get(presence_data["type"])

        logger.info(f"[ROUTES] Received rich presence request: {presence_data}")

        def _is_external_url(val: object) -> bool:
            if not isinstance(val, str):
                return False
            val_lower = val.lower()
            if val_lower.startswith(("https://cdn.discordapp.com/", "https://media.discordapp.net/", "https://images-ext-")):
                return False
            return val_lower.startswith(("http://", "https://"))

        large_url = presence_data.get("large_image_url")
        small_url = presence_data.get("small_image_url")
        urls_to_proxy = []
        if _is_external_url(large_url):
            urls_to_proxy.append(large_url)
        if _is_external_url(small_url):
            urls_to_proxy.append(small_url)

        if urls_to_proxy:
            if not await api.is_connected():
                raise HTTPException(status_code=400, detail="login first")

            app_id = presence_data.get("application_id") or "1445842785709326570"
            app_id = str(app_id)

            logger.info(f"[ROUTES] Proxying {len(urls_to_proxy)} external URL(s) via app {app_id}")

            try:
                proxied = await api.proxy_external_assets(app_id, urls_to_proxy)
            except Exception as e:
                logger.error(f"[ROUTES] Failed to proxy external assets: {e}")
                raise HTTPException(status_code=400, detail=f"Failed to proxy external image URLs: {e}")

            if large_url and large_url in proxied:
                presence_data["large_image_url"] = proxied[large_url]
                logger.info(f"[ROUTES] Proxied large_image: {large_url} -> {proxied[large_url]}")
            if small_url and small_url in proxied:
                presence_data["small_image_url"] = proxied[small_url]
                logger.info(f"[ROUTES] Proxied small_image: {small_url} -> {proxied[small_url]}")

        return await api.set_rich_presence(presence_data)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        msg = str(e)
        if msg == "Client not connected":
            raise HTTPException(status_code=400, detail="login first") from e
        logger.exception("Set rich presence failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@public.post("/test-discord-example")
async def test_discord_example():
    """Test with exact Discord example format"""
    try:
        logger.info("[ROUTES] Testing Discord example format")
        
        discord_example = {
            "name": "Rocket League",
            "details": "Ranked Duos: 2-1", 
            "state": "In a Match",
            "platform": "xbox"
        }
        
        return await api.set_rich_presence(discord_example)
    except Exception as e:
        logger.exception("Discord example test failed")
        raise HTTPException(status_code=503, detail=str(e)) from e

@public.post("/reconnect")
async def reconnect():
    try:
        return await api.reconnect()
    except Exception as e:
        if str(e) == "No active client to reconnect":
            raise HTTPException(status_code=400, detail="login first") from e
        logger.exception("Reconnect failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@public.get("/rpc/current-status")
async def get_current_status():
    """Get current Discord status in real-time"""
    try:
        if not api.client or not api.client.gateway:
            return {"status": None}
        
        current_status = api.client.gateway.status
        logger.info(f"[ROUTES] Current status requested: {current_status}")
        return {"status": current_status}
    except Exception as e:
        logger.exception("Failed to get current status")
        return {"status": None}


@public.websocket("/ws/status")
async def websocket_status_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time status updates"""
    await manager.connect(websocket)
    try:
        if api.client and api.client.gateway:
            current_status = api.client.gateway.status
            if current_status:
                await websocket.send_text(json.dumps({"type": "status_change", "status": current_status}))
        
        while True:
            try:
                await websocket.receive_text()
            except WebSocketDisconnect:
                break
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(websocket)


@public.post("/rpc/set-custom-status")
async def set_custom_status(req: Request):
    try:
        body = await req.json()
        final_text = body.get("text")
        final_emoji = body.get("emoji")
        
        logger.info(f"[ROUTES] Custom status request received: text='{final_text}', emoji='{final_emoji}'")
        return await api.set_custom_status(text=final_text, emoji=final_emoji)
    except Exception as e:
        if str(e) == "Client not connected":
            raise HTTPException(status_code=400, detail="login first") from e
        logger.exception("Set custom status failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@public.post("/rpc/spotify")
async def set_spotify_presence(request: SpotifyRequest):
    try:
        presence_data = {
            "name": "Spotify",
            "type": 2,
            "details": request.title,
            "state": f"by {', '.join(request.artists)}",
            "assets": {
                "large_image": request.album_cover_url,
                "large_text": request.album
            },
            "timestamps": {
                "start": int(request.start_ms / 1000),
                "end": int((request.start_ms + request.duration_ms) / 1000)
            }
        }
        
        return await api.set_rich_presence(presence_data)
    except Exception as e:
        if str(e) == "Client not connected":
            raise HTTPException(status_code=400, detail="login first") from e
        logger.exception("Set Spotify presence failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@public.post("/clear")
async def clear_presence():
    try:
        return await api.clear_presence()
    except Exception as e:
        if str(e) == "Client not connected":
            raise HTTPException(status_code=400, detail="login first") from e
        logger.exception("Clear presence failed")
        raise HTTPException(status_code=503, detail=str(e)) from e


@public.get("/current-activities")
async def get_current_activities():
    """Get current Discord activities with timestamps"""
    try:
        if not api.client or not api.client.gateway:
            return {"activities": []}
        
        activities = api.client.gateway._activities
        logger.info(f"[ROUTES] Current activities: {activities}")
        
        return {"activities": activities}
    except Exception as e:
        logger.exception("Failed to get current activities")
        return {"activities": []}


@public.post("/clear-id")
async def clear_specific_instance(request: Request):
    """Clear specific RPC instance by ID"""
    try:
        body = await request.json()
        instance_id = body.get("instanceId")
        
        if not instance_id:
            raise HTTPException(status_code=400, detail="instanceId is required")
        
        logger.info(f"[ROUTES] Clearing specific RPC instance: {instance_id}")
        
        if api.client and api.client.gateway:
            current_status = api.client.gateway.status
            logger.info(f"[ROUTES] Current status before clearing: {current_status}")
            
            await api.clear_presence()
            
            logger.info(f"[ROUTES] Cleared instance {instance_id} - other instances may need to be restarted")
        
        return {"message": f"Cleared instance {instance_id}", "instance_id": instance_id}
    except Exception as e:
        logger.exception(f"Clear instance {instance_id} failed")
        raise HTTPException(status_code=503, detail=str(e)) from e
