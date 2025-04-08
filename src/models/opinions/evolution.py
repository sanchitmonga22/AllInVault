"""
Evolution Tracking Models

This module provides data models for tracking the evolution of opinions across episodes.
Key features:
- EvolutionChain tracks the chronological progression of an opinion
- EvolutionNode represents a single point in an evolution chain
- EvolutionPattern categorizes common patterns in opinion evolution
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import uuid

from .opinion import Opinion


@dataclass
class EvolutionNode:
    """Represents a single point in an opinion evolution chain."""
    
    opinion_id: str  # ID of the opinion at this node
    episode_id: str  # Episode where this opinion appeared/evolved
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    date: datetime = field(default_factory=datetime.now)  # Date when this opinion appeared
    evolution_type: str = "initial"  # initial, refinement, pivot, contradiction, etc.
    description: str = ""  # Description of the evolution at this point
    previous_node_id: Optional[str] = None  # Previous node in the chain
    next_node_ids: List[str] = field(default_factory=list)  # Next nodes in the chain (can branch)
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "opinion_id": self.opinion_id,
            "date": self.date.isoformat() if self.date else None,
            "episode_id": self.episode_id,
            "evolution_type": self.evolution_type,
            "description": self.description,
            "previous_node_id": self.previous_node_id,
            "next_node_ids": self.next_node_ids,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvolutionNode':
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
            date=date,
            episode_id=data["episode_id"],
            evolution_type=data.get("evolution_type", "initial"),
            description=data.get("description", ""),
            previous_node_id=data.get("previous_node_id"),
            next_node_ids=data.get("next_node_ids", []),
            metadata=data.get("metadata", {})
        )


@dataclass
class EvolutionChain:
    """Represents a chain of opinion evolution across episodes."""
    
    root_node_id: str  # ID of the first node in the chain
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""  # Short descriptive title for this chain
    description: str = ""  # Longer description of this evolution chain
    nodes: Dict[str, EvolutionNode] = field(default_factory=dict)  # Map of node ID to node
    opinion_ids: Set[str] = field(default_factory=set)  # All opinion IDs in this chain
    pattern_id: Optional[str] = None  # ID of the pattern this chain follows
    category_id: Optional[str] = None  # Category ID for this chain
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def add_node(self, node: EvolutionNode) -> None:
        """Add a node to the chain."""
        self.nodes[node.id] = node
        self.opinion_ids.add(node.opinion_id)
        
        # If this node has a previous node, update the previous node's next_node_ids
        if node.previous_node_id and node.previous_node_id in self.nodes:
            prev_node = self.nodes[node.previous_node_id]
            if node.id not in prev_node.next_node_ids:
                prev_node.next_node_ids.append(node.id)
    
    def get_ordered_nodes(self) -> List[EvolutionNode]:
        """Get nodes in chronological order."""
        if not self.nodes:
            return []
            
        # Start with the root node
        if self.root_node_id not in self.nodes:
            # Fallback if the root node isn't found
            return sorted(self.nodes.values(), key=lambda n: n.date)
            
        ordered_nodes = []
        current_node_id = self.root_node_id
        visited = set()
        
        # Traverse the chain in order
        while current_node_id and current_node_id not in visited:
            if current_node_id not in self.nodes:
                break
                
            current_node = self.nodes[current_node_id]
            ordered_nodes.append(current_node)
            visited.add(current_node_id)
            
            # Pick the earliest next node by date
            next_nodes = [self.nodes[nid] for nid in current_node.next_node_ids 
                         if nid in self.nodes and nid not in visited]
            if next_nodes:
                next_nodes.sort(key=lambda n: n.date)
                current_node_id = next_nodes[0].id
            else:
                current_node_id = None
        
        return ordered_nodes
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "root_node_id": self.root_node_id,
            "nodes": {nid: node.to_dict() for nid, node in self.nodes.items()},
            "opinion_ids": list(self.opinion_ids),
            "pattern_id": self.pattern_id,
            "category_id": self.category_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvolutionChain':
        """Create from dictionary."""
        # Create the chain without nodes first
        chain = cls(
            id=data.get("id", str(uuid.uuid4())),
            title=data.get("title", ""),
            description=data.get("description", ""),
            root_node_id=data["root_node_id"],
            pattern_id=data.get("pattern_id"),
            category_id=data.get("category_id"),
            metadata=data.get("metadata", {})
        )
        
        # Process opinion IDs
        chain.opinion_ids = set(data.get("opinion_ids", []))
        
        # Add each node
        for node_data in data.get("nodes", {}).values():
            node = EvolutionNode.from_dict(node_data)
            chain.nodes[node.id] = node
            
        return chain


@dataclass
class EvolutionPattern:
    """Represents a common pattern in opinion evolution."""
    
    name: str  # Name of the pattern
    description: str  # Description of this pattern
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    steps: List[str] = field(default_factory=list)  # Description of steps in this pattern
    examples: List[str] = field(default_factory=list)  # IDs of evolution chains that exemplify this pattern
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "steps": self.steps,
            "examples": self.examples,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'EvolutionPattern':
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            name=data["name"],
            description=data.get("description", ""),
            steps=data.get("steps", []),
            examples=data.get("examples", []),
            metadata=data.get("metadata", {})
        ) 