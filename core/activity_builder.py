"""
Activity building utilities inspired by discord.py-self.
Provides helpers to construct Discord activity payloads for rich presence, custom status, and Spotify.
"""

import datetime
from typing import Any, Dict, List, Optional, Sequence, Union

from .activity_assets import parse_activity_asset


class ActivityTimestamps:
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActivityTimestamps":
        return cls(
            start=datetime.datetime.fromtimestamp(data["start"] / 1000) if data.get("start") else None,
            end=datetime.datetime.fromtimestamp(data["end"] / 1000) if data.get("end") else None,
        )

    def __init__(
        self,
        *,
        start: Optional[datetime.datetime] = None,
        end: Optional[datetime.datetime] = None,
    ) -> None:
        self.start = start
        self.end = end

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}
        if self.start:
            ret["start"] = int(self.start.timestamp() * 1000)
        if self.end:
            ret["end"] = int(self.end.timestamp() * 1000)
        return ret


class ActivityAssets:
    def __init__(
        self,
        *,
        large_image: Optional[Union[str, int]] = None,
        large_text: Optional[str] = None,
        large_url: Optional[str] = None,
        small_image: Optional[Union[str, int]] = None,
        small_text: Optional[str] = None,
        small_url: Optional[str] = None,
    ) -> None:
        self.large_image = parse_activity_asset(large_image) if large_image else None
        self.large_text = large_text
        self.large_url = large_url
        self.small_image = parse_activity_asset(small_image) if small_image else None
        self.small_text = small_text
        self.small_url = small_url

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}
        if self.large_image:
            ret["large_image"] = self.large_image
        if self.large_text:
            ret["large_text"] = self.large_text
        if self.large_url:
            ret["large_url"] = self.large_url
        if self.small_image:
            ret["small_image"] = self.small_image
        if self.small_text:
            ret["small_text"] = self.small_text
        if self.small_url:
            ret["small_url"] = self.small_url
        return ret


class ActivityParty:
    def __init__(
        self,
        *,
        id: Optional[str] = None,
        current_size: Optional[int] = None,
        max_size: Optional[int] = None,
    ) -> None:
        self.id = id
        if (current_size is None) != (max_size is None):
            raise ValueError("current_size and max_size must be provided together")
        self.current_size = current_size
        self.max_size = max_size

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}
        if self.id:
            ret["id"] = self.id
        if self.current_size is not None and self.max_size is not None:
            ret["size"] = [self.current_size, self.max_size]
        return ret


class ActivityButton:
    def __init__(self, label: str, url: Optional[str] = None):
        self.label = label
        self.url = url

    def to_dict(self) -> Dict[str, str]:
        return {"label": self.label, "url": self.url} if self.url else {"label": self.label}


class ActivitySecrets:
    def __init__(
        self,
        *,
        join: Optional[str] = None,
        spectate: Optional[str] = None,
    ) -> None:
        self.join = join
        self.spectate = spectate

    def to_dict(self) -> Dict[str, Any]:
        ret: Dict[str, Any] = {}
        if self.join:
            ret["join"] = self.join
        if self.spectate:
            ret["spectate"] = self.spectate
        return ret


def build_rich_presence(
    *,
    name: str,
    type: int,
    details: Optional[str] = None,
    state: Optional[str] = None,
    platform: Optional[str] = None,
    timestamps: Optional[ActivityTimestamps] = None,
    assets: Optional[ActivityAssets] = None,
    party: Optional[ActivityParty] = None,
    buttons: Optional[Sequence[Union[ActivityButton, str]]] = None,
    secrets: Optional[ActivitySecrets] = None,
    url: Optional[str] = None,
    application_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Construct a Discord rich presence activity payload."""
    activity: Dict[str, Any] = {
        "name": name,
        "type": type,
    }

    if details:
        activity["details"] = details
    if state:
        activity["state"] = state
    if url:
        activity["url"] = url
    if application_id:
        activity["application_id"] = application_id

    if platform:
        platform_map = {
            "ps5": "ps5",
            "xbox": "xbox",
            "pc": "desktop",
            "switch": "nintendo",
            "mobile": "android",
        }
        activity["platform"] = platform_map.get(platform.lower(), platform)

    if timestamps:
        ts = timestamps.to_dict()
        if ts:
            activity["timestamps"] = ts

    if assets:
        asset_dict = assets.to_dict()
        if asset_dict:
            activity["assets"] = asset_dict

    if party:
        party_dict = party.to_dict()
        if party_dict:
            activity["party"] = party_dict

    if buttons:
        btns = []
        btn_urls = []
        for btn in buttons:
            if isinstance(btn, ActivityButton):
                btns.append(btn.label)
                if btn.url:
                    btn_urls.append(btn.url)
            else:
                btns.append(str(btn))
        if btns:
            activity["buttons"] = btns
            if btn_urls:
                activity["metadata"] = {
                    "button_urls": btn_urls
                }

    if secrets:
        sec = secrets.to_dict()
        if sec:
            activity["secrets"] = sec

    return activity


def build_custom_status(
    *,
    text: Optional[str] = None,
    emoji: Optional[str] = None,
) -> Dict[str, Any]:
    """Construct a Discord custom status activity payload."""
    activity: Dict[str, Any] = {
        "name": "Custom Status",
        "type": 4,
    }

    if text:
        activity["state"] = text

    if emoji:
        if emoji.startswith("<") and emoji.endswith(">") and ":" in emoji:
            inner = emoji[1:-1]
            parts = inner.split(":")
            animated = False
            if parts and parts[0] == "a":
                animated = True
                parts = parts[1:]
            if len(parts) >= 2:
                name, emoji_id = parts[0], parts[1]
                activity["emoji"] = {"name": name, "id": emoji_id, "animated": animated}
            else:
                activity["emoji"] = {"name": emoji, "id": None}
        else:
            activity["emoji"] = {"name": emoji, "id": None}

    return activity


def build_spotify_activity(
    *,
    title: str,
    artists: Sequence[str],
    album: Optional[str] = None,
    album_cover_url: Optional[str] = None,
    start_time: Optional[datetime.datetime] = None,
    duration: datetime.timedelta,
    track_id: Optional[str] = None,
    party_owner_id: int,
) -> Dict[str, Any]:
    """Construct a Spotify listening activity payload."""
    assets = ActivityAssets(
        large_image=album_cover_url,
        large_text=album,
    )

    start = start_time or datetime.datetime.utcnow()
    timestamps = ActivityTimestamps(start=start, end=start + duration)

    party = ActivityParty(id=f"spotify:{party_owner_id}")

    activity: Dict[str, Any] = {
        "type": 2,
        "name": "Spotify",
        "details": title,
        "state": "; ".join([artist.replace(";", "") for artist in list(artists)[:5]]),
        "sync_id": track_id,
        "timestamps": timestamps.to_dict(),
        "assets": assets.to_dict(),
        "party": party.to_dict(),
        "flags": (1 << 2) | (1 << 0) if track_id else 0,
    }

    return activity
