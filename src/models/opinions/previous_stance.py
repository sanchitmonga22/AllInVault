"""
Previous Stance Model

This module provides the data model for tracking a speaker's previous stance on an opinion.
Key features:
- PreviousStance extends SpeakerStance to track historical stances
- Contains metadata about when and why a stance changed
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid

from .opinion import SpeakerStance


@dataclass
class PreviousStance(SpeakerStance):
    """Model representing a speaker's previous stance on an opinion."""
    
    episode_id: str = ""  # ID of the episode where this stance was held
    episode_title: str = ""  # Title of the episode where this stance was held
    date: Optional[datetime] = None  # Date when this stance was held
    changed_in_episode_id: Optional[str] = None  # Episode where stance changed
    changed_at: Optional[datetime] = None  # When the stance changed
    change_reason: Optional[str] = None  # Why the stance changed
    next_stance: Optional[str] = None  # What the stance changed to
    
    def __post_init__(self):
        """Normalize date to ensure consistent timezone handling."""
        # Convert timezone-aware datetime to naive datetime
        if self.date and hasattr(self.date, 'tzinfo') and self.date.tzinfo is not None:
            self.date = self.date.replace(tzinfo=None)
            
        if self.changed_at and hasattr(self.changed_at, 'tzinfo') and self.changed_at.tzinfo is not None:
            self.changed_at = self.changed_at.replace(tzinfo=None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        # Get the base speaker stance dict
        base_dict = super().to_dict()
        
        # Add previous stance specific fields
        previous_stance_dict = {
            "episode_id": self.episode_id,
            "episode_title": self.episode_title,
            "date": self.date.isoformat() if self.date else None,
            "changed_in_episode_id": self.changed_in_episode_id,
            "changed_at": self.changed_at.isoformat() if self.changed_at else None,
            "change_reason": self.change_reason,
            "next_stance": self.next_stance
        }
        
        # Combine and return
        return {**base_dict, **previous_stance_dict}
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PreviousStance':
        """Create from dictionary."""
        # Handle datetime conversion for date
        date = data.get("date")
        if date and isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
                # Normalize to naive datetime
                if hasattr(date, 'tzinfo') and date.tzinfo is not None:
                    date = date.replace(tzinfo=None)
            except ValueError:
                date = None
                
        # Handle datetime conversion for changed_at
        changed_at = data.get("changed_at")
        if changed_at and isinstance(changed_at, str):
            try:
                changed_at = datetime.fromisoformat(changed_at)
                # Normalize to naive datetime
                if hasattr(changed_at, 'tzinfo') and changed_at.tzinfo is not None:
                    changed_at = changed_at.replace(tzinfo=None)
            except ValueError:
                changed_at = None
        
        return cls(
            speaker_id=data["speaker_id"],
            speaker_name=data["speaker_name"],
            stance=data.get("stance", "support"),
            reasoning=data.get("reasoning"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time"),
            episode_id=data.get("episode_id", ""),
            episode_title=data.get("episode_title", ""),
            date=date,
            changed_in_episode_id=data.get("changed_in_episode_id"),
            changed_at=changed_at,
            change_reason=data.get("change_reason"),
            next_stance=data.get("next_stance")
        )
    
    @classmethod
    def from_speaker_stance(cls, 
                           stance: SpeakerStance, 
                           episode_id: str, 
                           episode_title: str, 
                           date: datetime,
                           changed_in_episode_id: Optional[str] = None,
                           changed_at: Optional[datetime] = None,
                           change_reason: Optional[str] = None,
                           next_stance: Optional[str] = None) -> 'PreviousStance':
        """Create a PreviousStance from a SpeakerStance."""
        return cls(
            speaker_id=stance.speaker_id,
            speaker_name=stance.speaker_name,
            stance=stance.stance,
            reasoning=stance.reasoning,
            start_time=stance.start_time,
            end_time=stance.end_time,
            episode_id=episode_id,
            episode_title=episode_title,
            date=date,
            changed_in_episode_id=changed_in_episode_id,
            changed_at=changed_at,
            change_reason=change_reason,
            next_stance=next_stance
        ) 