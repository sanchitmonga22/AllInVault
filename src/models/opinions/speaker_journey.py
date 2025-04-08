"""
Speaker Journey Models

This module provides data models for tracking a speaker's journey and stance changes across opinions.
Key features:
- SpeakerJourney tracks a speaker's stance evolution across episodes
- SpeakerJourneyNode represents a single point in a speaker's journey with a specific stance
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import uuid


@dataclass
class SpeakerJourneyNode:
    """Represents a single point in a speaker's opinion journey."""
    
    opinion_id: str  # ID of the opinion at this node
    speaker_id: str  # ID of the speaker
    episode_id: str  # Episode where this opinion was expressed
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: datetime = field(default_factory=datetime.now)  # Date when this opinion was expressed
    stance: str = "neutral"  # support, oppose, neutral, etc.
    reasoning: str = ""  # Reasoning for the stance
    previous_node_id: Optional[str] = None  # Previous node in the journey
    next_node_ids: List[str] = field(default_factory=list)  # Next nodes in the journey (can branch)
    stance_changed: bool = False  # Whether stance changed from previous node
    change_description: Optional[str] = None  # Description of the stance change
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "opinion_id": self.opinion_id,
            "episode_id": self.episode_id,
            "date": self.date.isoformat() if self.date else None,
            "stance": self.stance,
            "reasoning": self.reasoning,
            "previous_node_id": self.previous_node_id,
            "next_node_ids": self.next_node_ids,
            "stance_changed": self.stance_changed,
            "change_description": self.change_description,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpeakerJourneyNode':
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
                date = datetime.now()
        elif date is None:
            date = datetime.now()
            
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            opinion_id=data["opinion_id"],
            episode_id=data["episode_id"],
            date=date,
            stance=data["stance"],
            reasoning=data.get("reasoning", ""),
            previous_node_id=data.get("previous_node_id"),
            next_node_ids=data.get("next_node_ids", []),
            stance_changed=data.get("stance_changed", False),
            change_description=data.get("change_description"),
            metadata=data.get("metadata", {})
        )


@dataclass
class SpeakerJourney:
    """Represents a speaker's journey through opinions over time."""
    
    speaker_id: str  # ID of the speaker
    speaker_name: str  # Name of the speaker
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    root_node_id: Optional[str] = None  # ID of the first node in the journey
    nodes: Dict[str, SpeakerJourneyNode] = field(default_factory=dict)  # Map of node ID to node
    opinion_ids: Set[str] = field(default_factory=set)  # All opinion IDs in this journey
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_node(self, node: SpeakerJourneyNode) -> None:
        """Add a journey node for this speaker."""
        self.nodes[node.id] = node
        
        # Update opinion_ids mapping
        self.opinion_ids.add(node.opinion_id)
        
        # If this node has a previous node, update the previous node's next_node_ids
        if node.previous_node_id and node.previous_node_id in self.nodes:
            prev_node = self.nodes[node.previous_node_id]
            if node.id not in prev_node.next_node_ids:
                prev_node.next_node_ids.append(node.id)
    
    def get_opinion_journey(self, opinion_id: str) -> List[SpeakerJourneyNode]:
        """Get all nodes for a specific opinion in chronological order."""
        if opinion_id not in self.opinion_ids:
            return []
            
        nodes = [self.nodes[node_id] for node_id in self.opinion_ids if node_id in self.nodes]
        
        # Sort by date
        nodes.sort(key=lambda n: n.date)
        return nodes
    
    def get_stance_changes(self) -> Dict[str, List[SpeakerJourneyNode]]:
        """Get all nodes where the stance changed, grouped by opinion."""
        changes = {}
        
        for opinion_id in self.opinion_ids:
            stance_change_nodes = [self.nodes[nid] for nid in self.opinion_ids 
                                 if nid in self.nodes and self.nodes[nid].stance_changed]
            
            if stance_change_nodes:
                changes[opinion_id] = sorted(stance_change_nodes, key=lambda n: n.date)
                
        return changes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "speaker_id": self.speaker_id,
            "speaker_name": self.speaker_name,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "opinion_ids": list(self.opinion_ids),
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SpeakerJourney':
        """Create from dictionary."""
        # Create the journey without nodes first
        journey = cls(
            speaker_id=data["speaker_id"],
            speaker_name=data["speaker_name"],
            id=data.get("id", str(uuid.uuid4())),
            opinion_ids=set(data.get("opinion_ids", [])),
            metadata=data.get("metadata", {})
        )
        
        # Add each node
        for node_data in data.get("nodes", {}).values():
            node = SpeakerJourneyNode.from_dict(node_data)
            journey.nodes[node.id] = node
            
        return journey 