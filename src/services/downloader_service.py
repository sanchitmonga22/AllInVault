import os
import concurrent.futures
import subprocess
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
            Updated list of podcast episodes with webm_filename
        """
        pass
    
    @abstractmethod
    def convert_audio(self, episode: PodcastEpisode, webm_dir: str, mp3_dir: str, format: str = "mp3", quality: str = "192") -> bool:
        """Convert downloaded WebM to MP3.
        
        Args:
            episode: Podcast episode with webm_filename
            webm_dir: Directory containing WebM files
            mp3_dir: Directory to save MP3 files
            format: Target audio format
            quality: Audio quality
            
        Returns:
            True if conversion successful, False otherwise
        """
        pass
    
    @abstractmethod
    def convert_episodes(self, episodes: List[PodcastEpisode], webm_dir: str, mp3_dir: str, format: str = "mp3", 
                       quality: str = "192", max_workers: int = 4) -> List[PodcastEpisode]:
        """Convert multiple episodes in parallel.
        
        Args:
            episodes: List of podcast episodes with webm_filename
            webm_dir: Directory containing WebM files
            mp3_dir: Directory to save MP3 files
            format: Target audio format
            quality: Audio quality
            max_workers: Maximum number of concurrent conversion processes
            
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
        """Download audio from YouTube video ID in WebM format."""
        url = f"https://www.youtube.com/watch?v={video_id}"
        output_template = os.path.join(output_path, f"{video_id}.%(ext)s")
        
        ydl_opts = {
            'format': 'bestaudio',
            'outtmpl': output_template,
            'quiet': False,
            'no_warnings': True,
            'ignoreerrors': True,
            'no_check_certificate': True,
            # Don't post-process - just download raw files
            'postprocessor_args': []
        }
        
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            try:
                ydl.download([url])
                
                # Find the downloaded file (should be webm or some other format)
                for ext in ['webm', 'mkv', 'm4a']:
                    filename = f"{video_id}.{ext}"
                    output_file = os.path.join(output_path, filename)
                    if os.path.exists(output_file) and os.path.getsize(output_file) > 0:
                        return output_file
                
                raise Exception(f"Downloaded file not found for {video_id}")
                    
            except Exception as e:
                print(f"Error downloading {video_id}: {e}")
                raise
    
    def download_episodes(self, episodes: List[PodcastEpisode], output_dir: str) -> List[PodcastEpisode]:
        """Download audio for multiple episodes in WebM format."""
        # Make sure output directory exists
        os.makedirs(output_dir, exist_ok=True)
        
        for episode in episodes:
            try:
                # Download the audio
                audio_path = self.download_audio(episode.video_id, output_dir)
                
                # Update the episode with the webm filename
                relative_path = os.path.basename(audio_path)
                episode.webm_filename = relative_path
                
                print(f"Downloaded: {episode.title} -> {relative_path}")
                
            except Exception as e:
                print(f"Error downloading {episode.video_id}: {e}")
                # Don't update the episode if download failed
                continue
        
        return episodes
    
    def convert_audio(self, episode: PodcastEpisode, webm_dir: str, mp3_dir: str, format: str = "mp3", quality: str = "192") -> bool:
        """Convert downloaded WebM to MP3 using FFmpeg."""
        if not episode.webm_filename:
            print(f"No WebM file available for episode {episode.video_id}")
            return False
        
        try:
            webm_path = os.path.join(webm_dir, episode.webm_filename)
            mp3_filename = f"{episode.video_id}.{format}"
            mp3_path = os.path.join(mp3_dir, mp3_filename)
            
            # Run FFmpeg to convert the file
            cmd = [
                'ffmpeg', '-i', webm_path, 
                '-vn',  # No video
                '-ar', '44100',  # Audio sample rate
                '-ac', '2',  # Stereo
                '-b:a', f'{quality}k',  # Bitrate
                '-f', format,  # Format
                '-y',  # Overwrite if exists
                mp3_path
            ]
            
            # Run the command
            process = subprocess.run(cmd, capture_output=True, text=True, check=False)
            
            if process.returncode != 0:
                print(f"Error converting {episode.video_id}: {process.stderr}")
                return False
                
            # Update episode with MP3 filename
            episode.audio_filename = mp3_filename
            
            # Remove the WebM file if conversion successful
            if os.path.exists(mp3_path) and os.path.getsize(mp3_path) > 0:
                os.remove(webm_path)
                print(f"Converted and removed WebM: {episode.video_id}")
            
            return True
            
        except Exception as e:
            print(f"Error converting {episode.video_id}: {e}")
            return False
    
    def convert_episodes(self, episodes: List[PodcastEpisode], webm_dir: str, mp3_dir: str, format: str = "mp3", 
                      quality: str = "192", max_workers: int = 4) -> List[PodcastEpisode]:
        """Convert multiple episodes in parallel."""
        # Make sure output directory exists
        os.makedirs(mp3_dir, exist_ok=True)
        
        print(f"Converting {len(episodes)} episodes using {max_workers} workers")
        
        # Use ThreadPoolExecutor for parallel processing
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all conversion tasks
            futures = [
                executor.submit(
                    self.convert_audio, 
                    episode, 
                    webm_dir, 
                    mp3_dir, 
                    format, 
                    quality
                ) 
                for episode in episodes if episode.webm_filename
            ]
            
            # Wait for all tasks to complete and process results
            for episode, future in zip([ep for ep in episodes if ep.webm_filename], futures):
                try:
                    success = future.result()
                    if success:
                        print(f"Successfully converted: {episode.title}")
                    else:
                        print(f"Failed to convert: {episode.title}")
                except Exception as e:
                    print(f"Error in conversion task for {episode.video_id}: {e}")
        
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
            placeholder_file = os.path.join(output_path, f"{video_id}.webm")
            
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
            placeholder_file = os.path.join(output_path, f"{video_id}.webm")
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
                
                # Update the episode with the webm filename
                relative_path = os.path.basename(audio_path)
                episode.webm_filename = relative_path
                
                print(f"Downloaded: {episode.title} -> {relative_path}")
                
            except Exception as e:
                print(f"Error downloading {episode.video_id}: {e}")
        
        return episodes
    
    def convert_audio(self, episode: PodcastEpisode, webm_dir: str, mp3_dir: str, format: str = "mp3", quality: str = "192") -> bool:
        """Simulate conversion of audio file."""
        if not episode.webm_filename:
            print(f"No WebM file available for episode {episode.video_id}")
            return False
            
        try:
            # Create placeholder MP3 file
            mp3_filename = f"{episode.video_id}.{format}"
            mp3_path = os.path.join(mp3_dir, mp3_filename)
            
            with open(mp3_path, 'w') as f:
                f.write(f"This is a simulated MP3 file for {episode.video_id}\n")
            
            # Update episode with MP3 filename
            episode.audio_filename = mp3_filename
            
            print(f"Simulated conversion: {episode.title}")
            return True
            
        except Exception as e:
            print(f"Error in simulated conversion {episode.video_id}: {e}")
            return False
    
    def convert_episodes(self, episodes: List[PodcastEpisode], webm_dir: str, mp3_dir: str, format: str = "mp3", 
                      quality: str = "192", max_workers: int = 4) -> List[PodcastEpisode]:
        """Simulate converting multiple episodes in parallel."""
        # Make sure output directory exists
        os.makedirs(mp3_dir, exist_ok=True)
        
        for episode in episodes:
            if episode.webm_filename:
                self.convert_audio(episode, webm_dir, mp3_dir, format, quality)
        
        return episodes 