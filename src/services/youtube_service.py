from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Optional

import googleapiclient.discovery
import googleapiclient.errors
from googleapiclient.discovery import build

from src.models.podcast_episode import PodcastEpisode


class YouTubeServiceInterface(ABC):
    """Interface for YouTube API service."""
    
    @abstractmethod
    def get_channel_uploads_playlist_id(self, channel_id: str) -> str:
        """Get the uploads playlist ID for a channel."""
        pass
    
    @abstractmethod
    def get_playlist_items(self, playlist_id: str, max_results: int = 50) -> List[dict]:
        """Get items from a playlist."""
        pass
    
    @abstractmethod
    def get_video_details(self, video_ids: List[str]) -> List[dict]:
        """Get details for specific videos."""
        pass
    
    @abstractmethod
    def search_channel_videos(self, channel_id: str, query: str = None, 
                             max_results: int = 50) -> List[dict]:
        """Search for videos in a channel."""
        pass
    
    @abstractmethod
    def get_all_episodes(self, channel_id: str, max_results: int = None) -> List[PodcastEpisode]:
        """Get all episodes from a channel as PodcastEpisode objects."""
        pass
    
    @abstractmethod
    def get_episode_by_id(self, video_id: str) -> Optional[PodcastEpisode]:
        """Get a specific episode by video ID."""
        pass


class YouTubeService(YouTubeServiceInterface):
    """Implementation of YouTube API service."""
    
    def __init__(self, api_key: str):
        """Initialize with YouTube API key."""
        self.api_key = api_key
        self.youtube = build("youtube", "v3", developerKey=api_key)
    
    def get_channel_uploads_playlist_id(self, channel_id: str) -> str:
        """Get the uploads playlist ID for a channel."""
        request = self.youtube.channels().list(
            part="contentDetails",
            id=channel_id
        )
        response = request.execute()
        
        if not response.get("items"):
            raise ValueError(f"No channel found with ID: {channel_id}")
        
        return response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]
    
    def get_playlist_items(self, playlist_id: str, max_results: int = 50) -> List[dict]:
        """Get items from a playlist."""
        items = []
        next_page_token = None
        
        while True:
            request = self.youtube.playlistItems().list(
                part="snippet",
                playlistId=playlist_id,
                maxResults=min(50, max_results - len(items)) if max_results else 50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            items.extend(response.get("items", []))
            next_page_token = response.get("nextPageToken")
            
            if not next_page_token or (max_results and len(items) >= max_results):
                break
                
        return items
    
    def get_video_details(self, video_ids: List[str]) -> List[dict]:
        """Get details for specific videos."""
        items = []
        
        # YouTube API supports up to 50 video IDs per request
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i+50]
            request = self.youtube.videos().list(
                part="snippet,contentDetails,statistics",
                id=",".join(batch)
            )
            response = request.execute()
            items.extend(response.get("items", []))
            
        return items
    
    def search_channel_videos(self, channel_id: str, query: str = None, 
                             max_results: int = 50) -> List[dict]:
        """Search for videos in a channel."""
        items = []
        next_page_token = None
        
        while True:
            request = self.youtube.search().list(
                part="snippet",
                channelId=channel_id,
                q=query,
                type="video",
                maxResults=min(50, max_results - len(items)) if max_results else 50,
                pageToken=next_page_token
            )
            response = request.execute()
            
            items.extend(response.get("items", []))
            next_page_token = response.get("nextPageToken")
            
            if not next_page_token or (max_results and len(items) >= max_results):
                break
                
        return items
    
    def get_all_episodes(self, channel_id: str, max_results: Optional[int] = None) -> List[PodcastEpisode]:
        """Get all episodes from a channel as PodcastEpisode objects."""
        try:
            # Get uploads playlist ID
            uploads_playlist_id = self.get_channel_uploads_playlist_id(channel_id)
            
            # Get all video IDs from playlist
            playlist_items = self.get_playlist_items(uploads_playlist_id, max_results)
            video_ids = [item["snippet"]["resourceId"]["videoId"] for item in playlist_items]
            
            # Get detailed video information
            video_details = self.get_video_details(video_ids)
            
            # Convert to PodcastEpisode objects
            episodes = []
            for video in video_details:
                snippet = video["snippet"]
                content_details = video["contentDetails"]
                statistics = video["statistics"]
                
                episode = PodcastEpisode(
                    video_id=video["id"],
                    title=snippet["title"],
                    description=snippet["description"],
                    published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
                    channel_id=snippet["channelId"],
                    channel_title=snippet["channelTitle"],
                    tags=snippet.get("tags", []),
                    duration=content_details.get("duration"),
                    view_count=int(statistics.get("viewCount", 0)),
                    like_count=int(statistics.get("likeCount", 0)) if "likeCount" in statistics else None,
                    comment_count=int(statistics.get("commentCount", 0)) if "commentCount" in statistics else None,
                    thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url")
                )
                episodes.append(episode)
                
            return episodes
            
        except googleapiclient.errors.HttpError as e:
            print(f"YouTube API error: {e}")
            raise 
    
    def get_episode_by_id(self, video_id: str) -> Optional[PodcastEpisode]:
        """
        Get a specific episode by video ID.
        
        Args:
            video_id: YouTube video ID to fetch
            
        Returns:
            PodcastEpisode object or None if not found
        """
        try:
            # Get video details
            video_details = self.get_video_details([video_id])
            
            if not video_details:
                return None
                
            video = video_details[0]
            snippet = video["snippet"]
            content_details = video["contentDetails"]
            statistics = video["statistics"]
            
            episode = PodcastEpisode(
                video_id=video["id"],
                title=snippet["title"],
                description=snippet["description"],
                published_at=datetime.fromisoformat(snippet["publishedAt"].replace("Z", "+00:00")),
                channel_id=snippet["channelId"],
                channel_title=snippet["channelTitle"],
                tags=snippet.get("tags", []),
                duration=content_details.get("duration"),
                view_count=int(statistics.get("viewCount", 0)),
                like_count=int(statistics.get("likeCount", 0)) if "likeCount" in statistics else None,
                comment_count=int(statistics.get("commentCount", 0)) if "commentCount" in statistics else None,
                thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url")
            )
            
            return episode
                
        except googleapiclient.errors.HttpError as e:
            print(f"YouTube API error: {e}")
            return None 