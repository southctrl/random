import json
import re
import uuid
import base64
import random
import time
import hashlib
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Sequence

from curl_cffi.requests import Session




CHROME_VERSIONS = [
    {"major": "145", "full": "145.0.0.0"},
    {"major": "144", "full": "144.0.7251.168"},
    {"major": "143", "full": "143.0.7204.220"},
]

LOCATIONS = [
    {"timezone": "America/New_York",    "locale": "en-US"},
    {"timezone": "America/Chicago",     "locale": "en-US"},
    {"timezone": "America/Los_Angeles", "locale": "en-US"},
    {"timezone": "Europe/London",       "locale": "en-GB"},
    {"timezone": "Europe/Paris",        "locale": "fr-FR"},
    {"timezone": "Asia/Tokyo",          "locale": "ja-JP"},
    {"timezone": "Australia/Sydney",    "locale": "en-AU"},
]

RESOLUTIONS = ["1920x1080", "2560x1440", "3840x2160", "1366x768", "1536x864"]

CONTEXT_LOCATIONS = {
    "chat":         "chat_input",
    "guild":        "guild_header",
    "profile":      "user_profile",
    "dm":           "dm_channel",
    "search":       "search",
    "context_menu": "context_menu",
    "add_friend":   "add_friend_navbar",
    "join_guild":   "join_guild",
    "settings":     "user_settings",
}



@dataclass
class BrowserProfile:
    user_agent: str
    os: str
    browser: str
    browser_version: str
    os_version: str
    locale: str
    timezone: str
    screen_resolution: str
    hardware_concurrency: int
    device_memory: int



