"""
Handles Discord CDN/media URL conversion and external asset proxying for rich presence.
"""

import re
from typing import Optional, Union

MP_REGEX = re.compile(r'https?://(?:cdn|media|images-ext-\d+)\.discordapp\.(?:com|net)/(.+)')
TWITCH_REGEX = re.compile(r'https?://static-cdn\.jtvnw\.net/previews-ttv/live_user_(.+?)(?:-(\d+)x(\d+))?\.jpg')
YOUTUBE_REGEX = re.compile(r'https?://i\.ytimg\.com/vi/(.+?)/(.+?)\.jpg')
SPOTIFY_REGEX = re.compile(r'https?://i\.scdn\.co/image/(.+)')

def parse_activity_asset(asset: Optional[Union[str, int]]) -> Optional[str]:
    """
    Parse a raw asset value for Discord activity assets.
    - If it's a Discord CDN/media URL, convert to mp: prefix.
    - If it's a recognized Twitch/YouTube/Spotify URL, convert to respective prefix.
    - Otherwise, return the value unchanged (allow external URLs or asset keys).
    """
    if not asset:
        return None

    if isinstance(asset, int):
        return str(asset)

    asset = str(asset)

    m = MP_REGEX.match(asset)
    if m:
        path = m.group(1).split('?')[0]
        return f'mp:{path}'

    m = TWITCH_REGEX.match(asset)
    if m:
        return f'twitch:{m.group(1)}'

    m = YOUTUBE_REGEX.match(asset)
    if m:
        return f'youtube:{m.group(1)}'

    m = SPOTIFY_REGEX.match(asset)
    if m:
        return f'spotify:{m.group(1)}'

    return asset

def is_external_url(url: str) -> bool:
    """Check if a URL is external (not Discord CDN) and needs proxying."""
    if not url or not isinstance(url, str):
        return False
    
    if MP_REGEX.match(url) or url.startswith("mp:"):
        return False
    
    return url.startswith(('http://', 'https://'))

"""
Activity Assets Module

This module handles Discord activity assets including images, text, and other visual elements
for rich presence activities.
"""

from typing import Optional, Dict, Any
from dataclasses import dataclass


@dataclass
class ActivityAssets:
    """Discord activity assets for rich presence"""
    
    large_image: Optional[str] = None
    large_text: Optional[str] = None
    
    small_image: Optional[str] = None
    small_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format"""
        assets = {}
        
        if self.large_image:
            assets["large_image"] = self.large_image
                
        if self.large_text:
            assets["large_text"] = self.large_text
            
        if self.small_image:
            assets["small_image"] = self.small_image
                
        if self.small_text:
            assets["small_text"] = self.small_text
            
        return assets
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ActivityAssets":
        """Create from dictionary"""
        return cls(
            large_image=data.get("large_image"),
            large_text=data.get("large_text"),
            small_image=data.get("small_image"),
            small_text=data.get("small_text")
        )


class AssetBuilder:
    """Builder for creating activity assets"""
    
    def __init__(self):
        self.large_image = None
        self.large_text = None
        self.small_image = None
        self.small_text = None
    
    def with_large_image(self, image: str, text: str = None) -> "AssetBuilder":
        """Set large image and optional text"""
        self.large_image = image
        self.large_text = text
        return self
    
    def with_small_image(self, image: str, text: str = None) -> "AssetBuilder":
        """Set small image and optional text"""
        self.small_image = image
        self.small_text = text
        return self
    
    def build(self) -> ActivityAssets:
        """Build the assets object"""
        return ActivityAssets(
            large_image=self.large_image,
            large_text=self.large_text,
            small_image=self.small_image,
            small_text=self.small_text
        )

"""
Activity Builder Module

This module provides a fluent builder interface for creating Discord activities
with proper validation and structure for rich presence based on Discord's official API.
"""

from typing import Optional, List, Dict, Any, Literal, Union
from dataclasses import dataclass
from datetime import datetime


@dataclass
class ActivityTimestamps:
    """Activity timestamps for start/end times"""
    
    start: Optional[int] = None
    end: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format"""
        timestamps = {}
        if self.start is not None:
            timestamps["start"] = self.start
        if self.end is not None:
            timestamps["end"] = self.end
        return timestamps if timestamps else None


