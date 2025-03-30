#!/usr/bin/env python3
"""
Podcast Pipeline Service - Orchestrates the entire podcast processing workflow.

This service coordinates:
1. Episode retrieval from YouTube
2. Episode analysis to identify full episodes vs shorts
3. Audio download for full episodes
4. Transcription of downloaded audio
"""

import os
import sys
from typing import List, Dict, Optional, Tuple
import logging

from src.models.podcast_episode import PodcastEpisode
from src.repositories.episode_repository import JsonFileRepository
from src.services.youtube_service import YouTubeService
from src.services.downloader_service import YtDlpDownloader
from src.services.episode_analyzer import EpisodeAnalyzerService
from src.services.batch_transcriber import BatchTranscriberService
from src.utils.config import load_config, AppConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PodcastPipeline")

class PodcastPipelineService:
    """
    Service to orchestrate the entire podcast processing pipeline.
    """
    
    def __init__(
        self,
        config: Optional[AppConfig] = None,
        min_duration_seconds: int = 120
    ):
        """
        Initialize the podcast pipeline service.
        
        Args:
            config: Application configuration
            min_duration_seconds: Minimum duration for a full episode (in seconds)
        """
        self.config = config or load_config()
        self.min_duration_seconds = min_duration_seconds
        
        # Initialize services
        self.youtube_service = YouTubeService(self.config.youtube_api_key)
        self.downloader = YtDlpDownloader(
            format=self.config.audio_format, 
            quality=self.config.audio_quality
        )
        self.analyzer = EpisodeAnalyzerService(min_duration=self.min_duration_seconds)
        self.batch_transcriber = BatchTranscriberService()
        
        # Initialize repository
        self.repository = JsonFileRepository(str(self.config.episodes_db_path))
    
    def fetch_episodes(self, limit: Optional[int] = None) -> List[PodcastEpisode]:
        """
        Fetch episodes metadata from YouTube.
        
        Args:
            limit: Maximum number of episodes to fetch
            
        Returns:
            List of podcast episodes
        """
        logger.info(f"Fetching episodes for channel ID: {self.config.all_in_channel_id}")
        
        # Get episodes from YouTube
        episodes = self.youtube_service.get_all_episodes(
            self.config.all_in_channel_id,
            max_results=limit
        )
        
        logger.info(f"Found {len(episodes)} episodes")
        
        # Save episodes metadata to repository
        self.repository.save_episodes(episodes)
        logger.info(f"Saved episode metadata to {self.config.episodes_db_path}")
        
        return episodes
    
    def analyze_episodes(self, episodes_json_path: Optional[str] = None, limit: int = 0) -> Tuple[List[PodcastEpisode], List[PodcastEpisode]]:
        """
        Analyze episodes to identify full episodes vs shorts.
        
        Args:
            episodes_json_path: Path to the episodes JSON file (optional)
            limit: Maximum number of episodes to analyze (0 for all)
            
        Returns:
            Tuple of (full_episodes, shorts)
        """
        path = episodes_json_path or str(self.config.episodes_db_path)
        
        logger.info(f"Analyzing episodes from {path}")
        full_episodes, shorts = self.analyzer.analyze_episodes(path, limit)
        
        logger.info(f"Analysis complete: {len(full_episodes)} full episodes, {len(shorts)} shorts")
        
        # Add episode type to each episode in the repository
        for episode in full_episodes:
            episode_obj = self.repository.get_episode(episode['video_id'])
            if episode_obj:
                episode_obj.metadata = episode_obj.metadata or {}
                episode_obj.metadata['type'] = 'FULL'
                episode_obj.metadata['duration_seconds'] = episode.get('duration_seconds')
                self.repository.save_episode(episode_obj)
        
        for episode in shorts:
            episode_obj = self.repository.get_episode(episode['video_id'])
            if episode_obj:
                episode_obj.metadata = episode_obj.metadata or {}
                episode_obj.metadata['type'] = 'SHORT'
                episode_obj.metadata['duration_seconds'] = episode.get('duration_seconds')
                self.repository.save_episode(episode_obj)
        
        logger.info("Episode types updated in repository")
        
        return full_episodes, shorts
    
    def download_audio(self, episodes: List[Dict], output_dir: Optional[str] = None) -> List[PodcastEpisode]:
        """
        Download audio for the specified episodes.
        
        Args:
            episodes: List of episode dictionaries
            output_dir: Directory to save audio files
            
        Returns:
            List of updated podcast episodes
        """
        audio_dir = output_dir or str(self.config.audio_dir)
        
        logger.info(f"Downloading audio for {len(episodes)} episodes to {audio_dir}")
        
        # Convert dicts to PodcastEpisode objects if needed
        episode_objects = []
        for ep in episodes:
            if isinstance(ep, dict):
                episode_obj = self.repository.get_episode(ep['video_id'])
                if episode_obj:
                    episode_objects.append(episode_obj)
            else:
                episode_objects.append(ep)
        
        # Download audio
        updated_episodes = self.downloader.download_episodes(episode_objects, audio_dir)
        
        # Update repository with audio filenames
        self.repository.save_episodes(updated_episodes)
        logger.info("Updated metadata with audio filenames")
        
        return updated_episodes
    
    def transcribe_audio(
        self, 
        episodes: List[PodcastEpisode], 
        audio_dir: Optional[str] = None,
        transcripts_dir: Optional[str] = None
    ) -> List[PodcastEpisode]:
        """
        Transcribe audio for the specified episodes.
        
        Args:
            episodes: List of podcast episodes
            audio_dir: Directory containing audio files
            transcripts_dir: Directory to save transcripts
            
        Returns:
            List of updated podcast episodes
        """
        audio_path = audio_dir or str(self.config.audio_dir)
        transcripts_path = transcripts_dir or str(self.config.transcripts_dir)
        
        logger.info(f"Transcribing {len(episodes)} episodes")
        
        # Use the batch transcriber service to handle transcription
        self.batch_transcriber.transcribe_episodes(
            [ep.video_id for ep in episodes],
            audio_dir=audio_path,
            transcripts_dir=transcripts_path
        )
        
        # Generate readable text transcripts
        self.batch_transcriber.generate_readable_transcripts(
            [ep.video_id for ep in episodes],
            input_dir=transcripts_path,
            output_dir=transcripts_path
        )
        
        # Reload episodes to get updated transcript information
        updated_episodes = []
        for episode in episodes:
            updated_ep = self.repository.get_episode(episode.video_id)
            if updated_ep:
                updated_episodes.append(updated_ep)
        
        logger.info("Transcription complete")
        return updated_episodes
    
    def run_pipeline(self, num_episodes: int = 5, download_audio: bool = True, transcribe: bool = True) -> None:
        """
        Run the full podcast processing pipeline.
        
        Args:
            num_episodes: Maximum number of episodes to process
            download_audio: Whether to download audio files
            transcribe: Whether to transcribe audio files
        """
        logger.info(f"Starting podcast pipeline with {num_episodes} episodes")
        
        # Step 1: Fetch episode metadata
        self.fetch_episodes(num_episodes)
        
        # Step 2: Analyze episodes to identify full episodes vs shorts
        full_episodes, _ = self.analyze_episodes(limit=num_episodes)
        
        # Step 3: Download audio for full episodes
        if download_audio:
            updated_episodes = self.download_audio(full_episodes)
        else:
            logger.info("Skipping audio download")
            # Get episode objects from repository
            updated_episodes = []
            for ep in full_episodes:
                ep_obj = self.repository.get_episode(ep['video_id'])
                if ep_obj and ep_obj.audio_filename:
                    updated_episodes.append(ep_obj)
        
        # Step 4: Transcribe audio
        if transcribe and updated_episodes:
            logger.info(f"Transcribing {len(updated_episodes)} episodes")
            transcribed_episodes = self.transcribe_audio(updated_episodes)
            logger.info(f"Transcribed {len(transcribed_episodes)} episodes")
        elif not transcribe:
            logger.info("Skipping transcription")
        else:
            logger.warning("No episodes with audio available for transcription")
        
        logger.info("Pipeline execution complete")

# Command-line interface
def main():
    """Run the pipeline as a standalone script."""
    pipeline = PodcastPipelineService()
    pipeline.run_pipeline()

if __name__ == "__main__":
    main() 