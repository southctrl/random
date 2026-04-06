import logging
from typing import Dict, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Activity:
    """Base activity class for Discord presence"""
    name: str
    type: int = 0
    details: Optional[str] = None
    state: Optional[str] = None
    platform: Optional[str] = None
    timestamps: Optional[Dict[str, int]] = None
    assets: Optional[Dict[str, str]] = None
    buttons: Optional[list[Dict[str, str]]] = None


class PresenceManager:
    """Manages Discord presence activities and status"""
    
    def __init__(self):
        self.current_activity: Optional[Activity] = None
        self.current_status: str = None 
        
    def create_rich_presence(
        self,
        name: str,
        platform: Optional[str] = None,
        details: Optional[str] = None,
        state: Optional[str] = None,
        large_image_url: Optional[str] = None,
        large_text: Optional[str] = None,
        small_image_url: Optional[str] = None,
        small_text: Optional[str] = None,
        start: Optional[int] = None,
        end: Optional[int] = None,
        button1_label: Optional[str] = None,
        button1_url: Optional[str] = None,
        button2_label: Optional[str] = None,
        button2_url: Optional[str] = None
    ) -> Activity:
        """Create a rich presence activity"""
        
        assets = None
        if any([large_image_url, large_text, small_image_url, small_text]):
            assets = {}
            if large_image_url:
                assets["large_image"] = large_image_url
            if large_text:
                assets["large_text"] = large_text
            if small_image_url:
                assets["small_image"] = small_image_url
            if small_text:
                assets["small_text"] = small_text
                
        timestamps = None
        if start or end:
            timestamps = {}
            if start:
                timestamps["start"] = start
            if end:
                timestamps["end"] = end
                
        buttons = None
        if (button1_label and button1_url) or (button2_label and button2_url):
            buttons = []
            if button1_label and button1_url:
                buttons.append({"label": button1_label, "url": button1_url})
                
            if button2_label and button2_url:
                buttons.append({"label": button2_label, "url": button2_url})
                
        activity = Activity(
            name=name,
            type=0,
            details=details,
            state=state,
            platform=platform,
            timestamps=timestamps,
            assets=assets,
            buttons=buttons
        )
        
        self.current_activity = activity
        return activity
        
    def create_spotify_presence(
        self,
        title: str,
        artists: list[str],
        album: str,
        album_cover_url: str,
        track_id: str,
        duration_ms: int,
        start_ms: int = 0
    ) -> Activity:
        """Create a Spotify listening activity"""
        
        activity = Activity(
            name="Spotify",
            type=2,
            details=title,
            state=f"by {', '.join(artists)}",
            assets={
                "large_image": album_cover_url,
                "large_text": album
            },
            timestamps={
                "start": int(start_ms / 1000),
                "end": int((start_ms + duration_ms) / 1000)
            }
        )
        
        self.current_activity = activity
        return activity
        
    def create_custom_status(
        self,
        text: Optional[str] = None,
        emoji: Optional[str] = None
    ) -> Activity:
        """Create a custom status activity"""
        
        state = None
        if emoji and text:
            state = f"{emoji} {text}"
        elif emoji:
            state = emoji
        elif text:
            state = text
            
        activity = Activity(
            name=text or "Custom Status",
            type=4,
            state=state
        )
        
        self.current_activity = activity
        return activity
        
    def create_streaming_presence(
        self,
        name: str,
        details: Optional[str] = None,
        twitch_url: Optional[str] = None
    ) -> Activity:
        """Create a streaming activity"""
        
        activity = Activity(
            name=name,
            type=1,
            details=details,
            url=twitch_url
        )
        
        self.current_activity = activity
        return activity
        
    def clear_activity(self) -> None:
        """Clear current activity"""
        self.current_activity = None
        
    def set_status(self, status: str) -> None:
        """Set user status"""
        valid_statuses = ["online", "idle", "dnd", "invisible"]
        if status in valid_statuses:
            self.current_status = status
        else:
            logger.warning(f"Invalid status: {status}")
            
    def get_presence_payload(self) -> Dict[str, Any]:
        """Get presence payload for Discord gateway"""
        
        activities = []
        if self.current_activity:
            activity_dict = {
                "name": self.current_activity.name,
                "type": self.current_activity.type
            }
            
            if self.current_activity.details:
                activity_dict["details"] = self.current_activity.details
            if self.current_activity.state:
                activity_dict["state"] = self.current_activity.state
            if self.current_activity.platform:
                activity_dict["platform"] = self.current_activity.platform
            if self.current_activity.timestamps:
                activity_dict["timestamps"] = self.current_activity.timestamps
            if self.current_activity.assets:
                activity_dict["assets"] = self.current_activity.assets
            if self.current_activity.buttons:
                activity_dict["buttons"] = self.current_activity.buttons
                
            activities.append(activity_dict)
            
        return {
            "since": None,
            "activities": activities,
            "status": self.current_status,
            "afk": False
        }
        
    def get_activity_dict(self) -> Optional[Dict[str, Any]]:
        """Get current activity as dictionary"""
        if not self.current_activity:
            return None
            
        return {
            "name": self.current_activity.name,
            "type": self.current_activity.type,
            "details": self.current_activity.details,
            "state": self.current_activity.state,
            "platform": self.current_activity.platform,
            "timestamps": self.current_activity.timestamps,
            "assets": self.current_activity.assets,
            "buttons": self.current_activity.buttons
        }