@dataclass
class ActivityButton:
    """Activity button for rich presence"""
    
    label: str
    url: str
    
    def to_dict(self) -> Dict[str, str]:
        """Convert to Discord API format"""
        return {
            "label": self.label,
            "url": self.url
        }


@dataclass
class ActivityAssets:
    """Discord activity assets for rich presence"""
    
    large_image: Optional[str] = None
    large_text: Optional[str] = None
    small_image: Optional[str] = None
    small_text: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format"""
        assets = {}
        
        if self.large_image:
            assets["large_image"] = self.large_image
        if self.large_text:
            assets["large_text"] = self.large_text
        if self.small_image:
            assets["small_image"] = self.small_image
        if self.small_text:
            assets["small_text"] = self.small_text
            
        return assets if assets else None


@dataclass
class ActivityParty:
    """Discord activity party information"""
    
    id: Optional[str] = None
    size: Optional[List[int]] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format"""
        party = {}
        if self.id:
            party["id"] = self.id
        if self.size:
            party["size"] = self.size
        return party if party else None


@dataclass
class ActivitySecrets:
    """Discord activity secrets for join functionality"""
    
    join: Optional[str] = None
    spectate: Optional[str] = None
    match: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord API format"""
        secrets = {}
        if self.join:
            secrets["join"] = self.join
        if self.spectate:
            secrets["spectate"] = self.spectate
        if self.match:
            secrets["match"] = self.match
        return secrets if secrets else None


@dataclass
class ActivityFlags:
    """Discord activity flags (INSTANCE, JOIN, SPECTATE, JOIN_REQUEST)"""
    
    instance: bool = False
    join: bool = False
    spectate: bool = False
    join_request: bool = False
    
    def to_int(self) -> int:
        """Convert flags to integer"""
        flags = 0
        if self.instance:
            flags |= (1 << 0)
        if self.join:
            flags |= (1 << 1)
        if self.spectate:
            flags |= (1 << 2)
        if self.join_request:
            flags |= (1 << 3)
        return flags


@dataclass
class Activity:
    """Complete Discord Activity for rich presence based on official Discord API"""
    
    name: str
    type: int = 0
    platform: Optional[str] = None
    url: Optional[str] = None
    details: Optional[str] = None
    state: Optional[str] = None
    timestamps: Optional[ActivityTimestamps] = None
    assets: Optional[ActivityAssets] = None
    buttons: Optional[List[ActivityButton]] = None
    party: Optional[ActivityParty] = None
    secrets: Optional[ActivitySecrets] = None
    flags: Optional[ActivityFlags] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to Discord Gateway format according to Discord documentation"""
        activity = {
            "name": self.name,
            "type": self.type
        }
        
        if self.url and self.url.strip():
            activity["url"] = self.url
        if self.details and self.details.strip():
            activity["details"] = self.details
        if self.state and self.state.strip():
            activity["state"] = self.state
        if self.platform and self.platform.strip():
            activity["platform"] = self.platform
            
        if self.timestamps:
            timestamps_dict = self.timestamps.to_dict()
            if timestamps_dict:
                activity["timestamps"] = timestamps_dict
                
        if self.assets:
            assets_dict = self.assets.to_dict()
            if assets_dict:
                activity["assets"] = assets_dict
                
        if self.buttons:
            activity["buttons"] = [button.to_dict() for button in self.buttons]
            
        if self.party:
            party_dict = self.party.to_dict()
            if party_dict:
                activity["party"] = party_dict
                
        if self.secrets:
            secrets_dict = self.secrets.to_dict()
            if secrets_dict:
                activity["secrets"] = secrets_dict
                
        if self.flags:
            activity["flags"] = self.flags.to_int()
            
        return activity


