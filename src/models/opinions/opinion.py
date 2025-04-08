"""
Opinion Model

This module provides the data model for opinion tracking across episodes and speakers.
Key features:
- Opinions are unique objects that can appear in multiple episodes
- Each appearance can have multiple speakers with different stances
- Evolution tracking across episodes
- Contradiction detection between opinions
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Set
from dataclasses import dataclass, field
import uuid
import logging

logger = logging.getLogger(__name__)


@dataclass
class SpeakerStance:
    """Model representing a speaker's stance on an opinion in a specific episode."""
    
    speaker_id: str  # ID of the speaker
    speaker_name: str  # Name of the speaker
    stance: str = "support"  # support, oppose, neutral
    reasoning: Optional[str] = None  # Why they have this stance
    start_time: Optional[float] = None  # When they start discussing this opinion
    end_time: Optional[float] = None  # When they finish discussing this opinion
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "stance": self.stance,
            "reasoning": self.reasoning,
            "start_time": self.start_time,
            "end_time": self.end_time
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpeakerStance':
        """Create from dictionary."""
        return cls(
            speaker_id=data["speaker_id"],
            speaker_name=data["speaker_name"],
            stance=data.get("stance", "support"),
            reasoning=data.get("reasoning"),
            start_time=data.get("start_time"),
            end_time=data.get("end_time")
        )


@dataclass
class OpinionAppearance:
    """Model representing an appearance of an opinion in a specific episode."""
    
    episode_id: str  # ID of the episode
    episode_title: str  # Title of the episode
    date: datetime  # Date of the episode
    speakers: List[SpeakerStance] = field(default_factory=list)  # Speakers discussing this opinion
    content: Optional[str] = None  # Actual content from this episode
    context_notes: Optional[str] = None  # Context notes for this appearance
    evolution_notes_for_episode: Optional[str] = None  # Evolution notes specific to this episode
    
    def __post_init__(self):
        """Normalize date to ensure consistent timezone handling."""
        # Convert timezone-aware datetime to naive datetime
        if self.date and hasattr(self.date, 'tzinfo') and self.date.tzinfo is not None:
            self.date = self.date.replace(tzinfo=None)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "episode_id": self.episode_id,
            "episode_title": self.episode_title,
            "date": self.date.isoformat() if self.date else None,
            "speakers": [speaker.to_dict() for speaker in self.speakers],
            "content": self.content,
            "context_notes": self.context_notes,
            "evolution_notes_for_episode": self.evolution_notes_for_episode
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'OpinionAppearance':
        """Create from dictionary."""
        # Handle datetime conversion
        date = data.get("date")
        if date and isinstance(date, str):
            try:
                date = datetime.fromisoformat(date)
                # Normalize to naive datetime
                if hasattr(date, 'tzinfo') and date.tzinfo is not None:
                    date = date.replace(tzinfo=None)
            except ValueError:
                # Fallback for older date formats
                logger.warning(f"Could not parse date: {date}")
                date = datetime.now()
        elif date is None:
            date = datetime.now()
            
        # Create speakers list
        speakers = []
        for speaker_data in data.get("speakers", []):
            speakers.append(SpeakerStance.from_dict(speaker_data))
            
        return cls(
            episode_id=data["episode_id"],
            episode_title=data["episode_title"],
            date=date,
            speakers=speakers,
            content=data.get("content"),
            context_notes=data.get("context_notes"),
            evolution_notes_for_episode=data.get("evolution_notes_for_episode")
        )
    
    def is_contentious(self) -> bool:
        """Check if this appearance has disagreement among speakers."""
        stances = {speaker.stance for speaker in self.speakers}
        # If we have both support and oppose stances, it's contentious
        return "support" in stances and "oppose" in stances


