import json
import os
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Dict, List, Optional, Union

from src.models.podcast_episode import PodcastEpisode


class EpisodeRepositoryInterface(ABC):
    """Interface for episode repository."""
    
    @abstractmethod
    def save_episode(self, episode: PodcastEpisode) -> None:
        """Save a single episode to the repository."""
        pass
    
    @abstractmethod
    def save_episodes(self, episodes: List[PodcastEpisode]) -> None:
        """Save multiple episodes to the repository."""
        pass
    
    @abstractmethod
    def get_episode(self, video_id: str) -> Optional[PodcastEpisode]:
        """Get an episode by video ID."""
        pass
    
    @abstractmethod
    def get_all_episodes(self) -> List[PodcastEpisode]:
        """Get all episodes from the repository."""
        pass
    
    @abstractmethod
    def search_episodes(self, query: str) -> List[PodcastEpisode]:
        """Search for episodes matching a query."""
        pass


class JsonFileRepository(EpisodeRepositoryInterface):
    """Repository implementation using JSON file storage."""
    
    def __init__(self, file_path: str):
        """Initialize with the JSON file path."""
        self.file_path = file_path
        self._ensure_file_exists()
    
    def _ensure_file_exists(self) -> None:
        """Ensure the JSON file exists, create if it doesn't."""
        directory = os.path.dirname(self.file_path)
        if directory and not os.path.exists(directory):
            os.makedirs(directory, exist_ok=True)
            
        if not os.path.exists(self.file_path):
            with open(self.file_path, 'w') as f:
                json.dump({"episodes": []}, f)
    
    def _read_data(self) -> Dict:
        """Read data from the JSON file."""
        with open(self.file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return {"episodes": []}
    
    def _write_data(self, data: Dict) -> None:
        """Write data to the JSON file."""
        with open(self.file_path, 'w') as f:
            json.dump(data, f, indent=2)
    
    def save_episode(self, episode: PodcastEpisode) -> None:
        """Save a single episode to the repository."""
        data = self._read_data()
        
        # Check if episode already exists, update if it does
        for i, existing in enumerate(data["episodes"]):
            if existing["video_id"] == episode.video_id:
                data["episodes"][i] = episode.to_dict()
                self._write_data(data)
                return
        
        # Episode doesn't exist, append it
        data["episodes"].append(episode.to_dict())
        self._write_data(data)
    
    def save_episodes(self, episodes: List[PodcastEpisode]) -> None:
        """Save multiple episodes to the repository."""
        data = self._read_data()
        
        # Create a lookup of existing episodes
        existing_episodes = {e["video_id"]: i for i, e in enumerate(data["episodes"])}
        
        for episode in episodes:
            if episode.video_id in existing_episodes:
                # Update existing episode
                data["episodes"][existing_episodes[episode.video_id]] = episode.to_dict()
            else:
                # Add new episode
                data["episodes"].append(episode.to_dict())
        
        self._write_data(data)
    
    def get_episode(self, video_id: str) -> Optional[PodcastEpisode]:
        """Get an episode by video ID."""
        data = self._read_data()
        
        for episode_data in data["episodes"]:
            if episode_data["video_id"] == video_id:
                return PodcastEpisode.from_dict(episode_data)
        
        return None
    
    def get_all_episodes(self) -> List[PodcastEpisode]:
        """Get all episodes from the repository."""
        data = self._read_data()
        
        return [PodcastEpisode.from_dict(episode_data) for episode_data in data["episodes"]]
    
    def search_episodes(self, query: str) -> List[PodcastEpisode]:
        """Search for episodes matching a query."""
        data = self._read_data()
        query = query.lower()
        
        matching_episodes = []
        for episode_data in data["episodes"]:
            if (query in episode_data["title"].lower() or 
                query in episode_data["description"].lower()):
                matching_episodes.append(PodcastEpisode.from_dict(episode_data))
        
        return matching_episodes 