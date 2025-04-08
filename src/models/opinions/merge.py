"""
Merge Tracking Models

This module provides data models for tracking opinion merges and conflict resolution.
Key features:
- MergeRecord tracks when opinions are merged together
- ConflictResolution tracks how conflicts during merges are resolved
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
import uuid


@dataclass
class ConflictResolution:
    """Represents a resolution to a conflict during opinion merging."""
    
    field_name: str  # Name of the field with conflict
    resolution_type: str  # Type of resolution (e.g., keep_a, keep_b, merge)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    description: str = ""  # Description of how the conflict was resolved
    resolution_data: Dict[str, Any] = field(default_factory=dict)  # Additional data about the resolution
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "field_name": self.field_name,
            "resolution_type": self.resolution_type,
            "description": self.description,
            "resolution_data": self.resolution_data,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConflictResolution':
        """Create from dictionary."""
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            field_name=data["field_name"],
            resolution_type=data["resolution_type"],
            description=data.get("description", ""),
            resolution_data=data.get("resolution_data", {}),
            metadata=data.get("metadata", {})
        )


@dataclass
class MergeRecord:
    """Record of a merge operation between opinions."""
    
    merged_opinion_id: str  # ID of the resulting merged opinion
    source_opinion_ids: List[str]  # IDs of the opinions that were merged
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    merge_type: str = "manual"  # Type of merge (manual, auto, etc.)
    description: str = ""  # Description of the merge operation
    resolutions: List[ConflictResolution] = field(default_factory=list)  # List of conflict resolutions
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        """Normalize date to ensure consistent timezone handling."""
        # Convert timezone-aware datetime to naive datetime
        if self.merge_date and hasattr(self.merge_date, 'tzinfo') and self.merge_date.tzinfo is not None:
            self.merge_date = self.merge_date.replace(tzinfo=None)
    
    def add_conflict(self, conflict: ConflictResolution) -> None:
        """Add a conflict resolution to this merge record."""
        self.conflicts.append(conflict)
    
    def get_conflicts_by_field(self, field_name: str) -> List[ConflictResolution]:
        """Get all conflicts for a specific field."""
        return [c for c in self.conflicts if c.field_name == field_name]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "merged_opinion_id": self.merged_opinion_id,
            "source_opinion_ids": self.source_opinion_ids,
            "merge_date": self.merge_date.isoformat() if self.merge_date else None,
            "merge_method": self.merge_method,
            "merge_reason": self.merge_reason,
            "similarity_score": self.similarity_score,
            "conflicts": [c.to_dict() for c in self.conflicts],
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'MergeRecord':
        """Create from dictionary."""
        # Handle datetime conversion
        merge_date = data.get("merge_date")
        if merge_date and isinstance(merge_date, str):
            try:
                merge_date = datetime.fromisoformat(merge_date)
                # Normalize to naive datetime
                if hasattr(merge_date, 'tzinfo') and merge_date.tzinfo is not None:
                    merge_date = merge_date.replace(tzinfo=None)
            except ValueError:
                merge_date = datetime.now()
        elif merge_date is None:
            merge_date = datetime.now()
            
        # Create conflicts list
        conflicts = []
        for conflict_data in data.get("conflicts", []):
            conflicts.append(ConflictResolution.from_dict(conflict_data))
            
        return cls(
            id=data.get("id", str(uuid.uuid4())),
            merged_opinion_id=data["merged_opinion_id"],
            source_opinion_ids=data["source_opinion_ids"],
            merge_date=merge_date,
            merge_method=data.get("merge_method", "semantic"),
            merge_reason=data.get("merge_reason", ""),
            similarity_score=data.get("similarity_score", 0.0),
            conflicts=conflicts,
            metadata=data.get("metadata", {})
        ) 