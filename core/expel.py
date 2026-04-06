import asyncio
import json
import logging
import datetime
from typing import Dict, Any, Optional, Callable, List

from .gateway import Gateway, FatalTokenError
from .activity_assets import parse_activity_asset, is_external_url
from .tools.headers import Headers

logger = logging.getLogger(__name__)


class ExpelClient:
    """Main Discord client using custom headers and WebSocket gateway"""
    
    def __init__(self, token: str):
        self.token = token
        self.gateway: Optional[Gateway] = None
        self.is_connected = False
        self.user_data: Optional[Dict] = None
        self.headers = Headers(token)
        self.current_status = None
        
        self._status_callbacks: List[Callable[[str], None]] = []
        
    def on(self, event: str, handler: Callable):
        """Register event handler - will be passed to gateway"""
        pass
    
    def add_status_callback(self, callback: Callable[[str], None]):
        """Add callback for status changes"""
        self._status_callbacks.append(callback)
    
    def remove_status_callback(self, callback: Callable[[str], None]):
        """Remove status change callback"""
        if callback in self._status_callbacks:
            self._status_callbacks.remove(callback)
    
    def _notify_status_change(self, old_status: str, new_status: str):
        """Notify all callbacks of status change"""
        self.current_status = new_status
        for callback in self._status_callbacks:
            try:
                callback(new_status)
            except Exception as e:
                logger.error(f"[API] Status callback error: {e}")
        
    async def connect(self) -> Dict[str, Any]:
        """Connect to Discord gateway"""
        try:
            self.gateway = Gateway(self.token)
            
            self.gateway._client = self
            
            async def on_ready(data):
                self.user_data = data.get("user")
                self.is_connected = True
                
            self.gateway.on("ready", on_ready)
            
            await self.gateway.run()
            
            if not self.user_data:
                raise Exception("Failed to get user data")
                
            return {
                "user": self.user_data,
                "user_id": self.user_data['id'],
                "avatar_url": f"https://cdn.discordapp.com/avatars/{self.user_data['id']}/{self.user_data['avatar']}.png"
            }
            
        except FatalTokenError as e:
            logger.error(f"Fatal token error: {e}")
            raise Exception("Invalid Discord token") from e
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            raise e
            
    async def clear_presence(self):
        """Clear presence using opcode 3"""
        if not self.gateway or not self.is_connected:
            raise Exception("Not connected to gateway")
        await self.gateway.clear_presence()
        
    async def update_status(self, status: str):
        """Update user status using Discord REST API"""
        if not self.is_connected:
            raise Exception("Not connected to Discord")
        
        try:
            patch_request = self.headers.patch_status(status=status)
            
            response = self.headers.session.patch(
                patch_request["url"],
                headers=patch_request["headers"],
                json=patch_request["json"]
            )
            
            response.raise_for_status()
            self.current_status = status
            logger.info(f"[API] Status updated to {status}")
            
        except Exception as e:
            logger.error(f"[API] Failed to update status: {e}")
            raise Exception(f"Failed to update status: {e}")

    async def set_custom_status(self, text: str, emoji: str = None) -> Dict[str, str]:
        """Set custom status using Discord REST API"""
        if not self.is_connected:
            raise Exception("Not connected to Discord")
        
        try:
            emoji_payload = None
            if emoji:
                import re
                match = re.match(r"<(a?):([a-zA-Z0-9_\-]+):(\d+)>", emoji)
                if match:
                    animated, name, emoji_id = match.groups()
                    emoji_payload = {
                        "emoji_id": int(emoji_id),  
                        "emoji_name": str(name), 
                        "emoji_animated": bool(animated == "a")
                    }
                else:
                    emoji_payload = {"emoji_name": emoji}
            
            current_status = self.gateway.status if self.gateway else None
            if not current_status:
                try:
                    current_status = await self.gateway.get_current_status()
                    if not current_status:
                        raise Exception("Could not determine current status")
                except Exception as e:
                    logger.error(f"[API] Failed to get current status: {e}")
                    raise Exception("Gateway status not available - please ensure Discord connection is established")
            
            logger.info(f"[API] Using current status: {current_status} for custom status")
            status_payload = self.headers.build_status_payload(
                status=current_status,
                custom=text,
                emoji=emoji_payload
            )
            
            response = self.headers.session.patch(
                "https://discord.com/api/v9/users/@me/settings",
                headers=self.headers.get_headers(skip_context_props=True),
                json=status_payload
            )
            
            response.raise_for_status()
            logger.info(f"[API] Custom status set successfully: {text} with emoji: {emoji}")
            return {"message": "Custom status set successfully"}
            
        except Exception as e:
            logger.error(f"[API] Failed to set custom status: {e}")
            raise Exception(f"Failed to set custom status: {e}")
        
    async def set_rich_presence(self, activity: Dict[str, Any]):
        """Set rich presence"""
        if not self.gateway or not self.is_connected:
            raise Exception("Not connected to gateway")
        await self.gateway.set_rich_presence(activity)
        
    async def disconnect(self):
        """Disconnect from gateway"""
        if self.gateway:
            await self.gateway.disconnect()
            self.gateway = None
        self.is_connected = False

    async def proxy_external_assets(self, application_id: str, urls: list[str]) -> dict[str, str]:
        """Proxy external URLs through Discord's media proxy."""
        if not self.gateway or not self.is_connected:
            raise Exception("Not connected to gateway")
        return await self.gateway.proxy_external_assets(application_id, urls)