class ActivityBuilder:
    """Fluent builder for creating Discord activities"""
    
    def __init__(self, name: str):
        self.name = name
        self.type = 0
        self.url = None
        self.details = None
        self.state = None
        self.platform = None
        self.timestamps = None
        self.assets = None
        self.buttons = []
        self.party = None
        self.secrets = None
        self.flags = None
        
    def with_type(self, activity_type: int) -> "ActivityBuilder":
        """Set activity type"""
        self.type = activity_type
        return self
    
    def with_platform(self, platform: str) -> "ActivityBuilder":
        """Set platform for console-specific presence"""
        self.platform = platform
        return self
    
    def with_url(self, url: str) -> "ActivityBuilder":
        """Set activity URL (for streaming)"""
        self.url = url
        return self
    
    def with_details(self, details: str) -> "ActivityBuilder":
        """Set activity details"""
        self.details = details
        return self
    
    def with_state(self, state: str) -> "ActivityBuilder":
        """Set activity state"""
        self.state = state
        return self
    
    def with_timestamps(self, start: int = None, end: int = None) -> "ActivityBuilder":
        """Set timestamps"""
        self.timestamps = ActivityTimestamps(start=start, end=end)
        return self
    
    def with_elapsed_time(self, start_time: datetime) -> "ActivityBuilder":
        """Set elapsed time from start time to now"""
        self.timestamps = ActivityTimestamps(
            start=int(start_time.timestamp() * 1000)
        )
        return self
    
    def with_assets(self, assets: ActivityAssets) -> "ActivityBuilder":
        """Set activity assets"""
        self.assets = assets
        return self
    
    def with_large_image(self, image: str, text: str = None) -> "ActivityBuilder":
        """Set large image asset"""
        if not self.assets:
            self.assets = ActivityAssets()
        self.assets.large_image = image
        if text:
            self.assets.large_text = text
        return self
    
    def with_small_image(self, image: str, text: str = None) -> "ActivityBuilder":
        """Set small image asset"""
        if not self.assets:
            self.assets = ActivityAssets()
        self.assets.small_image = image
        if text:
            self.assets.small_text = text
        return self
    
    def add_button(self, label: str, url: str) -> "ActivityBuilder":
        """Add a button to Activity"""
        self.buttons.append(ActivityButton(label=label, url=url))
        return self
    
    def with_buttons(self, buttons: List[ActivityButton]) -> "ActivityBuilder":
        """Set multiple buttons"""
        self.buttons = buttons
        return self
    
    def with_party(self, party: ActivityParty) -> "ActivityBuilder":
        """Set party information"""
        self.party = party
        return self
    
    def with_secrets(self, secrets: ActivitySecrets) -> "ActivityBuilder":
        """Set Activity secrets for join functionality"""
        self.secrets = secrets
        return self
    
    def with_flags(self, flags: ActivityFlags) -> "ActivityBuilder":
        """Set Activity flags"""
        self.flags = flags
        return self
    
    def build(self) -> Activity:
        """Builds the Activity object"""
        return Activity(
            name=self.name,
            type=self.type,
            platform=self.platform,
            url=self.url,
            details=self.details,
            state=self.state,
            timestamps=self.timestamps,
            assets=self.assets,
            buttons=self.buttons if self.buttons else None,
            party=self.party,
            secrets=self.secrets,
            flags=self.flags
        )


class ActivityFactory:
    """Factory for creating common Activity types"""
    
    @staticmethod
    def playing(name: str) -> ActivityBuilder:
        """Create a 'Playing' activity"""
        return ActivityBuilder(name).with_type(0)
    
    @staticmethod
    def streaming(name: str) -> ActivityBuilder:
        """Create a 'Streaming' Activity"""
        return ActivityBuilder(name).with_type(1)
    
    @staticmethod
    def listening(name: str) -> ActivityBuilder:
        """Create a 'Listening' Activity"""
        return ActivityBuilder(name).with_type(2)
    
    @staticmethod
    def watching(name: str) -> ActivityBuilder:
        """Create a 'Watching' Activity"""
        return ActivityBuilder(name).with_type(3)
    
    @staticmethod
    def competing(name: str) -> ActivityBuilder:
        """Create a 'Competing' Activity"""
        return ActivityBuilder(name).with_type(5)
    
    @staticmethod
    def custom_status() -> ActivityBuilder:
        """Create a custom status Activity"""
        return ActivityBuilder("Custom Status").with_type(0)