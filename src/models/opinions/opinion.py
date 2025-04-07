"""
Opinion Model

This module provides the data model for opinion tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field


@dataclass
class Opinion:
    """Model representing an opinion expressed in a podcast episode."""
    
    id: str  # Unique identifier for the opinion
    title: str  # Short title/summary of the opinion
    description: str  # Longer description of the opinion
    content: str  # The actual text of the opinion as expressed
    
    # Speaker information
    speaker_id: str  # ID of the speaker expressing the opinion
    speaker_name: str  # Name of the speaker
    
    # Episode information
    episode_id: str  # ID of the episode where the opinion was expressed
    episode_title: str  # Title of the episode
    
    # Timestamps
    start_time: float  # Start timestamp in seconds
    end_time: float  # End timestamp in seconds
    date: datetime  # Date of the episode
    
    # Metadata
    keywords: List[str] = field(default_factory=list)  # Keywords associated with this opinion
    sentiment: Optional[float] = None  # Sentiment score of the opinion (-1 to 1)
    confidence: float = 0.0  # Confidence score for opinion detection
    category: Optional[str] = None  # Category or topic of the opinion
    
    # Tracking over time
    related_opinions: List[str] = field(default_factory=list)  # IDs of related opinions
    evolution_notes: Optional[str] = None  # Notes on how this opinion has evolved
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Opinion to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "content": self.content,
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "episode_id": self.episode_id,
            "episode_title": self.episode_title,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "date": self.date.isoformat() if self.date else None,
            "keywords": self.keywords,
            "sentiment": self.sentiment,
            "confidence": self.confidence,
            "category": self.category,
            "related_opinions": self.related_opinions,
            "evolution_notes": self.evolution_notes,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Opinion':
        """Create Opinion from dictionary."""
        # Handle datetime conversion
        date = data.get("date")
        if date and isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif date is None:
            date = datetime.now()
            
        return cls(
            id=data["id"],
            title=data["title"],
            description=data["description"],
            content=data["content"],
            speaker_id=data["speaker_id"],
            speaker_name=data["speaker_name"],
            episode_id=data["episode_id"],
            episode_title=data["episode_title"],
            start_time=data["start_time"],
            end_time=data["end_time"],
            date=date,
            keywords=data.get("keywords", []),
            sentiment=data.get("sentiment"),
            confidence=data.get("confidence", 0.0),
            category=data.get("category"),
            related_opinions=data.get("related_opinions", []),
            evolution_notes=data.get("evolution_notes"),
            metadata=data.get("metadata", {})
        ) 