class ExpelAPI:
    """Main API class that manages the client and endpoints"""
    
    def __init__(self):
        self.client: Optional[ExpelClient] = None
        self.current_status = None
        self._lock = asyncio.Lock()
        self._login_task: Optional[asyncio.Task] = None
        self._token: Optional[str] = None
        
    async def login(self, token: str) -> Dict[str, Any]:
        """Login to Discord"""
        async with self._lock:
            if (
                self.client
                and self.client.is_connected
                and self._token == token
                and self.client.user_data
            ):
                return {
                    "user": self.client.user_data,
                    "user_id": self.client.user_data["id"],
                    "avatar_url": f"https://cdn.discordapp.com/avatars/{self.client.user_data['id']}/{self.client.user_data['avatar']}.png",
                }

            if self._login_task and not self._login_task.done():
                task = self._login_task
            else:
                if self.client:
                    try:
                        await self.client.disconnect()
                    except Exception:
                        pass
                    self.client = None

                self._token = token
                self.client = ExpelClient(token)
                
                def sync_status(new_status):
                    self.current_status = new_status
                    logger.info(f"[API] Status synchronized: {new_status}")
                
                self.client.add_status_callback(sync_status)
                
                self._login_task = asyncio.create_task(self.client.connect())
                task = self._login_task

        try:
            return await task
        except Exception as e:
            async with self._lock:
                if self._login_task is task:
                    self._login_task = None
                self.client = None
                self._token = None
            raise e
            
    async def logout(self):
        """Logout from Discord"""
        async with self._lock:
            task = self._login_task
            self._login_task = None
            client = self.client
            self.client = None
            self._token = None

        if task and not task.done():
            task.cancel()
        if client:
            await client.disconnect()
            
    async def is_connected(self) -> bool:
        """Check if connected"""
        return self.client is not None and self.client.is_connected if self.client else False
        
    async def get_status(self) -> Dict[str, Any]:
        """Get current status"""
        if not await self.is_connected():
            return {
                "connected": False,
                "detail": "Client not connected"
            }
            
        return {
            "connected": True,
            "user": str(self.client.user_data['username']) + "#" + str(self.client.user_data['discriminator']),
            "user_id": self.client.user_data['id'],
            "avatar_url": f"https://cdn.discordapp.com/avatars/{self.client.user_data['id']}/{self.client.user_data['avatar']}.png",
            "status": self.current_status
        }
        
    async def update_status(self, status: str) -> Dict[str, str]:
        """Update status"""
        if not await self.is_connected():
            raise Exception("Client not connected")
            
        await self.client.update_status(status)
        self.client.current_status = status
        self.current_status = status
        return {"message": f"Status updated to {status}"}
        
    async def clear_presence(self) -> Dict[str, str]:
        """Clear presence"""
        if not await self.is_connected():
            raise Exception("Client not connected")
            
        await self.client.clear_presence()
        return {"message": "Presence cleared"}
        
    async def reconnect(self) -> Dict[str, str]:
        """Reconnect to Discord"""
        async with self._lock:
            if not self.client or not self._token:
                raise Exception("No active client to reconnect")
            token = self._token

        await self.logout()
        await self.login(token)
        return {"message": "Reconnected successfully"}

    async def update_status(self, status: str) -> Dict[str, str]:
        """Update status"""
        if not await self.is_connected():
            raise Exception("Client not connected")
            
        await self.client.update_status(status)
        self.client.current_status = status
        self.current_status = status
        return {"message": f"Status updated to {status}"}
        
    async def get_current_status(self) -> str:
        """Get current Discord status from gateway"""
        if not await self.is_connected():
            return None
        return self.client.gateway.status if self.client and self.client.gateway else None

    async def set_custom_status(self, text: str, emoji: str = None) -> Dict[str, str]:
        """Set custom status using Discord REST API"""
        if not await self.is_connected():
            raise Exception("Client not connected")
            
        return await self.client.set_custom_status(text, emoji)

    async def set_rich_presence(self, presence_data: Dict[str, Any]) -> Dict[str, str]:
        """Set rich presence"""
        if not await self.is_connected():
            raise Exception("Client not connected")
        
        logger.info(f"[API] Building rich presence from data: {json.dumps(presence_data, indent=2)}")

        from .activity_builder import (
            ActivityTimestamps,
            ActivityAssets,
            ActivityParty,
            ActivityButton,
            build_rich_presence,
        )

        timestamps = None
        if presence_data.get("start") or presence_data.get("end"):
            timestamps = ActivityTimestamps(
                start=datetime.datetime.fromtimestamp(int(presence_data["start"]) / 1000) if presence_data.get("start") else None,
                end=datetime.datetime.fromtimestamp(int(presence_data["end"]) / 1000) if presence_data.get("end") else None,
            )

        assets = None
        if any([presence_data.get(k) for k in ["large_image_url", "large_text", "small_image_url", "small_text"]]):
            large_image = presence_data.get("large_image_url")
            small_image = presence_data.get("small_image_url")
            
            assets = ActivityAssets(
                large_image=parse_activity_asset(large_image),
                large_text=presence_data.get("large_text"),
                small_image=parse_activity_asset(small_image),
                small_text=presence_data.get("small_text"),
            )

        party = None
        if presence_data.get("party_id") or (presence_data.get("party_current") and presence_data.get("party_max")):
            party = ActivityParty(
                id=presence_data.get("party_id"),
                current_size=presence_data.get("party_current"),
                max_size=presence_data.get("party_max"),
            )

        buttons = None
        if presence_data.get("button1_label") and presence_data.get("button1_url"):
            buttons = [ActivityButton(label=presence_data["button1_label"], url=presence_data["button1_url"])]
        if presence_data.get("button2_label") and presence_data.get("button2_url"):
            buttons = buttons or []
            buttons.append(ActivityButton(label=presence_data["button2_label"], url=presence_data["button2_url"]))

        activity = build_rich_presence(
            name=presence_data.get("name"),
            type=presence_data.get("type"),
            details=presence_data.get("details") or " ",
            state=presence_data.get("state"),
            platform=presence_data.get("platform"),
            timestamps=timestamps,
            assets=assets,
            party=party,
            buttons=buttons,
            url=presence_data.get("url"),
            application_id=presence_data.get("application_id"),
        )
        
        logger.info(f"[API] Final activity payload: {json.dumps(activity, indent=2)}")
        
        try:
            await self.client.set_rich_presence(activity)
            logger.info("[API] Rich presence sent successfully")
        except Exception as e:
            logger.error(f"[API] Failed to set rich presence: {e}")
            raise e
            
        return {"message": "Rich presence set"}

    async def set_rich_presence_direct(self, activity: Dict[str, Any]) -> Dict[str, str]:
        """Set rich presence directly (used by routes when external assets are detected)"""
        if not await self.is_connected():
            raise Exception("Client not connected")
        try:
            await self.client.set_rich_presence(activity)
            return {"message": "Rich presence set"}
        except Exception as e:
            logger.error(f"[API] Failed to set rich presence: {e}")
            raise e

    async def proxy_external_assets(self, application_id: str, urls: list[str]) -> dict[str, str]:
        """Proxy external URLs through Discord's media proxy."""
        if not await self.is_connected():
            raise Exception("Client not connected")
        return await self.client.proxy_external_assets(application_id, urls)


api = ExpelAPI()