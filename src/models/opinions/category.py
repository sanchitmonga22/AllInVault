"""
Category Model

This module provides the data model for opinion categories.
"""

from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field


@dataclass
class Category:
    """Model representing a category for opinions."""
    
    id: str  # Unique identifier for the category
    name: str  # Name of the category (e.g., "Politics", "Economics")
    description: Optional[str] = None  # Optional description of the category
    parent_id: Optional[str] = None  # Optional parent category ID for hierarchical categories
    metadata: Dict[str, Any] = field(default_factory=dict)  # Additional metadata
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert Category to dictionary for serialization."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "parent_id": self.parent_id,
            "metadata": self.metadata
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Category':
        """Create Category from dictionary."""
        return cls(
            id=data["id"],
            name=data["name"],
            description=data.get("description"),
            parent_id=data.get("parent_id"),
            metadata=data.get("metadata", {})
        ) 