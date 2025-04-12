"""
Opinion Repository

This module provides functionality for managing opinions storage.
"""

import json
import os
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime

from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder for datetime objects."""
    
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)


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
                    # Check if this is a legacy opinion format that needs migration
                    if "speaker_id" in opinion_data or "episode_id" in opinion_data:
                        # This is an old format opinion, use the migration method
                        opinion = Opinion.migrate_legacy_opinion(opinion_data)
                    else:
                        # This is the new format
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
                json.dump(data, f, indent=2, cls=DateTimeEncoder)
                
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
    
    def get_opinions_by_speaker(self, speaker_id: str) -> List[Opinion]:
        """
        Get all opinions expressed by a specific speaker.
        
        Args:
            speaker_id: ID of the speaker
            
        Returns:
            List of opinions involving the speaker
        """
        results = []
        for opinion in self.opinions.values():
            # Check if this speaker appears in any of the opinion's appearances
            for appearance in opinion.appearances:
                for speaker in appearance.speakers:
                    if speaker.speaker_id == speaker_id:
                        results.append(opinion)
                        break
        
        return results
    
    def get_opinions_by_speaker_name(self, speaker_name: str) -> List[Opinion]:
        """
        Get all opinions expressed by a speaker identified by name.
        
        Args:
            speaker_name: Name of the speaker
            
        Returns:
            List of opinions involving the speaker
        """
        results = []
        speaker_name_lower = speaker_name.lower()
        
        for opinion in self.opinions.values():
            # Check if this speaker appears in any of the opinion's appearances
            for appearance in opinion.appearances:
                for speaker in appearance.speakers:
                    if speaker.speaker_name.lower() == speaker_name_lower:
                        results.append(opinion)
                        break
        
        return results
    
    def get_opinions_by_episode(self, episode_id: str) -> List[Opinion]:
        """
        Get all opinions expressed in a specific episode.
        
        Args:
            episode_id: ID of the episode
            
        Returns:
            List of opinions from the episode
        """
        results = []
        for opinion in self.opinions.values():
            # Check if this episode appears in any of the opinion's appearances
            for appearance in opinion.appearances:
                if appearance.episode_id == episode_id:
                    results.append(opinion)
                    break
        
        return results
    
    def get_opinions_by_category(self, category_id: str) -> List[Opinion]:
        """
        Get all opinions belonging to a specific category.
        
        Args:
            category_id: Category ID to filter by
            
        Returns:
            List of opinions in the category
        """
        return [op for op in self.opinions.values() if op.category_id == category_id]
    
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
    
    def get_contradicting_opinions(self, opinion_id: str) -> List[Opinion]:
        """
        Get all opinions that contradict a specific opinion.
        
        Args:
            opinion_id: ID of the reference opinion
            
        Returns:
            List of contradicting opinions
        """
        result = []
        
        for opinion in self.opinions.values():
            if opinion.is_contradiction and opinion.contradicts_opinion_id == opinion_id:
                result.append(opinion)
            
        return result
    
    def save_opinion(self, opinion: Opinion) -> None:
        """
        Save an opinion to the repository.
        
        Args:
            opinion: The opinion to save
        """
        self.opinions[opinion.id] = opinion
        # Don't save to file immediately to avoid redundant saves
    
    def save_opinions(self, opinions: List[Opinion]) -> None:
        """
        Save multiple opinions to the repository and persist to file.
        
        Args:
            opinions: List of opinions to save
        """
        for opinion in opinions:
            self.opinions[opinion.id] = opinion
        # Save to file once after all opinions are added
        self._save_opinions()
    
    def flush(self) -> None:
        """
        Force a save of all opinions to the file system.
        Use this when you need to ensure all changes are persisted.
        """
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
    
    def add_opinion_appearance(self, opinion_id: str, appearance: OpinionAppearance) -> None:
        """
        Add a new episode appearance to an existing opinion.
        
        Args:
            opinion_id: ID of the opinion to update
            appearance: The appearance to add
        """
        opinion = self.get_opinion(opinion_id)
        if not opinion:
            logger.error(f"Cannot add appearance: Opinion {opinion_id} not found")
            return
            
        opinion.add_appearance(appearance)
        self.save_opinion(opinion)
    
    def get_speaker_evolution(self, speaker_id: str, opinion_id: str) -> List[Dict[str, Any]]:
        """
        Get the evolution of a speaker's stance on an opinion across episodes.
        
        Args:
            speaker_id: ID of the speaker
            opinion_id: ID of the opinion
            
        Returns:
            List of stance evolution data sorted by date
        """
        opinion = self.get_opinion(opinion_id)
        if not opinion:
            return []
            
        return opinion.get_speaker_evolution(speaker_id)
    
    def get_contentious_opinions(self) -> List[Opinion]:
        """
        Get all opinions that have disagreement among speakers.
        
        Returns:
            List of contentious opinions
        """
        return [op for op in self.opinions.values() if op.is_contentious_overall()]
    
    def get_cross_episode_opinions(self, min_episodes: int = 2) -> List[Opinion]:
        """
        Get all opinions that appear in multiple episodes.
        
        Args:
            min_episodes: Minimum number of episodes an opinion must appear in
            
        Returns:
            List of opinions appearing in multiple episodes
        """
        return [op for op in self.opinions.values() if len(op.appearances) >= min_episodes]
    
    def migrate_legacy_opinions(self) -> int:
        """
        Migrate all opinions from legacy format to new format.
        
        Returns:
            Number of opinions migrated
        """
        migrated_count = 0
        
        # Load all opinions from the file directly to get the raw data
        try:
            with open(self.opinions_file_path, 'r') as f:
                data = json.load(f)
            
            opinions_list = data.get("opinions", [])
            updated_opinions = []
            
            for opinion_data in opinions_list:
                # Check if this opinion needs migration
                if "speaker_id" in opinion_data or "episode_id" in opinion_data:
                    # Migrate the opinion
                    migrated_opinion = Opinion.migrate_legacy_opinion(opinion_data)
                    self.opinions[migrated_opinion.id] = migrated_opinion
                    updated_opinions.append(migrated_opinion)
                    migrated_count += 1
            
            # Save the migrated opinions
            if migrated_count > 0:
                self._save_opinions()
                
            return migrated_count
                
        except Exception as e:
            logger.error(f"Failed to migrate legacy opinions: {e}")
            return 0 