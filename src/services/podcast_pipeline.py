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
from src.services.speaker_identification_service import SpeakerIdentificationService

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
        min_duration_seconds: int = 120,
        speaker_service: Optional[SpeakerIdentificationService] = None,
        use_llm_for_speakers: bool = True,
        llm_provider: str = "openai"
    ):
        """
        Initialize the podcast pipeline service.
        
        Args:
            config: Application configuration
            min_duration_seconds: Minimum duration for a full episode (in seconds)
            speaker_service: Optional service for speaker identification
            use_llm_for_speakers: Whether to use LLM for speaker identification
            llm_provider: LLM provider to use ('openai' or 'deepseq')
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
        
        # Initialize speaker identification service if not provided
        if speaker_service is None:
            self.speaker_service = SpeakerIdentificationService(
                use_llm=use_llm_for_speakers,
                llm_provider=llm_provider
            )
        else:
            self.speaker_service = speaker_service
        
        # Flags to track which parts of the pipeline have been executed
        self._downloaded_metadata = False
        self._downloaded_audio = False
        self._transcribed_audio = False
        self._identified_speakers = False
    
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
        for episode in updated_episodes:
            # Preserve metadata from previous versions
            existing_episode = self.repository.get_episode(episode.video_id)
            if existing_episode and existing_episode.metadata:
                episode.metadata = existing_episode.metadata
            self.repository.save_episode(episode)
        
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
                # Ensure transcript information is synced with YouTube metadata
                self._sync_episode_metadata(updated_ep)
                updated_episodes.append(updated_ep)
        
        logger.info("Transcription complete")
        
        # Identify speakers after transcription
        if updated_episodes:
            self.identify_speakers(updated_episodes, transcripts_path)
        
        return updated_episodes
    
    def _sync_episode_metadata(self, episode: PodcastEpisode) -> None:
        """
        Sync episode metadata between YouTube and transcript information.
        
        Args:
            episode: PodcastEpisode to update
        """
        if not episode.metadata:
            episode.metadata = {}
            
        # Calculate transcript coverage if we have both durations
        if episode.transcript_duration and episode.metadata.get('duration_seconds'):
            coverage = min(100.0, (episode.transcript_duration / episode.metadata['duration_seconds']) * 100)
            episode.metadata['transcript_coverage'] = round(coverage, 2)
            
            # Add speaker information if available
            if episode.transcript_utterances and not episode.speaker_count:
                # Try to estimate from transcript content
                # In future: could analyze transcript file to get exact count
                episode.speaker_count = min(4, max(1, episode.transcript_utterances // 10))
                
            # Save the updated episode
            self.repository.update_episode(episode)
            logger.info(f"Updated metadata for episode {episode.video_id}: " 
                       f"Coverage: {episode.metadata['transcript_coverage']}%, "
                       f"Speakers: {episode.speaker_count}")
    
    def identify_speakers(
        self,
        episodes: Optional[List[PodcastEpisode]] = None,
        transcripts_dir: str = "data/transcripts",
        force_reidentify: bool = False
    ) -> List[PodcastEpisode]:
        """
        Identify speakers in podcast episodes.
        
        Args:
            episodes: List of episodes to process (if None, will use all episodes)
            transcripts_dir: Directory containing transcript files
            force_reidentify: Whether to force reidentification of speakers even if already done
            
        Returns:
            List of updated episodes
        """
        logger.info("Starting speaker identification process")
        
        # Get episodes if not provided
        if episodes is None:
            episodes = self.repository.get_all_episodes()
        
        # Filter episodes that have transcripts
        episodes_to_process = []
        for episode in episodes:
            if episode.transcript_filename:
                if force_reidentify or not episode.metadata or "speakers" not in episode.metadata:
                    episodes_to_process.append(episode)
        
        if not episodes_to_process:
            logger.info("No episodes to process for speaker identification")
            return []
        
        logger.info(f"Identifying speakers in {len(episodes_to_process)} episodes")
        updated_episodes = []
        
        for episode in episodes_to_process:
            try:
                logger.info(f"Processing episode: {episode.title}")
                # Process transcript to identify speakers
                updated_episode = self.speaker_service.process_episode(episode, transcripts_dir)
                
                # Save updated episode
                self.repository.update_episode(updated_episode)
                updated_episodes.append(updated_episode)
                
                # Log identified speakers
                if "speakers" in updated_episode.metadata:
                    logger.info(f"Speakers identified in {updated_episode.title}:")
                    for speaker_id, speaker_info in updated_episode.metadata["speakers"].items():
                        name = speaker_info["name"]
                        confidence = speaker_info.get("confidence", 0)
                        utterances = speaker_info.get("utterance_count", 0)
                        is_unknown = speaker_info.get("is_unknown", False)
                        is_guest = speaker_info.get("is_guest", False)
                        
                        speaker_type = "GUEST" if is_guest else "HOST"
                        if is_unknown:
                            speaker_type = "UNKNOWN"
                        
                        logger.info(f"  Speaker {speaker_id}: {name} "
                                  f"({speaker_type}, confidence: {confidence:.2f}, "
                                  f"utterances: {utterances})")
            except Exception as e:
                logger.error(f"Error processing episode {episode.video_id}: {e}")
        
        self._identified_speakers = True
        logger.info(f"Speaker identification completed for {len(updated_episodes)} episodes")
        
        return updated_episodes
    
    def run_pipeline(
        self, 
        num_episodes: int = 5, 
        download_audio: bool = True, 
        transcribe: bool = True,
        identify_speakers: bool = True,
        use_llm_for_speakers: bool = True
    ) -> None:
        """
        Run the entire podcast processing pipeline.
        
        Args:
            num_episodes: Number of episodes to process
            download_audio: Whether to download audio
            transcribe: Whether to transcribe audio
            identify_speakers: Whether to identify speakers
            use_llm_for_speakers: Whether to use LLM for speaker identification
        """
        try:
            # Step 1: Fetch episodes
            if not self._downloaded_metadata:
                logger.info(f"Fetching up to {num_episodes} episodes")
                self.fetch_episodes(num_episodes)
                self._downloaded_metadata = True
            else:
                logger.info("Using previously downloaded metadata")
            
            # Step 2: Analyze episodes
            if not self._downloaded_audio:
                logger.info("Analyzing episodes to identify full episodes")
                full_episodes, _ = self.analyze_episodes(limit=num_episodes)
                
                # Step 3: Download audio for full episodes
                if download_audio:
                    logger.info("Downloading audio for full episodes")
                    # Limit to num_episodes
                    if len(full_episodes) > num_episodes:
                        full_episodes = full_episodes[:num_episodes]
                    self.download_audio(full_episodes)
                    self._downloaded_audio = True
                else:
                    logger.info("Skipping audio download (--skip-download flag used)")
            else:
                logger.info("Using previously downloaded audio")
            
            # Step 4: Transcribe audio
            episodes_with_audio = []
            all_episodes = self.repository.get_all_episodes()
            for episode in all_episodes:
                if episode.audio_filename:
                    # Check that audio file actually exists
                    audio_path = os.path.join(self.config.audio_dir, episode.audio_filename)
                    if os.path.exists(audio_path):
                        episodes_with_audio.append(episode)
                    
                    # Limit to num_episodes
                    if len(episodes_with_audio) >= num_episodes:
                        break
            
            if transcribe and not self._transcribed_audio and episodes_with_audio:
                logger.info(f"Transcribing {len(episodes_with_audio)} episodes")
                self.transcribe_audio(episodes_with_audio)
                self._transcribed_audio = True
            elif not transcribe:
                logger.info("Skipping transcription (--skip-transcription flag used)")
            elif self._transcribed_audio:
                logger.info("Using previously generated transcripts")
            else:
                logger.info("No episodes with audio found for transcription")
            
            # Step 5: Identify speakers in transcripts
            episodes_with_transcripts = []
            all_episodes = self.repository.get_all_episodes()
            for episode in all_episodes:
                if episode.transcript_filename:
                    # Check that transcript file actually exists
                    transcript_path = os.path.join(self.config.transcripts_dir, episode.transcript_filename)
                    if os.path.exists(transcript_path):
                        episodes_with_transcripts.append(episode)
                    
                    # Limit to num_episodes
                    if len(episodes_with_transcripts) >= num_episodes:
                        break
            
            if identify_speakers and not self._identified_speakers and episodes_with_transcripts:
                # Configure the speaker service if needed
                if use_llm_for_speakers != self.speaker_service.use_llm:
                    self.speaker_service = SpeakerIdentificationService(
                        use_llm=use_llm_for_speakers,
                        llm_provider="openai"
                    )
                
                logger.info(f"Identifying speakers in {len(episodes_with_transcripts)} episodes")
                self.identify_speakers(episodes_with_transcripts)
                self._identified_speakers = True
            elif not identify_speakers:
                logger.info("Skipping speaker identification")
            elif self._identified_speakers:
                logger.info("Using previously identified speakers")
            else:
                logger.info("No episodes with transcripts found for speaker identification")
            
            logger.info("Pipeline execution completed")
            
        except Exception as e:
            logger.error(f"Error in pipeline execution: {e}")
            raise

def main():
    """Run the podcast pipeline as a standalone script."""
    from argparse import ArgumentParser
    
    parser = ArgumentParser(description="Process podcast episodes from YouTube")
    parser.add_argument("--limit", "-l", type=int, default=5, help="Number of episodes to process")
    parser.add_argument("--skip-download", "-s", action="store_true", help="Skip audio download")
    parser.add_argument("--skip-transcribe", "-t", action="store_true", help="Skip transcription")
    
    args = parser.parse_args()
    
    pipeline = PodcastPipelineService()
    pipeline.run_pipeline(
        num_episodes=args.limit,
        download_audio=not args.skip_download,
        transcribe=not args.skip_transcribe
    )

if __name__ == "__main__":
    main() 