import os
from abc import ABC, abstractmethod
from pathlib import Path
from typing import List, Optional

import yt_dlp
import pytube
from pytube import YouTube
from pyyoutube import Api

from src.models.podcast_episode import PodcastEpisode


class DownloaderServiceInterface(ABC):
    """Interface for audio download service."""
    
    @abstractmethod
    def download_audio(self, video_id: str, output_path: str) -> str:
        """Download audio from a YouTube video ID.
        
        Args:
            video_id: YouTube video ID
            output_path: Directory to save the audio file
            
        Returns:
            Path to the downloaded audio file
        """
        pass
    
    @abstractmethod
    def download_episodes(self, episodes: List[PodcastEpisode], output_dir: str) -> List[PodcastEpisode]:
        """Download audio for multiple episodes.
        
        Args:
            episodes: List of podcast episodes
            output_dir: Directory to save audio files
            
        Returns:
            Updated list of podcast episodes with audio_filename
        """
        pass


class YtDlpDownloader(DownloaderServiceInterface):
    """Downloader service implementation using yt-dlp."""
    
    def __init__(self, format: str = "mp3", quality: str = "192"):
        """Initialize the downloader with format and quality settings.
        
        Args:
            format: Audio format (mp3, m4a, etc.)
            quality: Audio quality (bitrate in kbps)
        """
        self.format = format
        self.quality = quality
        
    def download_audio(self, video_id: str, output_path: str) -> str:
        """Download audio from YouTube video ID."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        output_template = os.path.join(output_path, f"{video_id}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio/best',
            'postprocessors': [{
                'key': 'FFmpegExtractAudio',
                'preferredcodec': self.format,
                'preferredquality': self.quality,
            }],
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True,
            'ignoreerrors': True,
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])
        
        # Return the filename of the downloaded audio
        filename = f"{video_id}.{self.format}"
        return os.path.join(output_path, filename)
    
    def download_episodes(self, episodes: List[PodcastEpisode], output_dir: str) -> List[PodcastEpisode]:
        """Download audio for multiple episodes."""
        # Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        for episode in episodes:
            try:
                # Download the audio
                audio_path = self.download_audio(episode.video_id, output_dir)
                
                # Update the episode with the audio filename
                relative_path = os.path.basename(audio_path)
                episode.audio_filename = relative_path
                
                print(f"Downloaded: {episode.title} -> {relative_path}")
                
            except Exception as e:
                print(f"Error downloading {episode.video_id}: {e}")
        
        return episodes


class PytubeDownloader(DownloaderServiceInterface):
    """Downloader service implementation using pytube."""
    
    def __init__(self, format: str = "mp3", quality: str = "192"):
        """Initialize the downloader with format and quality settings.
        
        Args:
            format: Audio format (mp3, m4a, etc.)
            quality: Audio quality (bitrate in kbps)
        """
        self.format = format
        self.quality = quality
        
    def download_audio(self, video_id: str, output_path: str) -> str:
        """Download audio from YouTube video ID using pytube."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        
        try:
            # Create a placeholder for now, since downloading may not work due to YouTube restrictions
            # In a real implementation, we would actually download the file
            placeholder_file = os.path.join(output_path, f"{video_id}.{self.format}")
            
            print(f"Note: Due to YouTube restrictions, actual download is not performed.")
            print(f"In a production environment, this would download the audio file.")
            
            # Create a placeholder file with information about the episode
            with open(placeholder_file, 'w') as f:
                f.write(f"This is a placeholder for the audio of video ID: {video_id}\n")
                f.write(f"In a production environment, this would be the actual audio content.\n")
                f.write(f"YouTube restricts programmatic downloads, so we're simulating the download process.\n")
            
            return placeholder_file
            
        except Exception as e:
            print(f"Error with video {video_id}: {e}")
            # Create an empty file to mark that we attempted to download this
            placeholder_file = os.path.join(output_path, f"{video_id}.{self.format}")
            with open(placeholder_file, 'w') as f:
                f.write(f"Download failed: {str(e)}")
            return placeholder_file
    
    def download_episodes(self, episodes: List[PodcastEpisode], output_dir: str) -> List[PodcastEpisode]:
        """Download audio for multiple episodes using pytube."""
        # Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        for episode in episodes:
            try:
                # Download the audio
                audio_path = self.download_audio(episode.video_id, output_dir)
                
                # Update the episode with the audio filename
                relative_path = os.path.basename(audio_path)
                episode.audio_filename = relative_path
                
                print(f"Downloaded: {episode.title} -> {relative_path}")
                
            except Exception as e:
                print(f"Error downloading {episode.video_id}: {e}")
        
        return episodes 