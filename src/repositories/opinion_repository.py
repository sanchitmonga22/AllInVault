"""
Opinion Repository

This module provides functionality for managing opinions storage.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime

from src.models.opinions.opinion import Opinion

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpinionRepository:
    """Repository for opinion data with JSON file storage."""
    
    def __init__(self, opinions_file_path: str = "data/json/opinions.json"):
        """
        Initialize the opinion repository.
        
        Args:
            opinions_file_path: Path to the opinions JSON file
        """
        self.opinions_file_path = opinions_file_path
        self.opinions: Dict[str, Opinion] = {}
        self._ensure_file_exists()
        self._load_opinions()
    
    def _ensure_file_exists(self) -> None:
        """Ensure the opinions file exists, creating it if necessary."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.opinions_file_path), exist_ok=True)
        
        # Create file if it doesn't exist
        if not os.path.exists(self.opinions_file_path):
            with open(self.opinions_file_path, 'w') as f:
                json.dump({"opinions": []}, f)
    
    def _load_opinions(self) -> None:
        """Load opinions from the JSON file."""
        try:
            with open(self.opinions_file_path, 'r') as f:
                data = json.load(f)
                
            opinions_list = data.get("opinions", [])
            self.opinions = {}
            
            for opinion_data in opinions_list:
                try:
                    opinion = Opinion.from_dict(opinion_data)
                    self.opinions[opinion.id] = opinion
                except Exception as e:
                    logger.error(f"Error parsing opinion data: {e}")
                    
            logger.info(f"Loaded {len(self.opinions)} opinions from {self.opinions_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load opinions file: {e}")
            self.opinions = {}
    
    def _save_opinions(self) -> None:
        """Save opinions to the JSON file."""
        try:
            opinions_list = [opinion.to_dict() for opinion in self.opinions.values()]
            data = {"opinions": opinions_list}
            
            with open(self.opinions_file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved {len(self.opinions)} opinions to {self.opinions_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save opinions file: {e}")
    
    def get_all_opinions(self) -> List[Opinion]:
        """
        Get all opinions.
        
        Returns:
            List of all opinions
        """
        return list(self.opinions.values())
    
    def get_opinion(self, opinion_id: str) -> Optional[Opinion]:
        """
        Get an opinion by ID.
        
        Args:
            opinion_id: ID of the opinion to get
            
        Returns:
            The opinion if found, or None
        """
        return self.opinions.get(opinion_id)
    
    def get_opinions_by_speaker(self, speaker_name: str) -> List[Opinion]:
        """
        Get all opinions expressed by a specific speaker.
        
        Args:
            speaker_name: Name of the speaker
            
        Returns:
            List of opinions by the speaker
        """
        return [op for op in self.opinions.values() if op.speaker_name.lower() == speaker_name.lower()]
    
    def get_opinions_by_episode(self, episode_id: str) -> List[Opinion]:
        """
        Get all opinions expressed in a specific episode.
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            List of opinions from the episode
        """
        return [op for op in self.opinions.values() if op.episode_id == episode_id]
    
    def get_opinions_by_category(self, category: str) -> List[Opinion]:
        """
        Get all opinions belonging to a specific category.
        
        Args:
            category: Category to filter by
            
        Returns:
            List of opinions in the category
        """
        return [op for op in self.opinions.values() if op.category and op.category.lower() == category.lower()]
    
    def get_related_opinions(self, opinion_id: str) -> List[Opinion]:
        """
        Get all opinions related to a specific opinion.
        
        Args:
            opinion_id: ID of the reference opinion
            
        Returns:
            List of related opinions
        """
        opinion = self.get_opinion(opinion_id)
        if not opinion:
            return []
            
        related_ids = set(opinion.related_opinions)
        return [op for op in self.opinions.values() if op.id in related_ids]
    
    def save_opinion(self, opinion: Opinion) -> None:
        """
        Save an opinion to the repository.
        
        Args:
            opinion: The opinion to save
        """
        self.opinions[opinion.id] = opinion
        self._save_opinions()
    
    def save_opinions(self, opinions: List[Opinion]) -> None:
        """
        Save multiple opinions to the repository.
        
        Args:
            opinions: List of opinions to save
        """
        for opinion in opinions:
            self.opinions[opinion.id] = opinion
        self._save_opinions()
    
    def delete_opinion(self, opinion_id: str) -> bool:
        """
        Delete an opinion from the repository.
        
        Args:
            opinion_id: ID of the opinion to delete
            
        Returns:
            True if the opinion was deleted, False if not found
        """
        if opinion_id in self.opinions:
            del self.opinions[opinion_id]
            self._save_opinions()
            return True
        return False
    
    def link_related_opinions(self, opinion_id: str, related_opinion_ids: List[str]) -> None:
        """
        Link an opinion to other related opinions.
        
        Args:
            opinion_id: ID of the opinion to update
            related_opinion_ids: IDs of related opinions
        """
        opinion = self.get_opinion(opinion_id)
        if not opinion:
            return
            
        # Add new related opinions
        opinion.related_opinions = list(set(opinion.related_opinions + related_opinion_ids))
        self.save_opinion(opinion)
        
        # Make sure relationships are bidirectional
        for rel_id in related_opinion_ids:
            rel_opinion = self.get_opinion(rel_id)
            if rel_opinion and opinion_id not in rel_opinion.related_opinions:
                rel_opinion.related_opinions.append(opinion_id)
                self.save_opinion(rel_opinion) 