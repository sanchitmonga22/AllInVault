"""
Opinion Relationship Models

This module provides data models for representing relationships between opinions.
Key features:
- Relationship tracks connections between opinions (same, similar, evolution, contradiction)
- RelationshipEvidence provides evidence for why a relationship exists
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime
import uuid


@dataclass
class RelationshipEvidence:
    """Evidence supporting a relationship between opinions."""
    
    description: str  # Description of the evidence
    source_quote: str  # Quote from source opinion
    target_quote: str  # Quote from target opinion
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    evidence_type: str = "direct"  # direct, indirect, inferred, etc.
    confidence: float = 0.8  # Confidence score for this evidence
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "description": self.description,
            "evidence_type": self.evidence_type,
            "confidence": self.confidence,
            "source_quote": self.source_quote,
            "target_quote": self.target_quote,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'RelationshipEvidence':
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            description=data["description"],
            source_quote=data["source_quote"],
            target_quote=data["target_quote"],
            evidence_type=data.get("evidence_type", "direct"),
            confidence=data.get("confidence", 0.8),
            metadata=data.get("metadata", {})
        )


@dataclass
class Relationship:
    """Represents a relationship between two opinions."""
    
    opinion_a_id: str  # ID of the first opinion
    opinion_b_id: str  # ID of the second opinion
    relationship_type: str  # Type of relationship (e.g., similar, contradicts, evolves)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""  # Description of the relationship
    evidence: List[RelationshipEvidence] = field(default_factory=list)  # Evidence supporting this relationship
    confidence: float = 0.8  # Overall confidence in this relationship
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Normalize date to ensure consistent timezone handling."""
        # Convert timezone-aware datetime to naive datetime
        if self.created_at and hasattr(self.created_at, 'tzinfo') and self.created_at.tzinfo is not None:
            self.created_at = self.created_at.replace(tzinfo=None)
    
    def add_evidence(self, evidence: RelationshipEvidence) -> None:
        """Add evidence to this relationship."""
        self.evidence.append(evidence)
        
        # Update the overall confidence score
        if self.evidence:
            # Weight by confidence scores
            total_confidence = sum(e.confidence for e in self.evidence)
            if total_confidence > 0:
                # Normalize to 0-1 range
                self.confidence = min(1.0, total_confidence / len(self.evidence))
            else:
                # Default if no confidence scores
                self.confidence = 0.5
    
    def get_evidence_by_type(self, evidence_type: str) -> List[RelationshipEvidence]:
        """Get all evidence of a specific type."""
        return [e for e in self.evidence if e.evidence_type == evidence_type]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "opinion_a_id": self.opinion_a_id,
            "opinion_b_id": self.opinion_b_id,
            "relationship_type": self.relationship_type,
            "description": self.description,
            "direction": self.direction,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "evidence": [e.to_dict() for e in self.evidence],
            "similarity_score": self.similarity_score,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Relationship':
        """Create from dictionary."""
        # Handle datetime conversion
        created_at = data.get("created_at")
        if created_at and isinstance(created_at, str):
            try:
                created_at = datetime.fromisoformat(created_at)
                # Normalize to naive datetime
                if hasattr(created_at, 'tzinfo') and created_at.tzinfo is not None:
                    created_at = created_at.replace(tzinfo=None)
            except ValueError:
                created_at = datetime.now()
        elif created_at is None:
            created_at = datetime.now()
            
        # Create evidence list
        evidence = []
        for evidence_data in data.get("evidence", []):
            evidence.append(RelationshipEvidence.from_dict(evidence_data))
            
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            opinion_a_id=data["opinion_a_id"],
            opinion_b_id=data["opinion_b_id"],
            relationship_type=data["relationship_type"],
            description=data["description"],
            direction=data.get("direction", "undirected"),
            confidence=data.get("confidence", 0.8),
            created_at=created_at,
            evidence=evidence,
            similarity_score=data.get("similarity_score"),
            metadata=data.get("metadata", {})
        ) 