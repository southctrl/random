import asyncio
import json
import logging
import random
import time
import zlib
from typing import Optional, Dict, Any, Callable

from curl_cffi import AsyncSession

from .tools.headers import Headers

logger = logging.getLogger(__name__)


def _redact(obj: Any):
    if isinstance(obj, dict):
        redacted: Dict[str, Any] = {}
        for k, v in obj.items():
            if isinstance(k, str) and k.lower() in {"token", "authorization", "cookie", "set-cookie"}:
                redacted[k] = "[REDACTED]"
            else:
                redacted[k] = _redact(v)
        return redacted
    if isinstance(obj, list):
        return [_redact(v) for v in obj]
    return obj


GATEWAY_URL = "wss://gateway.discord.gg/?v=10&encoding=json&compress=zlib-stream"
API_BASE = "https://discord.com/api/v10"

_NO_RESUME_CODES = {4004, 4010, 4011, 4012, 4013, 4014}
_FATAL_CODES = {4004, 4014}
_SESSION_MAX_AGE = 4 * 3600


class FatalTokenError(Exception):
    pass


class Gateway:
    def __init__(self, token: str, proxy: str = None):
        self.token = token
        self.proxy = proxy
        self.spoofer = Headers(token)

        self._status: str = None
        self._activities: list[Dict[str, Any]] = []

        self._last_status_check = None
        self._status_poll_task = None

        self.session_id = None
        self.sequence = None
        self.resume_url = None

        self._heartbeat_interval = None
        self._heartbeat_task = None
        self._last_ack = True
        self._last_heartbeat_sent = 0.0
        self._attempting_resume = False

        self._inflator = zlib.decompressobj()
        self._buffer = bytearray()
        self._ws = None
        self._http = None

        self._reconnect_delay = 1
        self._running = True
        self._close_code = None
        self._session_born = 0.0

        self._tasks: set[asyncio.Task] = set()
        self._event_handlers: Dict[str, Callable] = {}
        self.user_data: Optional[Dict] = None
        self.is_connected = False
        self._client: Optional['ExpelClient'] = None

    async def get_current_status(self) -> str:
        """Get current status from Discord REST API"""
        try:
            response = self.spoofer.session.get(
                "https://discord.com/api/v9/users/@me/settings",
                headers=self.spoofer.get_headers()
            )
            if response.status_code == 200:
                settings = response.json()
                status = settings.get("status")
                if status:
                    print(f"[GATEWAY] Current status from API: {status}")
                    return status
        except Exception as e:
            print(f"[GATEWAY] Failed to get current status: {e}")
        return None

    async def _status_polling_loop(self):
        """Backup polling to detect status changes from Discord API"""
        while self._running:
            try:
                await asyncio.sleep(2)
                current_status = await self.get_current_status()
                if current_status is not None and current_status != self._status:
                    old_status = self._status
                    print(f"[GATEWAY] 📊 POLLING detected change from {old_status} to {current_status}")
                    logger.info(f"[GATEWAY] Polling detected change from {old_status} to {current_status}")
                    self._status = current_status
                    
                    if hasattr(self, '_client') and self._client:
                        print(f"[GATEWAY] ✅ Client reference exists: {type(self._client)}")
                        self._client.current_status = current_status
                        self._client._notify_status_change(old_status, current_status)
                    else:
                        print(f"[GATEWAY] ❌ No client reference - status updated but no notification")
            except Exception as e:
                print(f"[GATEWAY] Status polling error: {e}")

    @property
    def status(self) -> str:
        """Get current Discord status"""
        return self._status

    def on(self, event: str, handler: Callable):
        """Register event handler"""
        self._event_handlers[event] = handler

    def _spawn(self, coro) -> asyncio.Task:
        t = asyncio.create_task(coro)
        self._tasks.add(t)
        t.add_done_callback(self._tasks.discard)
        return t

    async def _init_http(self):
        if self._http:
            try:
                await self._http.close()
            except Exception:
                pass

        self._http = AsyncSession(impersonate="chrome136", proxy=self.proxy)

    async def _send(self, data: dict):
        if not self._ws:
            logger.error("[GATEWAY] Cannot send - no WebSocket connection")
            return
        try:
            payload = json.dumps(data)
            logger.info("[GATEWAY] Sending to Discord: %s", json.dumps(_redact(data)))
            await self._ws.send_str(payload)
            logger.info("[GATEWAY] Message sent successfully")
        except Exception as e:
            logger.error(f"[GATEWAY] Send error: {e}")
            print(f"[GATEWAY] Send error: {e}")

    async def _heartbeat_loop(self, interval: float):
        await asyncio.sleep(interval * random.random() / 1000)
        while self._running:
            if not self._last_ack:
                print("[GATEWAY] No heartbeat ACK -- forcing reconnect")
                ws = self._ws
                self._ws = None
                self.is_connected = False
                if ws is not None:
                    try:
                        await ws.close(code=1008)
                    except Exception:
                        pass
                return

            self._last_ack = False
            self._last_heartbeat_sent = time.monotonic()
            await self._send({"op": 1, "d": self.sequence})
            await asyncio.sleep(interval / 1000)

    async def _identify(self):
        p = self.spoofer.profile
        await self._send({
            "op": 2,
            "d": {
                "token": self.token,
                "properties": {
                    "os": p.os,
                    "browser": p.browser,
                    "device": "",
                    "system_locale": p.locale,
                    "has_client_mods": False,
                    "browser_user_agent": p.user_agent,
                    "browser_version": p.browser_version,
                    "os_version": p.os_version,
                    "referrer": "",
                    "referring_domain": "",
                    "referrer_current": "",
                    "referring_domain_current": "",
                    "release_channel": "stable",
                    "client_build_number": self.spoofer.build_number,
                    "client_event_source": None,
                    "client_launch_id": self.spoofer._launch_id,
                    "launch_signature": self.spoofer._launch_signature,
                    "client_app_state": "focused",
                    "client_heartbeat_session_id": self.spoofer._heartbeat_session_id,
                },
                "compress": True,
                "large_threshold": 250,
                "presence": {
                    "status": self._status, 
                    "since": 0,
                    "activities": self._activities,
                    "afk": False,
                },
                "capabilities": 16381,
            }
        })

    async def _resume(self):
        await self._send({
            "op": 6,
            "d": {
                "token": self.token,
                "session_id": self.session_id,
                "seq": self.sequence,
            }
        })

    def _decompress(self, data: bytes):
        self._buffer.extend(data)
        if len(self._buffer) < 4 or self._buffer[-4:] != b"\x00\x00\xff\xff":
            return None

        try:
            result = self._inflator.decompress(self._buffer)
            self._buffer.clear()
            return result.decode("utf-8")
        except zlib.error as e:
            print(f"[GATEWAY] Decompress error: {e}")
            self._inflator = zlib.decompressobj()
            self._buffer.clear()
            return None

    async def _handle_message(self, raw: bytes):
        text = self._decompress(raw)
        if not text:
            return

        try:
            msg = json.loads(text)
        except json.JSONDecodeError as e:
            print(f"[GATEWAY] JSON error: {e}")
            return

        op = msg.get("op")
        d = msg.get("d")
        t = msg.get("t")
        s = msg.get("s")

        if s is not None:
            self.sequence = s

        if op == 10:
            interval = d["heartbeat_interval"]
            self._heartbeat_interval = interval
            if self._heartbeat_task:
                self._heartbeat_task.cancel()
            self._last_ack = True
            self._heartbeat_task = self._spawn(self._heartbeat_loop(interval))

            if self._attempting_resume and self.session_id:
                print("[GATEWAY] Attempting resume...")
                await self._resume()
            else:
                await self._identify()

        elif op == 11:
            self._last_ack = True

        elif op == 1:
            await self._send({"op": 1, "d": self.sequence})

        elif op == 7:
            print("[GATEWAY] Server requested reconnect")
            self._attempting_resume = True
            try:
                await self._ws.close(code=4000)
            except Exception:
                pass

        elif op == 9:
            resumable = bool(d)
            print(f"[GATEWAY] Invalid session (resumable={resumable})")
            if resumable and self.session_id:
                await asyncio.sleep(random.uniform(1, 3))
                await self._resume()
            else:
                self.session_id = None
                self.sequence = None
                self.resume_url = None
                self._attempting_resume = False
                self._session_born = 0.0
                await asyncio.sleep(random.uniform(1, 5))
                await self._identify()

        elif op == 0:
            if t == "READY":
                self.session_id = d["session_id"]
                self.resume_url = d.get("resume_gateway_url", GATEWAY_URL)
                self._reconnect_delay = 1
                self._session_born = time.monotonic()
                self.is_connected = True

                user = d.get("user", {})
                self.user_data = user
                
                current_status = await self.get_current_status()
                if current_status:
                    self._status = current_status
                    print(f"[GATEWAY] Real-time status set to: {self._status}")
                else:
                    if "presence" in d:
                        self._status = d["presence"].get("status")
                        if self._status:
                            print(f"[GATEWAY] Status from READY event: {self._status}")
                        else:
                            print("[GATEWAY] Status unknown - will update when available")
                    else:
                        print("[GATEWAY] Status not available - will update when available")
                
                print(f"[GATEWAY] Ready as {user.get('username')}#{user.get('discriminator')} ({user.get('id')})")

                if "ready" in self._event_handlers:
                    self._spawn(self._event_handlers["ready"](d))

            elif t == "RESUMED":
                self._reconnect_delay = 1
                self.is_connected = True
                print("[GATEWAY] Session resumed successfully")
                if "ready" in self._event_handlers:
                    self._spawn(self._event_handlers["ready"](d))

            elif t == "PRESENCE_UPDATE":
                user = d.get("user", {})
                user_id = user.get("id")
                my_id = self.user_data.get("id")
                username = user.get("username")
                my_username = self.user_data.get("username")
                status = d.get("status")
                
                is_my_user = (user_id == my_id) or (username == my_username)
                
                is_my_user_and_status_changed = is_my_user and (status and status != self._status)
                
                if is_my_user_and_status_changed:
                    print(f"[GATEWAY] PRESENCE_UPDATE received: {d}")
                    print(f"[GATEWAY] User ID from event: {user_id}")
                    print(f"[GATEWAY] My user ID: {my_id}")
                    print(f"[GATEWAY] Username from event: {username}")
                    print(f"[GATEWAY] My username: {my_username}")
                    print(f"[GATEWAY] Status from event: {status}")
                    print(f"[GATEWAY] Current stored status: {self._status}")
                    print(f"[GATEWAY] Is my user: {is_my_user}")
                
                if is_my_user:
                    new_status = status
                    if new_status and new_status != self._status:
                        old_status = self._status
                        print(f"[GATEWAY] MY STATUS updated from {old_status} to {new_status}")
                        logger.info(f"[GATEWAY] Status updated from {old_status} to {new_status}")
                        self._status = new_status
                        
                        if hasattr(self, '_client') and self._client:
                            self._client.current_status = new_status
                            self._client._notify_status_change(old_status, new_status)

            if t in self._event_handlers:
                self._spawn(self._event_handlers[t](d))

        elif op == 7:
            print("[GATEWAY] Server requested reconnect")
            self._attempting_resume = True
            try:
                await self._ws.close(code=4000)
            except Exception:
                pass

        elif op == 9:
            resumable = bool(d)
            print(f"[GATEWAY] Invalid session (resumable={resumable})")
            if resumable and self.session_id:
                await asyncio.sleep(random.uniform(1, 3))
                await self._resume()
            else:
                self.session_id = None
                self.sequence = None
                self.resume_url = None
                self._attempting_resume = False
                self._session_born = 0.0
                await asyncio.sleep(random.uniform(1, 5))
                await self._identify()

    async def _connect(self):
        session_age = time.monotonic() - self._session_born
        if self.session_id and session_age >= _SESSION_MAX_AGE:
            print(f"[GATEWAY] Session age {session_age / 3600:.1f}h too old -- reidentifying")
            self.session_id = None
            self.sequence = None
            self.resume_url = None
            self._attempting_resume = False
            self._session_born = 0.0

        can_resume = bool(self.session_id and self.resume_url)
        url = self.resume_url if can_resume else GATEWAY_URL
        self._attempting_resume = can_resume
        self.resume_url = None

        self._inflator = zlib.decompressobj()
        self._buffer = bytearray()
        self._last_ack = True
        self._close_code = None

        session = AsyncSession(impersonate="chrome136", proxy=self.proxy)
        ws = None

        try:
            ws = await session.ws_connect(
                url,
                headers=self.spoofer.get_websocket_headers(),
            )
            self._ws = ws
            print(f"[GATEWAY] Connected to {url}")

            async for msg in ws:
                if self._ws is None:
                    break
                if isinstance(msg, bytes):
                    await self._handle_message(msg)

        except asyncio.CancelledError:
            raise
        except Exception as e:
            print(f"[GATEWAY] Connection error: {e}")
            self.is_connected = False
        finally:
            self._ws = None
            fatal_exc = None

            try:
                if ws:
                    code = getattr(ws, "close_code", None)
                    if code:
                        self._close_code = code
                        if code in _FATAL_CODES:
                            print(f"[GATEWAY] Fatal close code {code}")
                            self._running = False
                            fatal_exc = FatalTokenError(f"Discord close code {code}")
                        elif code in _NO_RESUME_CODES:
                            print(f"[GATEWAY] Close code {code} -- clearing session")
                            self.session_id = None
                            self.sequence = None
                            self.resume_url = None
                            self._attempting_resume = False
                            self._session_born = 0.0
                    await ws.close()
            except Exception:
                pass

            try:
                await session.close()
            except Exception:
                pass

            if fatal_exc:
                raise fatal_exc

    async def run(self):
        await self._init_http()

        while self._running:
            try:
                await self._connect()
                if self.is_connected and self.user_data:
                    if self._status_poll_task:
                        self._status_poll_task.cancel()
                    self._status_poll_task = asyncio.create_task(self._status_polling_loop())
                    break
            except FatalTokenError:
                raise
            except asyncio.CancelledError:
                print("[GATEWAY] Task cancelled -- reconnecting")
                self.is_connected = False
            except Exception as e:
                print(f"[GATEWAY] Unhandled error: {e}")
                self.is_connected = False
            finally:
                if self._heartbeat_task:
                    try:
                        self._heartbeat_task.cancel()
                        await self._heartbeat_task
                    except (asyncio.CancelledError, RuntimeError):
                        pass
                    self._heartbeat_task = None

            if not self._running:
                break

            if not self.is_connected:
                print(f"[GATEWAY] Connection lost, auto-reconnecting in {self._reconnect_delay}s...")
                await asyncio.sleep(self._reconnect_delay)
                self._reconnect_delay = min(self._reconnect_delay * 2, 60)

    async def clear_presence(self):
        """Clear presence using opcode 3"""
        if not self.is_connected or not self._ws:
            raise Exception("Not connected to gateway")

        self._activities = []
        
        payload = {
            "op": 3,
            "d": {
                "since": None,
                "activities": self._activities,
                "status": self._status,
                "afk": False
            }
        }
        
        logger.info(f"[GATEWAY] Sending opcode 3 - Clear Presence: {json.dumps(payload, indent=2)}")
        logger.info(f"[GATEWAY] Request to Discord Gateway - Clearing presence")
        
        await self._send(payload)
        
        logger.info("[GATEWAY] Presence cleared successfully")

    async def update_status(self, status: str):
        """Update user status via REST API + gateway.
        
        Uses PATCH /users/@me/settings so the change persists
        even when the real Discord client is running.
        """
        if not self.is_connected or not self._ws:
            raise Exception("Not connected to gateway")

        await self._patch_settings({"status": status})

        self._status = status
        since = int(time.time() * 1000) if status == "idle" else None
        
        payload = {
            "op": 3,
            "d": {
                "since": since,
                "activities": self._activities,
                "status": self._status,
                "afk": False
            }
        }
        
        logger.info(f"[GATEWAY] Sending opcode 3 - Update Status: {json.dumps(payload, indent=2)}")
        logger.info(f"[GATEWAY] Request to Discord Gateway - Updating status to: {status}")
        
        await self._send(payload)
        
        logger.info(f"[GATEWAY] Status updated to {status} successfully")

    async def set_custom_status(self, text: Optional[str] = None, emoji: Optional[str] = None):
        """Set custom status via REST API + gateway.
        
        Uses PATCH /users/@me/settings so the change persists
        even when the real Discord client is running.
        """
        if not self.is_connected or not self._ws:
            raise Exception("Not connected to gateway")

        if not text and not emoji:
            custom_status = None
        else:
            custom_status = {}
            if text:
                custom_status["text"] = text
            if emoji:
                custom_status["emoji_name"] = emoji
            custom_status["expires_at"] = None

        await self._patch_settings({"custom_status": custom_status})
        logger.info(f"[GATEWAY] Custom status set via REST API: {json.dumps(custom_status)}")

        activity: Dict[str, Any] = {
            "name": "Custom Status",
            "type": 4,
        }
        if text:
            activity["state"] = text
        if emoji:
            activity["emoji"] = {"name": emoji}

        await self.set_rich_presence(activity)

    async def _patch_settings(self, payload: Dict[str, Any]):
        """PATCH /users/@me/settings to persist status/custom-status."""
        if not self._http:
            await self._init_http()

        endpoint = f"{API_BASE}/users/@me/settings"
        p = self.spoofer.profile
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": p.user_agent,
            "Accept": "*/*",
            "Accept-Language": f"{p.locale},en;q=0.9",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/channels/@me",
            "Sec-Ch-Ua": f'"Not:A-Brand";v="99", "Google Chrome";v="{p.browser_version.split(".")[0]}", "Chromium";v="{p.browser_version.split(".")[0]}"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{p.os}"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Super-Properties": self.spoofer._xsp(),
        }

        try:
            resp = await self._http.patch(
                endpoint,
                headers=headers,
                json=payload,
            )
            if resp.status_code != 200:
                logger.error("[GATEWAY] PATCH settings failed: %s %s", resp.status_code, resp.text[:200])
            else:
                logger.info("[GATEWAY] Settings updated via REST API: %s", json.dumps(payload))
        except Exception as e:
            logger.error("[GATEWAY] PATCH settings error: %s", e)

    async def set_rich_presence(self, activity: Dict[str, Any]):
        """Set rich presence, preserving coexisting activities.
        
        Discord supports multiple activities simultaneously:
        - Type 4 (custom status) coexists with type 0 (game/RPC)
        - Setting one type preserves the other type
        """
        if not self.is_connected or not self._ws:
            raise Exception("Not connected to gateway")

        activity_type = activity.get("type")

        other = [a for a in self._activities if a.get("type") != activity_type]
        self._activities = other + [activity]
        
        payload = {
            "op": 3,
            "d": {
                "since": None,
                "activities": self._activities,
                "status": self._status,
                "afk": False
            }
        }

        activity_name = activity.get("name", "Unknown")
        if activity_type == 4:
            logger.info("[GATEWAY] Sending opcode 3 - Set Custom Status: %s", json.dumps(payload, indent=2))
            logger.info("[GATEWAY] Request to Discord Gateway - Setting custom status")
        else:
            logger.info("[GATEWAY] Sending opcode 3 - Set Rich Presence: %s", json.dumps(payload, indent=2))
            logger.info(
                "[GATEWAY] Request to Discord Gateway - Setting rich presence with activity: %s",
                activity_name,
            )
        
        await self._send(payload)

        if activity_type == 4:
            logger.info("[GATEWAY] Custom status set successfully")
        else:
            logger.info("[GATEWAY] Rich presence set successfully for activity: %s", activity_name)

    async def disconnect(self):
        """Disconnect from gateway"""
        self._running = False
        
        if self._heartbeat_task:
            self._heartbeat_task.cancel()
            
        if self._ws:
            await self._ws.close()
            
        if self._http:
            await self._http.close()
            
        self.is_connected = False
        print("[GATEWAY] Disconnected from gateway")

    async def proxy_external_assets(self, application_id: str, urls: list[str]) -> dict[str, str]:
        """Proxy external URLs through Discord's media proxy.
        
        Calls POST /applications/{app_id}/external-assets to convert
        external URLs into mp:external/... paths that Discord can render
        in rich presence.
        
        Returns a mapping of original URL -> mp:prefixed asset path.
        """
        if not urls:
            return {}

        if not self._http:
            await self._init_http()

        endpoint = f"{API_BASE}/applications/{application_id}/external-assets"
        p = self.spoofer.profile
        headers = {
            "Authorization": self.token,
            "Content-Type": "application/json",
            "User-Agent": p.user_agent,
            "Accept": "*/*",
            "Accept-Language": f"{p.locale},en;q=0.9",
            "Origin": "https://discord.com",
            "Referer": "https://discord.com/channels/@me",
            "Sec-Ch-Ua": f'"Not:A-Brand";v="99", "Google Chrome";v="{p.browser_version.split(".")[0]}", "Chromium";v="{p.browser_version.split(".")[0]}"',
            "Sec-Ch-Ua-Mobile": "?0",
            "Sec-Ch-Ua-Platform": f'"{p.os}"',
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "X-Super-Properties": self.spoofer._xsp(),
        }

        unique_urls = list(dict.fromkeys(urls))

        logger.info("[GATEWAY] Proxying %d external asset URL(s) via app %s", len(unique_urls), application_id)

        try:
            resp = await self._http.post(
                endpoint,
                headers=headers,
                json={"urls": unique_urls},
            )

            if resp.status_code != 200:
                logger.error("[GATEWAY] External asset proxy failed: %s %s", resp.status_code, resp.text)
                raise Exception(f"Discord external asset proxy returned {resp.status_code}: {resp.text}")

            data = resp.json()
            logger.info("[GATEWAY] External asset proxy response: %s", json.dumps(data))

            result: dict[str, str] = {}
            for item in data:
                original_url = item.get("url", "")
                asset_path = item.get("external_asset_path", "")
                if original_url and asset_path:
                    result[original_url] = f"mp:{asset_path}"

            logger.info("[GATEWAY] Proxied assets: %s", json.dumps(result))
            return result

        except Exception as e:
            logger.error("[GATEWAY] External asset proxy error: %s", e)
            raise