class Headers:
    _build_cache: Optional[int] = None
    _build_cache_time: float    = 0.0
    BUILD_CACHE_TTL             = 3600

    def __init__(self, token: str):
        self.token       = token
        self.cookies     = ""
        self.fingerprint = ""
        self._fp_cache_time = 0.0
        self._app_state     = "focused"

        self.profile = self._make_profile()
        self.session = Session(impersonate="chrome136")

        self.build_number = self._get_build_number()

        self._launch_id            = str(uuid.uuid4())
        self._launch_signature     = str(uuid.uuid4())
        self._heartbeat_session_id = str(uuid.uuid4())
        self._installation_id      = str(uuid.uuid4())
        self._science_token        = self._make_science_token()


    def _make_profile(self) -> BrowserProfile:
        seed = int(hashlib.md5(self.token.encode()).hexdigest(), 16)
        rng  = random.Random(seed)
        loc    = rng.choice(LOCATIONS)
        chrome = rng.choice(CHROME_VERSIONS)
        return BrowserProfile(
            user_agent=f"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/{chrome['full']} Safari/537.36",
            os="Windows",
            browser="Chrome",
            browser_version=chrome["full"],
            os_version=rng.choice(["10", "11"]),
            locale=loc["locale"],
            timezone=loc["timezone"],
            screen_resolution=rng.choice(RESOLUTIONS),
            hardware_concurrency=rng.choice([8, 12, 16]),
            device_memory=rng.choice([8, 16, 32]),
        )

    def _make_science_token(self) -> str:
        parts = self.token.split(".")
        return f"{parts[0]}.{parts[1]}" if len(parts) >= 2 else self.token





    def _get_build_number(self) -> int:
        now = time.time()
        if Headers._build_cache and now - Headers._build_cache_time < self.BUILD_CACHE_TTL:
            return Headers._build_cache
        try:
            r = self.session.get(
                "https://discord.com/login",
                headers={"User-Agent": self.profile.user_agent},
                timeout=15,
            )
            scripts = re.findall(r'<script src="(/assets/[^"]+\.js)"', r.text)
            for path in reversed(scripts):
                js = self.session.get(
                    f"https://discord.com{path}",
                    headers={"User-Agent": self.profile.user_agent},
                    timeout=15,
                )
                for pat in [
                    r'buildNumber\s*[=:]\s*"?(\d{5,7})"?',
                    r'"buildNumber","(\d{5,7})"',
                    r'CLIENT_BUILD_NUMBER\s*[=:]\s*(\d{5,7})',
                    r'build_number["\s:=]+(\d{5,7})',
                    r'"(\d{6,7})"\s*,\s*"stable"',
                ]:
                    m = re.search(pat, js.text)
                    if m:
                        build = int(m.group(1))
                        Headers._build_cache      = build
                        Headers._build_cache_time = now
                        print(f"[*] build: {build}")
                        return build
        except Exception as e:
            print(f"[!] build fetch failed: {e}")
        fallback = 502980
        Headers._build_cache      = fallback
        Headers._build_cache_time = now
        return fallback

    def refresh_build_number(self) -> int:
        Headers._build_cache_time = 0.0
        self.build_number = self._get_build_number()
        return self.build_number



    def _fallback_fingerprint(self) -> str:
        return f"{int(time.time() * 1000)}.{random.randint(10**17, 10**18 - 1)}"

    def _default_cookies(self) -> str:
        h = hashlib.md5(self.token.encode()).hexdigest()
        return f"__dcfduid={h[:32]}; __sdcfduid={h}{h[:40]}; locale={self.profile.locale}"

    def fetch_fingerprint(self) -> Tuple[str, str]:
        if time.time() - self._fp_cache_time < 3600 and self.fingerprint:
            return self.fingerprint, self.cookies
        try:
            r = self.session.get(
                "https://discord.com/api/v9/experiments",
                headers={
                    "User-Agent":      self.profile.user_agent,
                    "Accept":          "application/json",
                    "Accept-Language": self.profile.locale,
                },
                timeout=10,
            )
            if r.status_code == 200:
                self.fingerprint    = r.json().get("fingerprint", self._fallback_fingerprint())
                jar                 = "; ".join(f"{k}={v}" for k, v in r.cookies.items())
                self.cookies        = jar + ("" if "locale=" in jar else f"; locale={self.profile.locale}")
                self._fp_cache_time = time.time()
            else:
                self.fingerprint = self._fallback_fingerprint()
                self.cookies     = self._default_cookies()
        except Exception as e:
            print(f"[!] fingerprint error: {e}")
            self.fingerprint = self._fallback_fingerprint()
            self.cookies     = self._default_cookies()
        return self.fingerprint, self.cookies



    def _xsp(
        self,
        referrer_current: str         = "https://discord.com/",
        referring_domain_current: str = "discord.com",
    ) -> str:
        props = {
            "os":                          self.profile.os,
            "browser":                     self.profile.browser,
            "device":                      "",
            "system_locale":               self.profile.locale,
            "has_client_mods":             False,
            "browser_user_agent":          self.profile.user_agent,
            "browser_version":             self.profile.browser_version,
            "os_version":                  self.profile.os_version,
            "referrer":                    "",
            "referring_domain":            "",
            "referrer_current":            referrer_current,
            "referring_domain_current":    referring_domain_current,
            "release_channel":             "stable",
            "client_build_number":         self.build_number,
            "client_event_source":         None,
            "client_launch_id":            self._launch_id,
            "launch_signature":            self._launch_signature,
            "client_app_state":            self._app_state,
            "client_heartbeat_session_id": self._heartbeat_session_id,
        }
        return base64.b64encode(json.dumps(props, separators=(",", ":")).encode()).decode()

    def _sec_ch_ua(self) -> str:
        v = self.profile.browser_version.split(".")[0]
        return f'"Not:A-Brand";v="99", "Google Chrome";v="{v}", "Chromium";v="{v}"'

    def _context_props(self, location: str) -> str:
        return base64.b64encode(
            json.dumps({"location": location}, separators=(",", ":")).encode()
        ).decode()

    def _shared(self, referer: str, cookies: str, fingerprint: str) -> Dict:
        return {
            "User-Agent":         self.profile.user_agent,
            "Accept":             "*/*",
            "Accept-Language":    f"{self.profile.locale},en;q=0.9",
            "Accept-Encoding":    "gzip, deflate, br, zstd",
            "Origin":             "https://discord.com",
            "Referer":            referer,
            "Sec-Ch-Ua":          self._sec_ch_ua(),
            "Sec-Ch-Ua-Mobile":   "?0",
            "Sec-Ch-Ua-Platform": f'"{self.profile.os}"',
            "Sec-Fetch-Dest":     "empty",
            "Sec-Fetch-Mode":     "cors",
            "Sec-Fetch-Site":     "same-origin",
            "Dnt":                "1",
            "Priority":           "u=1, i",
            "X-Debug-Options":    "bugReporterEnabled",
            "X-Discord-Locale":   self.profile.locale,
            "X-Discord-Timezone": self.profile.timezone,
            "X-Super-Properties": self._xsp(),
            "X-Fingerprint":      fingerprint,
            "Cookie":             cookies,
        }



    def set_focused(self):
        self._app_state = "focused"

    def set_unfocused(self):
        self._app_state = "unfocused"



    def get_headers(
        self,
        referer: str             = "https://discord.com/channels/@me",
        context_location: str    = "chat_input",
        extra: Dict              = None,
        skip_context_props: bool = False,
    ) -> Dict:
        fp, cookies = self.fetch_fingerprint()
        h = {
            "Authorization": self.token,
            "Content-Type":  "application/json",
            **self._shared(referer, cookies, fp),
        }
        if not skip_context_props:
            h["X-Context-Properties"] = self._context_props(context_location)
        if extra:
            h.update(extra)
        return h

    def get_science_headers(self, referer: str = "https://discord.com/channels/@me") -> Dict:
        fp, cookies = self.fetch_fingerprint()
        return {
            "Authorization": self.token,
            "Content-Type":  "application/json",
            **self._shared(referer, cookies, fp),
        }

    def get_multipart_headers(
        self,
        content_type: str,
        referer: str = "https://discord.com/channels/@me",
    ) -> Dict:
        fp, cookies = self.fetch_fingerprint()
        h = {
            "Authorization": self.token,
            "Content-Type":  content_type,
            **self._shared(referer, cookies, fp),
        }
        return h

    def get_websocket_headers(self) -> Dict:
        return {
            "User-Agent":               self.profile.user_agent,
            "Accept-Encoding":          "gzip, deflate, br",
            "Accept-Language":          self.profile.locale,
            "Cache-Control":            "no-cache",
            "Pragma":                   "no-cache",
            "Sec-WebSocket-Extensions": "permessage-deflate; client_max_window_bits",
            "Sec-WebSocket-Version":    "13",
            "Upgrade":                  "websocket",
            "Connection":               "Upgrade",
            "Origin":                   "https://discord.com",
        }



    def build_message_payload(
        self,
        content: str,
        nonce: str               = None,
        reply_to: str            = None,
        reply_channel: str       = None,
        reply_guild: str         = None,
        tts: bool                = False,
        flags: int               = 0,
        attachments: List        = None,
        sticker_ids: List[str]   = None,
        components: List         = None,
    ) -> Dict:
        if not nonce:
            nonce = str((int(time.time() * 1000) - 1420070400000) * 4194304)
        payload: Dict = {
            "mobile_network_type": "unknown",
            "content":             content,
            "nonce":               nonce,
            "tts":                 tts,
            "flags":               flags,
        }
        if reply_to:
            payload["message_reference"] = {
                "message_id": reply_to,
                "channel_id": reply_channel,
                "guild_id":   reply_guild,
            }
            payload["allowed_mentions"] = {
                "parse":        ["users", "roles", "everyone"],
                "replied_user": True,
            }
        if attachments:
            payload["attachments"] = attachments
        if sticker_ids:
            payload["sticker_ids"] = sticker_ids
        if components:
            payload["components"] = components
        return payload

    def build_reaction_payload(self) -> Dict:
        return {}

    def build_ack_payload(self) -> Dict:
        return {"token": None, "mention_count": 0}

    def build_typing_payload(self) -> Dict:
        return {}

    def build_science_payload(self, events: List[Dict]) -> Dict:
        return {"token": self._science_token, "events": events}

    def build_science_event(self, event_type: str, extra_props: Dict = None) -> Dict:
        props = {
            "client_track_timestamp":      int(time.time() * 1000),
            "client_heartbeat_session_id": self._heartbeat_session_id,
            "client_uuid":                 self._launch_id,
        }
        if extra_props:
            props.update(extra_props)
        return {"type": event_type, "properties": props}

    def build_ad_heartbeat(self) -> Dict:
        return self.build_science_event("client_ad_heartbeat", {
            "session_id": self._heartbeat_session_id,
        })

    def build_avatar_data_uri(self, image_bytes: bytes, mime: str = "image/png") -> str:
        return f"data:{mime};base64,{base64.b64encode(image_bytes).decode()}"

    def build_profile_payload(
        self,
        bio: str          = None,
        accent_color: int = None,
        pronouns: str     = None,
        banner: bytes     = None,
        banner_mime: str  = "image/png",
        effects: List     = None,
    ) -> Dict:
        payload = {}
        if bio          is not None: payload["bio"]          = bio
        if accent_color is not None: payload["accent_color"] = accent_color
        if pronouns     is not None: payload["pronouns"]     = pronouns
        if banner       is not None: payload["banner"]       = self.build_avatar_data_uri(banner, banner_mime)
        if effects      is not None: payload["profile_effects"] = effects
        return payload

    def build_status_payload(
        self,
        status: str   = None,
        custom: str   = None,
        emoji: Dict   = None,
        expires: int  = None,
    ) -> Dict:
        if not status:
            raise ValueError("Status cannot be None - must be set from actual Discord status")
        payload: Dict = {"status": status}
        if custom is not None:
            cs: Dict = {"text": custom}
            if emoji:
                cs["emoji_name"] = emoji.get("emoji_name")
                if emoji.get("emoji_id"):
                    cs["emoji_id"] = emoji["emoji_id"]
                if emoji.get("animated"):
                    cs["emoji_animated"] = emoji["animated"]
            if expires:
                cs["expires_at"] = expires
            payload["custom_status"] = cs
        return payload

    def build_settings_payload(self, settings_b64: str) -> Dict:
        return {"settings": settings_b64}

    def build_relationship_payload(self, username: str = None) -> Dict:
        payload: Dict = {}
        if username:
            payload["username"] = username
        return payload

    def build_join_guild_payload(self, invite_code: str) -> Dict:
        return {
            "session_id": self._heartbeat_session_id,
        }

    def build_thread_payload(
        self,
        name: str,
        auto_archive: int = 1440,
        slowmode: int     = 0,
    ) -> Dict:
        return {
            "name":                  name,
            "auto_archive_duration": auto_archive,
            "rate_limit_per_user":   slowmode,
            "type":                  11,
            "location":              "message",
        }

    def build_channel_payload(
        self,
        name: str,
        topic: str    = None,
        nsfw: bool    = False,
        slowmode: int = 0,
        position: int = None,
    ) -> Dict:
        payload: Dict = {"name": name, "nsfw": nsfw, "rate_limit_per_user": slowmode}
        if topic    is not None: payload["topic"]    = topic
        if position is not None: payload["position"] = position
        return payload

    def send_message(self, channel_id: str, content: str, guild_id: str = "@me", **kwargs) -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages",
            "headers": self.get_headers(referer=referer, context_location="chat_input"),
            "json":    self.build_message_payload(content, **kwargs),
        }

    def edit_message(self, channel_id: str, message_id: str, content: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}",
            "headers": self.get_headers(referer=referer, context_location="chat_input"),
            "json":    {"content": content, "flags": 0},
        }

    def delete_message(self, channel_id: str, message_id: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    None,
        }

    def add_reaction(self, channel_id: str, message_id: str, emoji: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    None,
        }

    def remove_reaction(self, channel_id: str, message_id: str, emoji: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    None,
        }

    def ack_message(self, channel_id: str, message_id: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}/ack",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    self.build_ack_payload(),
        }

    def start_typing(self, channel_id: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/typing",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    self.build_typing_payload(),
        }

    def pin_message(self, channel_id: str, message_id: str, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/pins/{message_id}",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    None,
        }

    def patch_avatar(self, image_bytes: bytes, mime: str = "image/png") -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me",
            "headers": self.get_headers(skip_context_props=True),
            "json":    {"avatar": self.build_avatar_data_uri(image_bytes, mime)},
        }

    def patch_banner(self, image_bytes: bytes, mime: str = "image/png") -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me",
            "headers": self.get_headers(skip_context_props=True),
            "json":    {"banner": self.build_avatar_data_uri(image_bytes, mime)},
        }

    def patch_profile(self, guild_id: str = None, **kwargs) -> Dict:
        if guild_id:
            url = f"https://discord.com/api/v9/guilds/{guild_id}/profile/@me"
        else:
            url = "https://discord.com/api/v9/users/@me/profile"
        return {
            "url":     url,
            "headers": self.get_headers(context_location="user_profile"),
            "json":    self.build_profile_payload(**kwargs),
        }

    def patch_username(self, username: str, password: str) -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me",
            "headers": self.get_headers(
                context_location="user_settings",
                referer="https://discord.com/channels/@me",
            ),
            "json":    {"username": username, "password": password},
        }

    def patch_status(self, status: str = None, custom: str = None, **kwargs) -> Dict:
        if not status:
            raise ValueError("Status cannot be None - must be set from actual Discord status")
        return {
            "url":     "https://discord.com/api/v9/users/@me/settings",
            "headers": self.get_headers(skip_context_props=True),
            "json":    self.build_status_payload(status, custom, **kwargs),
        }

    def patch_settings(self, settings_b64: str) -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me/settings-proto/1",
            "headers": self.get_headers(skip_context_props=True),
            "json":    self.build_settings_payload(settings_b64),
        }

    def get_settings(self) -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me/settings-proto/1",
            "headers": self.get_headers(skip_context_props=True),
        }

    def join_guild(self, invite_code: str) -> Dict:
        return {
            "url":     f"https://discord.com/api/v9/invites/{invite_code}",
            "headers": self.get_headers(
                context_location="join_guild",
                referer=f"https://discord.com/invite/{invite_code}",
            ),
            "json":    self.build_join_guild_payload(invite_code),
        }

    def leave_guild(self, guild_id: str) -> Dict:
        return {
            "url":     f"https://discord.com/api/v9/users/@me/guilds/{guild_id}",
            "headers": self.get_headers(skip_context_props=True),
            "json":    {"lurking": False},
        }

    def add_friend(self, username: str) -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me/relationships",
            "headers": self.get_headers(context_location="add_friend_navbar"),
            "json":    self.build_relationship_payload(username),
        }

    def remove_friend(self, user_id: str) -> Dict:
        return {
            "url":     f"https://discord.com/api/v9/users/@me/relationships/{user_id}",
            "headers": self.get_headers(skip_context_props=True),
            "json":    None,
        }

    def block_user(self, user_id: str) -> Dict:
        return {
            "url":     f"https://discord.com/api/v9/users/@me/relationships/{user_id}",
            "headers": self.get_headers(skip_context_props=True),
            "json":    {"type": 2},
        }

    def open_dm(self, user_id: str) -> Dict:
        return {
            "url":     "https://discord.com/api/v9/users/@me/channels",
            "headers": self.get_headers(context_location="dm_channel"),
            "json":    {"recipients": [user_id]},
        }

    def create_thread(
        self,
        channel_id: str,
        message_id: str,
        name: str,
        guild_id: str = None,
        **kwargs,
    ) -> Dict:
        referer = f"https://discord.com/channels/{guild_id or '@me'}/{channel_id}"
        return {
            "url":     f"https://discord.com/api/v9/channels/{channel_id}/messages/{message_id}/threads",
            "headers": self.get_headers(referer=referer, skip_context_props=True),
            "json":    self.build_thread_payload(name, **kwargs),
        }

    def post_science(self, events: List[Dict], referer: str = "https://discord.com/channels/@me") -> Dict:
        return {
            "url":     "https://discord.com/api/v9/science",
            "headers": self.get_science_headers(referer=referer),
            "json":    self.build_science_payload(events),
        }

    def get_messages(self, channel_id: str, limit: int = 50, before: str = None, guild_id: str = "@me") -> Dict:
        referer = f"https://discord.com/channels/{guild_id}/{channel_id}"
        url = f"https://discord.com/api/v9/channels/{channel_id}/messages?limit={limit}"
        if before:
            url += f"&before={before}"
        return {
            "url":     url,
            "headers": self.get_headers(referer=referer, skip_context_props=True),
        }

    def search_messages(
        self,
        guild_id: str   = None,
        channel_id: str = None,
        query: str      = None,
        author_id: str  = None,
        limit: int      = 25,
        offset: int     = 0,
    ) -> Dict:
        if guild_id:
            base = f"https://discord.com/api/v9/guilds/{guild_id}/messages/search"
            referer = f"https://discord.com/channels/{guild_id}"
        else:
            base = f"https://discord.com/api/v9/channels/{channel_id}/messages/search"
            referer = f"https://discord.com/channels/@me/{channel_id}"
        params = f"?limit={limit}&offset={offset}"
        if query:     params += f"&content={query}"
        if author_id: params += f"&author_id={author_id}"
        return {
            "url":     base + params,
            "headers": self.get_headers(referer=referer, skip_context_props=True),
        }

    def change_nickname(self, guild_id: str, nick: str) -> Dict:
        return {
            "url":     f"https://discord.com/api/v9/guilds/{guild_id}/members/@me",
            "headers": self.get_headers(
                referer=f"https://discord.com/channels/{guild_id}",
                skip_context_props=True,
            ),
            "json":    {"nick": nick},
        }

    def get_profile(self, user_id: str, guild_id: str = None) -> Dict:
        url = f"https://discord.com/api/v9/users/{user_id}/profile"
        if guild_id:
            url += f"?guild_id={guild_id}&with_mutual_guilds=true&with_mutual_friends_count=true"
        return {
            "url":     url,
            "headers": self.get_headers(context_location="user_profile"),
        }

    def create_app_external_assets(self, application_id: str, urls: Sequence[str]) -> Dict:
        """
        Create external assets for the application
        
        Parameters
        ----------
        application_id: str
            Discord application ID
        urls: Sequence[str]
            List of external asset URLs to proxy
        
        Returns
        --------
        Dict
            Response from Discord API
        """
        payload = {'urls': urls}
        
        response = self.session.post(
            f"https://discord.com/api/v10/applications/{application_id}/external-assets",
            headers=self.get_headers(skip_context_props=True),
            json=payload
        )
        
        response.raise_for_status()
        return response.json()

    def build_login_payload(
        self,
        login: str,
        password: str,
        undelete: bool       = False,
        login_source: str    = None,
        gift_code_sku_id: str = None,
    ) -> Dict:
        return {
            "login":            login,
            "password":         password,
            "undelete":         undelete,
            "login_source":     login_source,
            "gift_code_sku_id": gift_code_sku_id,
        }

    def login(
        self,
        login: str,
        password: str,
        redirect_to: str     = "/channels/@me",
        undelete: bool       = False,
        login_source: str    = None,
        gift_code_sku_id: str = None,
        captcha_key: str     = None,
        captcha_rqtoken: str = None,
    ) -> Dict:
        referer = f"https://discord.com/login?redirect_to={redirect_to}"
        fp, cookies = self.fetch_fingerprint()
        h = {
            "Content-Type":       "application/json",
            "User-Agent":         self.profile.user_agent,
            "Accept":             "*/*",
            "Accept-Language":    f"{self.profile.locale},en;q=0.9",
            "Accept-Encoding":    "gzip, deflate, br, zstd",
            "Origin":             "https://discord.com",
            "Referer":            referer,
            "Sec-Ch-Ua":          self._sec_ch_ua(),
            "Sec-Ch-Ua-Mobile":   "?0",
            "Sec-Ch-Ua-Platform": f'"{self.profile.os}"',
            "Sec-Fetch-Dest":     "empty",
            "Sec-Fetch-Mode":     "cors",
            "Sec-Fetch-Site":     "same-origin",
            "X-Debug-Options":    "bugReporterEnabled",
            "X-Discord-Locale":   self.profile.locale,
            "X-Discord-Timezone": self.profile.timezone,
            "X-Super-Properties": self._xsp(
                referrer_current=referer,
                referring_domain_current="discord.com",
            ),
            "X-Fingerprint":      fp,
            "Cookie":             cookies,
        }
        if captcha_key:
            h["X-Captcha-Key"] = captcha_key
        if captcha_rqtoken:
            h["X-Captcha-Rqtoken"] = captcha_rqtoken
        return {
            "url":     "https://discord.com/api/v9/auth/login",
            "headers": h,
            "json":    self.build_login_payload(login, password, undelete, login_source, gift_code_sku_id),
        }