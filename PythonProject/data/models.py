"""Data models for DeepFocus."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

@dataclass
class FocusSession:
    """Represents a single focus or break session."""
    id: Optional[int] = None
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    duration_minutes: int = 25
    completed: bool = False
    elapsed_seconds: Optional[float] = None
    outcome: str = ""
    mode_name: str = ""
    session_type: str = "focus"  # "focus", "short_break", "long_break"
    
    @property
    def actual_duration_seconds(self) -> float:
        """Calculate actual duration in seconds."""
        if self.elapsed_seconds is not None:
            return self.elapsed_seconds
        if self.end_time and self.start_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

@dataclass 
class BlockedItem:
    """Represents a blocked website or application."""
    id: Optional[int] = None
    name: str = ""
    item_type: str = "website"  # "website" or "app"
    value: str = ""  # URL for website, process name for app
    enabled: bool = True

@dataclass
class DailyStats:
    """Aggregated statistics for a single day."""
    date: str = ""  # YYYY-MM-DD format
    total_focus_minutes: int = 0
    total_sessions: int = 0
    completed_sessions: int = 0
    
    @property
    def focus_hours(self) -> float:
        """Get total focus time in hours."""
        return self.total_focus_minutes / 60.0
    
    @property  
    def completion_rate(self) -> float:
        """Get the session completion rate as a percentage."""
        if self.total_sessions == 0:
            return 0.0
        return round(self.completed_sessions / self.total_sessions * 100.0, 1)

@dataclass
class FocusMode:
    """Represents a focus mode configuration."""
    id: Optional[int] = None
    name: str = "Default"
    focus_minutes: int = 25
    short_break_minutes: int = 5
    long_break_minutes: int = 15
    sessions_before_long_break: int = 4
    blocked_sites: str = "[]"    # JSON array of site strings
    blocked_apps: str = "[]"     # JSON array of app strings
    dead_lock: bool = False      # Cannot unswitch blocking before timer ends
    notifications: bool = True   # Show break/session notifications
    is_default: bool = False     # True for the built-in Default mode
    auto_flow: bool = False      # Automatically start next phase
    whitelist_mode: bool = False # Use hardcore whitelist blocking
    target_goal: int = 4         # Target number of sessions
    auto_sound: str = "none"     # Sound to auto-play when focus starts
    auto_sound_volume: float = 0.5 # Volume of auto-played sound

@dataclass
class CustomSound:
    """Represents a user-imported custom sound."""
    id: Optional[int] = None
    name: str = ""
    icon: str = "🎵"
    file_path: str = ""