@dataclass
class Opinion:
    """Model representing a unique opinion that can appear across multiple episodes."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""  # Short title/summary of the opinion
    description: str = ""  # Longer description of the opinion
    category_id: Optional[str] = None  # ID of the category for this opinion
    
    # Evolution tracking
    related_opinions: List[str] = field(default_factory=list)  # IDs of related opinions
    evolution_notes: Optional[str] = None  # Overall notes on how this opinion has evolved
    evolution_chain: List[str] = field(default_factory=list)  # Chronological chain of opinion IDs in this evolution
    
    # Contradiction tracking
    is_contradiction: bool = False  # Whether this opinion contradicts another opinion
    contradicts_opinion_id: Optional[str] = None  # ID of the opinion this contradicts
    contradiction_notes: Optional[str] = None  # Notes about the contradiction
    
    # Episode appearances
    appearances: List[OpinionAppearance] = field(default_factory=list)
    
    # Additional metadata
    keywords: List[str] = field(default_factory=list)  # Keywords associated with this opinion
    confidence: float = 0.0  # Confidence score for opinion detection
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_appearance(self, appearance: OpinionAppearance) -> None:
        """Add an episode appearance to this opinion."""
        # Check if we already have an appearance for this episode
        for existing in self.appearances:
            if existing.episode_id == appearance.episode_id:
                # Update the existing appearance instead of adding a new one
                existing.speakers.extend(appearance.speakers)
                if appearance.content and not existing.content:
                    existing.content = appearance.content
                if appearance.context_notes and not existing.context_notes:
                    existing.context_notes = appearance.context_notes
                if appearance.evolution_notes_for_episode and not existing.evolution_notes_for_episode:
                    existing.evolution_notes_for_episode = appearance.evolution_notes_for_episode
                return
                
        # Add new appearance
        self.appearances.append(appearance)
        
        # Sort appearances by date
        self.appearances.sort(key=lambda app: app.date)
    
    def get_all_speaker_ids(self) -> List[str]:
        """Get all speaker IDs associated with this opinion across all episodes."""
        speaker_ids = set()
        for appearance in self.appearances:
            for speaker in appearance.speakers:
                speaker_ids.add(speaker.speaker_id)
        return list(speaker_ids)
    
    def get_all_speaker_names(self) -> List[str]:
        """Get all speaker names associated with this opinion across all episodes."""
        speaker_names = set()
        for appearance in self.appearances:
            for speaker in appearance.speakers:
                speaker_names.add(speaker.speaker_name)
        return list(speaker_names)
    
    def get_episode_ids(self) -> List[str]:
        """Get all episode IDs where this opinion appeared."""
        return [app.episode_id for app in self.appearances]
    
    def get_speaker_evolution(self, speaker_id: str) -> List[Dict[str, Any]]:
        """
        Track the evolution of a speaker's stance across episodes.
        
        Args:
            speaker_id: ID of the speaker to track
            
        Returns:
            List of dicts with episode_id, date, stance, and reasoning
        """
        evolution = []
        for appearance in self.appearances:
            for speaker in appearance.speakers:
                if speaker.speaker_id == speaker_id:
                    evolution.append({
                        "episode_id": appearance.episode_id,
                        "episode_title": appearance.episode_title,
                        "date": appearance.date,
                        "stance": speaker.stance,
                        "reasoning": speaker.reasoning
                    })
        
        # Sort by date
        evolution.sort(key=lambda e: e["date"])
        return evolution
    
    def is_contentious_overall(self) -> bool:
        """Check if this opinion has disagreement among speakers across all episodes."""
        all_stances = set()
        for appearance in self.appearances:
            for speaker in appearance.speakers:
                all_stances.add(speaker.stance)
        
        # If we have both support and oppose stances, it's contentious
        return "support" in all_stances and "oppose" in all_stances
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Opinion to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "category_id": self.category_id,
            "related_opinions": self.related_opinions,
            "evolution_notes": self.evolution_notes,
            "evolution_chain": self.evolution_chain,
            "is_contradiction": self.is_contradiction,
            "contradicts_opinion_id": self.contradicts_opinion_id,
            "contradiction_notes": self.contradiction_notes,
            "appearances": [app.to_dict() for app in self.appearances],
            "keywords": self.keywords,
            "confidence": self.confidence,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Opinion':
        """Create Opinion from dictionary."""
        # Create appearances
        appearances = []
        for app_data in data.get("appearances", []):
            appearances.append(OpinionAppearance.from_dict(app_data))
            
        # Create the basic opinion object
        opinion = cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            category_id=data.get("category_id"),
            related_opinions=data.get("related_opinions", []),
            evolution_notes=data.get("evolution_notes"),
            evolution_chain=data.get("evolution_chain", []),
            is_contradiction=data.get("is_contradiction", False),
            contradicts_opinion_id=data.get("contradicts_opinion_id"),
            contradiction_notes=data.get("contradiction_notes"),
            appearances=appearances,
            keywords=data.get("keywords", []),
            confidence=data.get("confidence", 0.0),
            metadata=data.get("metadata", {})
        )
        
        return opinion
    
    @classmethod
    def migrate_legacy_opinion(cls, legacy_data: Dict[str, Any]) -> 'Opinion':
        """
        Migrate a legacy opinion format to the new structure.
        
        Args:
            legacy_data: Dictionary representing a legacy opinion
            
        Returns:
            New Opinion object
        """
        # Create a new opinion
        opinion = cls(
            id=legacy_data.get("id", str(uuid.uuid4())),
            title=legacy_data.get("title", ""),
            description=legacy_data.get("description", ""),
            category_id=legacy_data.get("category_id"),
            related_opinions=legacy_data.get("related_opinions", []),
            evolution_notes=legacy_data.get("evolution_notes"),
            evolution_chain=legacy_data.get("evolution_chain", []),
            is_contradiction=legacy_data.get("is_contradiction", False),
            contradicts_opinion_id=legacy_data.get("contradicts_opinion_id"),
            contradiction_notes=legacy_data.get("contradiction_notes"),
            keywords=legacy_data.get("keywords", []),
            confidence=legacy_data.get("confidence", 0.0),
            metadata=legacy_data.get("metadata", {})
        )
        
        # Parse date from legacy data
        date = legacy_data.get("date")
        if date and isinstance(date, str):
            date = datetime.fromisoformat(date)
        elif date is None:
            date = datetime.now()
        
        # Create speakers from legacy speaker_timestamps
        speakers = []
        speaker_timestamps = legacy_data.get("speaker_timestamps", {})
        if speaker_timestamps:
            for speaker_id, data in speaker_timestamps.items():
                speaker_name = data.get("speaker_name", f"Speaker {speaker_id}")
                speakers.append(SpeakerStance(
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    stance=data.get("stance", "support"),
                    reasoning=data.get("reasoning"),
                    start_time=data.get("start_time", legacy_data.get("start_time")),
                    end_time=data.get("end_time", legacy_data.get("end_time"))
                ))
        else:
            # Handle single speaker case
            speakers.append(SpeakerStance(
                speaker_id=legacy_data.get("speaker_id", "unknown"),
                speaker_name=legacy_data.get("speaker_name", "Unknown"),
                stance="support",
                start_time=legacy_data.get("start_time"),
                end_time=legacy_data.get("end_time")
            ))
        
        # Create an appearance for the primary episode
        primary_appearance = OpinionAppearance(
            episode_id=legacy_data.get("episode_id", "unknown"),
            episode_title=legacy_data.get("episode_title", "Unknown"),
            date=date,
            speakers=speakers,
            content=legacy_data.get("content")
        )
        opinion.add_appearance(primary_appearance)
        
        # Add appearances for all episodes in appeared_in_episodes
        appeared_in_episodes = legacy_data.get("appeared_in_episodes", [])
        if appeared_in_episodes:
            episode_occurrences = legacy_data.get("metadata", {}).get("episode_occurrences", {})
            for ep_id in appeared_in_episodes:
                # Skip the primary episode we already added
                if ep_id == legacy_data.get("episode_id"):
                    continue
                
                # Try to get episode details
                ep_data = episode_occurrences.get(ep_id, {})
                ep_title = ep_data.get("title", "Unknown Episode")
                
                # Get date for this episode
                ep_date = ep_data.get("date")
                if ep_date and isinstance(ep_date, str):
                    ep_date = datetime.fromisoformat(ep_date)
                else:
                    ep_date = date  # Use same date as primary episode
                
                # Create appearance for this episode
                appearance = OpinionAppearance(
                    episode_id=ep_id,
                    episode_title=ep_title,
                    date=ep_date,
                    # No speakers assigned for these episodes
                    speakers=[]
                )
                opinion.add_appearance(appearance)
        
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