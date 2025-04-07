"""
Opinion Model

This module provides the data model for opinion tracking.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field


@dataclass
class Opinion:
    """Model representing an opinion expressed in a podcast episode."""
    
    id: str  # Unique identifier for the opinion
    title: str  # Short title/summary of the opinion
    description: str  # Longer description of the opinion
    content: str  # The actual text of the opinion as expressed
    
    # Speaker information
    speaker_id: str  # ID of the primary speaker expressing the opinion
    speaker_name: str  # Name of the speaker(s) - may include multiple names for shared opinions
    
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
    category_id: Optional[str] = None  # ID of the category for this opinion
    
    # Tracking over time
    related_opinions: List[str] = field(default_factory=list)  # IDs of related opinions
    evolution_notes: Optional[str] = None  # Notes on how this opinion has evolved
    
    # Evolution tracking
    original_opinion_id: Optional[str] = None  # ID of the first opinion in this evolution chain
    evolution_chain: List[str] = field(default_factory=list)  # Chronological chain of opinion IDs in this evolution
    
    # Additional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    # Contradiction and agreement tracking
    is_contradiction: bool = False  # Whether this opinion contradicts another opinion
    contradicts_opinion_id: Optional[str] = None  # ID of the opinion this contradicts
    contradiction_notes: Optional[str] = None  # Notes about the contradiction
    
    # Cross-episode tracking
    appeared_in_episodes: List[str] = field(default_factory=list)  # List of episode IDs where this opinion appeared
    
    # Per-speaker timestamps and positions
    speaker_timestamps: Dict[str, Dict[str, Any]] = field(default_factory=dict)  # Map of speaker_id -> {start_time, end_time, position, stance}
    
    def is_multi_speaker(self) -> bool:
        """Check if this opinion is shared by multiple speakers."""
        return "is_multi_speaker" in self.metadata and self.metadata["is_multi_speaker"]
    
    def get_all_speaker_ids(self) -> List[str]:
        """Get all speaker IDs associated with this opinion."""
        if self.speaker_timestamps:
            return list(self.speaker_timestamps.keys())
        if self.is_multi_speaker() and "all_speaker_ids" in self.metadata:
            return self.metadata["all_speaker_ids"]
        return [self.speaker_id]
    
    def get_all_speaker_names(self) -> List[str]:
        """Get all speaker names associated with this opinion."""
        if "," in self.speaker_name:
            return [name.strip() for name in self.speaker_name.split(",")]
        return [self.speaker_name]
    
    def get_speaker_stance(self, speaker_id: str) -> str:
        """Get a speaker's stance on this opinion (support, oppose, neutral)."""
        if speaker_id in self.speaker_timestamps and "stance" in self.speaker_timestamps[speaker_id]:
            return self.speaker_timestamps[speaker_id]["stance"]
        return "unknown"
    
    def get_speaker_timing(self, speaker_id: str) -> Dict[str, float]:
        """Get a speaker's timing for this opinion."""
        if speaker_id in self.speaker_timestamps:
            return {
                "start_time": self.speaker_timestamps[speaker_id].get("start_time", 0.0),
                "end_time": self.speaker_timestamps[speaker_id].get("end_time", 0.0)
            }
        return {"start_time": self.start_time, "end_time": self.end_time}
    
    def add_episode_occurrence(self, episode_id: str, episode_title: str) -> None:
        """Add an episode occurrence to this opinion."""
        if episode_id not in self.appeared_in_episodes:
            self.appeared_in_episodes.append(episode_id)
            if "episode_occurrences" not in self.metadata:
                self.metadata["episode_occurrences"] = {}
            self.metadata["episode_occurrences"][episode_id] = {
                "title": episode_title,
                "date": datetime.now().isoformat()
            }
    
    def is_contentious(self) -> bool:
        """Check if this opinion has disagreement among speakers."""
        stances = set()
        for speaker_data in self.speaker_timestamps.values():
            if "stance" in speaker_data:
                stances.add(speaker_data["stance"])
        # If we have both support and oppose stances, it's contentious
        return "support" in stances and "oppose" in stances
    
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
            "category_id": self.category_id,
            "related_opinions": self.related_opinions,
            "evolution_notes": self.evolution_notes,
            "original_opinion_id": self.original_opinion_id,
            "evolution_chain": self.evolution_chain,
            "is_contradiction": self.is_contradiction,
            "contradicts_opinion_id": self.contradicts_opinion_id,
            "contradiction_notes": self.contradiction_notes,
            "appeared_in_episodes": self.appeared_in_episodes,
            "speaker_timestamps": self.speaker_timestamps,
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
        
        # Handle legacy "category" field
        category_id = data.get("category_id")
        category = data.get("category")
        
        # If category_id is missing but category exists, use the category string
        if category_id is None and category is not None:
            category_id = category
            
        # Create the basic opinion object
        opinion = cls(
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
            category_id=category_id,
            related_opinions=data.get("related_opinions", []),
            evolution_notes=data.get("evolution_notes"),
            original_opinion_id=data.get("original_opinion_id"),
            evolution_chain=data.get("evolution_chain", []),
            is_contradiction=data.get("is_contradiction", False),
            contradicts_opinion_id=data.get("contradicts_opinion_id"),
            contradiction_notes=data.get("contradiction_notes"),
            appeared_in_episodes=data.get("appeared_in_episodes", []),
            speaker_timestamps=data.get("speaker_timestamps", {}),
            metadata=data.get("metadata", {})
        )
        
        # If this is a legacy opinion with no appeared_in_episodes, add the primary episode
        if not opinion.appeared_in_episodes and opinion.episode_id:
            opinion.appeared_in_episodes = [opinion.episode_id]
            
        return opinion
        
    def is_evolution_of(self, other_opinion: 'Opinion') -> bool:
        """
        Check if this opinion is an evolution of another opinion.
        
        Args:
            other_opinion: Another opinion to check against
            
        Returns:
            True if this opinion is an evolution of the other opinion
        """
        # Check if this opinion mentions the other opinion in its evolution chain
        if other_opinion.id in self.evolution_chain:
            return True
            
        # Check if both opinions are part of the same evolution chain
        if (self.original_opinion_id and 
            self.original_opinion_id == other_opinion.original_opinion_id):
            return True
            
        # Check if the other opinion is in related opinions
        if other_opinion.id in self.related_opinions:
            return True
            
        return False
    
    def contradicts(self, other_opinion: 'Opinion') -> bool:
        """
        Check if this opinion contradicts another opinion.
        
        Args:
            other_opinion: Another opinion to check against
            
        Returns:
            True if this opinion contradicts the other opinion
        """
        if self.is_contradiction and self.contradicts_opinion_id == other_opinion.id:
            return True
        
        if other_opinion.is_contradiction and other_opinion.contradicts_opinion_id == self.id:
            return True
            
        return False 