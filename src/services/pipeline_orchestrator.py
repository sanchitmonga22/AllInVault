#!/usr/bin/env python3
"""
Pipeline Orchestrator Service - Manages flexible multi-stage podcast processing pipeline.

This service defines a clear stage-based approach with:
1. Stage definitions for each processing step
2. Flexible execution of individual stages or the entire pipeline
3. Support for processing a single episode or multiple episodes
4. Stage dependency management
"""

import logging
import os
import sys
from abc import ABC, abstractmethod
from enum import Enum, auto
from typing import Dict, List, Optional, Set, Tuple, Any, Callable

from src.models.podcast_episode import PodcastEpisode 
from src.repositories.episode_repository import JsonFileRepository
from src.services.youtube_service import YouTubeService
from src.services.downloader_service import YtDlpDownloader
from src.services.episode_analyzer import EpisodeAnalyzerService
from src.services.batch_transcriber import BatchTranscriberService
from src.services.speaker_identification_service import SpeakerIdentificationService
from src.utils.config import load_config, AppConfig

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("PipelineOrchestrator")


class PipelineStage(Enum):
    """Enum representing each stage in the podcast processing pipeline."""
    FETCH_METADATA = auto()
    ANALYZE_EPISODES = auto()
    DOWNLOAD_AUDIO = auto()
    CONVERT_AUDIO = auto()
    TRANSCRIBE_AUDIO = auto()
    IDENTIFY_SPEAKERS = auto()


class StageResult:
    """Contains the result data and status from a pipeline stage execution."""
    
    def __init__(
        self, 
        success: bool = True,
        data: Any = None,
        message: str = "",
        error: Optional[Exception] = None
    ):
        self.success = success
        self.data = data
        self.message = message
        self.error = error


class AbstractStage(ABC):
    """Abstract base class for all pipeline stages."""
    
    def __init__(
        self, 
        stage_type: PipelineStage,
        repository: JsonFileRepository,
        config: AppConfig
    ):
        self.stage_type = stage_type
        self.repository = repository
        self.config = config
        self.dependencies: Set[PipelineStage] = set()
    
    @abstractmethod
    def execute(
        self, 
        episode_ids: Optional[List[str]] = None,
        **kwargs
    ) -> StageResult:
        """Execute the stage for the specified episodes."""
        pass
    
    @property
    def name(self) -> str:
        """Get the name of this stage."""
        return self.stage_type.name


class FetchMetadataStage(AbstractStage):
    """Stage for fetching episode metadata from YouTube."""
    
    def __init__(self, repository: JsonFileRepository, config: AppConfig):
        super().__init__(PipelineStage.FETCH_METADATA, repository, config)
        self.youtube_service = YouTubeService(self.config.youtube_api_key)
    
    def execute(self, episode_ids: Optional[List[str]] = None, **kwargs) -> StageResult:
        """
        Fetch episode metadata from YouTube.
        
        Args:
            episode_ids: List of video IDs to fetch, or None to fetch based on limit
            **kwargs: 
                limit: Maximum number of episodes to fetch (used only if episode_ids is None)
                
        Returns:
            StageResult containing the fetched episodes
        """
        try:
            limit = kwargs.get('limit')
            
            if episode_ids and len(episode_ids) > 0:
                logger.info(f"Fetching metadata for specific episodes: {episode_ids}")
                episodes = []
                for video_id in episode_ids:
                    episode = self.youtube_service.get_episode_by_id(video_id)
                    if episode:
                        episodes.append(episode)
            else:
                logger.info(f"Fetching up to {limit} episodes for channel ID: {self.config.all_in_channel_id}")
                episodes = self.youtube_service.get_all_episodes(
                    self.config.all_in_channel_id,
                    max_results=limit
                )
            
            logger.info(f"Found {len(episodes)} episodes")
            
            # Save episodes metadata to repository
            self.repository.save_episodes(episodes)
            logger.info(f"Saved episode metadata to {self.config.episodes_db_path}")
            
            return StageResult(success=True, data=episodes, message=f"Successfully fetched {len(episodes)} episodes")
            
        except Exception as e:
            logger.error(f"Error fetching episodes: {str(e)}")
            return StageResult(success=False, error=e, message=f"Failed to fetch episodes: {str(e)}")


class AnalyzeEpisodesStage(AbstractStage):
    """Stage for analyzing episodes to identify full episodes vs shorts."""
    
    def __init__(self, repository: JsonFileRepository, config: AppConfig):
        super().__init__(PipelineStage.ANALYZE_EPISODES, repository, config)
        self.dependencies.add(PipelineStage.FETCH_METADATA)
        self.analyzer = EpisodeAnalyzerService(min_duration=180)
    
    def execute(self, episode_ids: Optional[List[str]] = None, **kwargs) -> StageResult:
        """
        Analyze episodes to identify full episodes vs shorts.
        
        Args:
            episode_ids: List of video IDs to analyze, or None to analyze all
            **kwargs:
                min_duration: Minimum duration in seconds for a full episode
                
        Returns:
            StageResult containing tuple of (full_episodes, shorts)
        """
        try:
            min_duration = kwargs.get('min_duration', 180)
            
            if hasattr(self, 'analyzer'):
                self.analyzer.min_duration = min_duration
            else:
                self.analyzer = EpisodeAnalyzerService(min_duration=min_duration)
            
            if episode_ids and len(episode_ids) > 0:
                # Filter repository data to only process specified episodes
                logger.info(f"Analyzing specific episodes: {episode_ids}")
                episodes_to_analyze = []
                for video_id in episode_ids:
                    episode = self.repository.get_episode(video_id)
                    if episode:
                        episodes_to_analyze.append(episode.to_dict())
                
                # Create temporary JSON file for analysis
                import tempfile
                import json
                
                with tempfile.NamedTemporaryFile(mode='w+', delete=False, suffix='.json') as temp_file:
                    json.dump({"episodes": episodes_to_analyze}, temp_file)
                    temp_path = temp_file.name
                
                try:
                    # Analyze the filtered episodes
                    full_episodes, shorts = self.analyzer.analyze_episodes(temp_path, 0)
                finally:
                    # Clean up temporary file
                    if os.path.exists(temp_path):
                        os.unlink(temp_path)
            else:
                logger.info(f"Analyzing all episodes from {self.config.episodes_db_path}")
                full_episodes, shorts = self.analyzer.analyze_episodes(str(self.config.episodes_db_path), 0)
            
            logger.info(f"Analysis complete: {len(full_episodes)} full episodes, {len(shorts)} shorts")
            
            # Update episode types in repository
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
            
            return StageResult(
                success=True, 
                data=(full_episodes, shorts), 
                message=f"Analysis complete: {len(full_episodes)} full episodes, {len(shorts)} shorts"
            )
            
        except Exception as e:
            logger.error(f"Error analyzing episodes: {str(e)}")
            return StageResult(success=False, error=e, message=f"Failed to analyze episodes: {str(e)}")


class DownloadAudioStage(AbstractStage):
    """Stage for downloading audio files for episodes."""
    
    def __init__(self, repository: JsonFileRepository, config: AppConfig):
        super().__init__(PipelineStage.DOWNLOAD_AUDIO, repository, config)
        self.dependencies.add(PipelineStage.ANALYZE_EPISODES)
        self.downloader = YtDlpDownloader()
    
    def execute(self, episode_ids: Optional[List[str]] = None, **kwargs) -> StageResult:
        """
        Download audio for episodes in WebM format.
        
        Args:
            episode_ids: List of video IDs to download, or None to process all full episodes
            **kwargs:
                output_dir: Directory to save WebM files
                full_episodes_only: Whether to only download for full episodes
                
        Returns:
            StageResult containing the updated episode objects
        """
        try:
            output_dir = kwargs.get('output_dir', str(self.config.webm_dir))
            full_episodes_only = kwargs.get('full_episodes_only', True)
            
            # Determine which episodes to download
            if episode_ids and len(episode_ids) > 0:
                logger.info(f"Downloading audio for specific episodes: {episode_ids}")
                episodes_to_download = []
                for video_id in episode_ids:
                    episode = self.repository.get_episode(video_id)
                    if episode:
                        if not full_episodes_only or (episode.metadata and episode.metadata.get('type') == 'FULL'):
                            episodes_to_download.append(episode)
            else:
                # Get all episodes and filter for full episodes if requested
                logger.info("Downloading audio for all full episodes")
                episodes_to_download = self.repository.get_all_episodes()
                if full_episodes_only:
                    episodes_to_download = [
                        ep for ep in episodes_to_download 
                        if ep.metadata and ep.metadata.get('type') == 'FULL'
                    ]
            
            if not episodes_to_download:
                logger.warning("No episodes to download")
                return StageResult(success=True, data=[], message="No episodes to download")
            
            logger.info(f"Downloading audio for {len(episodes_to_download)} episodes to {output_dir}")
            
            # Download audio in WebM format
            updated_episodes = self.downloader.download_episodes(episodes_to_download, output_dir)
            
            # Update repository with webm filenames
            for episode in updated_episodes:
                existing_episode = self.repository.get_episode(episode.video_id)
                if existing_episode and existing_episode.metadata:
                    episode.metadata = existing_episode.metadata
                self.repository.save_episode(episode)
            
            logger.info("Updated metadata with WebM filenames")
            
            return StageResult(
                success=True, 
                data=updated_episodes, 
                message=f"Successfully downloaded WebM files for {len(updated_episodes)} episodes"
            )
            
        except Exception as e:
            logger.error(f"Error downloading audio: {str(e)}")
            return StageResult(success=False, error=e, message=f"Failed to download audio: {str(e)}")


class ConvertAudioStage(AbstractStage):
    """Stage for converting WebM audio files to MP3."""
    
    def __init__(self, repository: JsonFileRepository, config: AppConfig):
        super().__init__(PipelineStage.CONVERT_AUDIO, repository, config)
        self.dependencies.add(PipelineStage.DOWNLOAD_AUDIO)
        self.downloader = YtDlpDownloader(
            format=self.config.audio_format, 
            quality=self.config.audio_quality
        )
    
    def execute(self, episode_ids: Optional[List[str]] = None, **kwargs) -> StageResult:
        """
        Convert WebM audio files to MP3 format.
        
        Args:
            episode_ids: List of video IDs to convert, or None to process all episodes with WebM files
            **kwargs:
                webm_dir: Directory containing WebM files
                mp3_dir: Directory to save MP3 files
                audio_format: Target audio format
                audio_quality: Audio quality
                max_workers: Maximum number of parallel conversion processes
                delete_webm: Whether to delete WebM files after conversion
                
        Returns:
            StageResult containing the updated episode objects
        """
        try:
            webm_dir = kwargs.get('webm_dir', str(self.config.webm_dir))
            mp3_dir = kwargs.get('mp3_dir', str(self.config.audio_dir))
            audio_format = kwargs.get('audio_format', self.config.audio_format)
            audio_quality = kwargs.get('audio_quality', self.config.audio_quality)
            max_workers = kwargs.get('max_workers', self.config.conversion_threads)
            
            # Determine which episodes to convert
            if episode_ids and len(episode_ids) > 0:
                logger.info(f"Converting audio for specific episodes: {episode_ids}")
                episodes_to_convert = []
                for video_id in episode_ids:
                    episode = self.repository.get_episode(video_id)
                    if episode and episode.webm_filename:
                        episodes_to_convert.append(episode)
            else:
                # Get all episodes with WebM files
                logger.info("Converting audio for all episodes with WebM files")
                all_episodes = self.repository.get_all_episodes()
                episodes_to_convert = [ep for ep in all_episodes if ep.webm_filename]
            
            if not episodes_to_convert:
                logger.warning("No episodes to convert")
                return StageResult(success=True, data=[], message="No episodes to convert")
            
            logger.info(f"Converting {len(episodes_to_convert)} episodes from WebM to {audio_format}")
            
            # Convert WebM to MP3 in parallel
            updated_episodes = self.downloader.convert_episodes(
                episodes_to_convert, 
                webm_dir, 
                mp3_dir, 
                audio_format, 
                audio_quality, 
                max_workers
            )
            
            # Update repository with MP3 filenames
            for episode in updated_episodes:
                self.repository.save_episode(episode)
            
            logger.info(f"Updated metadata with {audio_format} filenames")
            
            return StageResult(
                success=True, 
                data=updated_episodes, 
                message=f"Successfully converted {len(updated_episodes)} episodes to {audio_format}"
            )
            
        except Exception as e:
            logger.error(f"Error converting audio: {str(e)}")
            return StageResult(success=False, error=e, message=f"Failed to convert audio: {str(e)}")


class TranscribeAudioStage(AbstractStage):
    """Stage for transcribing audio files."""
    
    def __init__(self, repository: JsonFileRepository, config: AppConfig):
        super().__init__(PipelineStage.TRANSCRIBE_AUDIO, repository, config)
        self.dependencies.add(PipelineStage.CONVERT_AUDIO)
        self.batch_transcriber = BatchTranscriberService()
    
    def execute(self, episode_ids: Optional[List[str]] = None, **kwargs) -> StageResult:
        """
        Transcribe audio files.
        
        Args:
            episode_ids: List of video IDs to process, or None for all episodes with audio
            **kwargs:
                audio_dir: Directory containing audio files
                transcripts_dir: Directory to store transcriptions
                model: Deepgram model to use
                detect_language: Whether to detect language
                smart_format: Whether to use smart formatting
                utterances: Whether to include utterances
                diarize: Whether to diarize the audio
                
        Returns:
            StageResult containing the updated episode objects
        """
        try:
            audio_dir = kwargs.get('audio_dir', str(self.config.audio_dir))
            transcripts_dir = kwargs.get('transcripts_dir', str(self.config.transcripts_dir))
            
            # Determine episodes to transcribe
            episodes_to_transcribe = []
            if episode_ids and len(episode_ids) > 0:
                logger.info(f"Transcribing specific episodes: {episode_ids}")
                for video_id in episode_ids:
                    episode = self.repository.get_episode(video_id)
                    if episode and episode.audio_filename:
                        episodes_to_transcribe.append(video_id)
            else:
                # Get all episodes with audio files
                logger.info("Transcribing all episodes with audio files")
                all_episodes = self.repository.get_all_episodes()
                episodes_to_transcribe = [
                    ep.video_id for ep in all_episodes if ep.audio_filename
                ]
            
            if not episodes_to_transcribe:
                logger.warning("No episodes to transcribe")
                return StageResult(success=True, data=[], message="No episodes to transcribe")
            
            logger.info(f"Transcribing {len(episodes_to_transcribe)} episodes")
            
            # Configure transcription options
            model = kwargs.get('model', 'nova-3')
            detect_language = kwargs.get('detect_language', False)
            smart_format = kwargs.get('smart_format', True)
            utterances = kwargs.get('utterances', True)
            diarize = kwargs.get('diarize', True)
            
            # Transcribe episodes - only pass parameters that the method accepts
            self.batch_transcriber.transcribe_episodes(
                episodes_to_transcribe,
                audio_dir=audio_dir,
                transcripts_dir=transcripts_dir
            )
            
            # Generate readable text transcripts
            self.batch_transcriber.generate_readable_transcripts(
                episodes_to_transcribe,
                input_dir=transcripts_dir,
                output_dir=transcripts_dir
            )
            
            # Get updated episodes
            updated_episodes = [self.repository.get_episode(vid) for vid in episodes_to_transcribe]
            updated_episodes = [ep for ep in updated_episodes if ep is not None]
            
            return StageResult(
                success=True, 
                data=updated_episodes, 
                message=f"Successfully transcribed {len(episodes_to_transcribe)} episodes"
            )
            
        except Exception as e:
            logger.error(f"Error transcribing audio: {str(e)}")
            return StageResult(success=False, error=e, message=f"Failed to transcribe audio: {str(e)}")


class IdentifySpeakersStage(AbstractStage):
    """Stage for identifying speakers in transcripts."""
    
    def __init__(self, repository: JsonFileRepository, config: AppConfig):
        super().__init__(PipelineStage.IDENTIFY_SPEAKERS, repository, config)
        self.dependencies.add(PipelineStage.TRANSCRIBE_AUDIO)
        
    def execute(self, episode_ids: Optional[List[str]] = None, **kwargs) -> StageResult:
        """
        Identify speakers in transcripts.
        
        Args:
            episode_ids: List of video IDs to process, or None for all episodes with transcripts
            **kwargs:
                transcripts_dir: Directory containing transcripts
                use_llm: Whether to use LLM for speaker identification
                llm_provider: LLM provider to use
                force_reidentify: Whether to force re-identification of speakers
                
        Returns:
            StageResult containing the updated episode objects
        """
        try:
            transcripts_dir = kwargs.get('transcripts_dir', str(self.config.transcripts_dir))
            use_llm = kwargs.get('use_llm', True)
            llm_provider = kwargs.get('llm_provider', 'openai')
            force_reidentify = kwargs.get('force_reidentify', False)
            
            # Initialize speaker service with appropriate settings
            speaker_service = SpeakerIdentificationService(
                use_llm=use_llm,
                llm_provider=llm_provider
            )
            
            # Determine episodes to process
            if episode_ids and len(episode_ids) > 0:
                logger.info(f"Identifying speakers for specific episodes: {episode_ids}")
                episodes_to_process = []
                for video_id in episode_ids:
                    episode = self.repository.get_episode(video_id)
                    if episode and episode.transcript_filename:
                        episodes_to_process.append(episode)
            else:
                # Get all episodes with transcripts
                logger.info("Identifying speakers for all episodes with transcripts")
                all_episodes = self.repository.get_all_episodes()
                episodes_to_process = [ep for ep in all_episodes if ep.transcript_filename]
            
            if not episodes_to_process:
                logger.warning("No episodes to process for speaker identification")
                return StageResult(success=True, data=[], message="No episodes to process for speaker identification")
            
            logger.info(f"Identifying speakers for {len(episodes_to_process)} episodes")
            
            # Identify speakers
            updated_episodes = speaker_service.process_episodes(
                episodes_to_process,
                transcripts_dir=transcripts_dir
            )
            
            logger.info(f"Speaker identification complete for {len(updated_episodes)} episodes")
            
            # Ensure repository is updated
            for episode in updated_episodes:
                self.repository.save_episode(episode)
            
            return StageResult(
                success=True, 
                data=updated_episodes, 
                message=f"Successfully identified speakers for {len(updated_episodes)} episodes"
            )
            
        except Exception as e:
            logger.error(f"Error identifying speakers: {str(e)}")
            return StageResult(success=False, error=e, message=f"Failed to identify speakers: {str(e)}")


class PipelineOrchestrator:
    """
    Orchestrates the podcast processing pipeline with flexible stage execution.
    """
    
    def __init__(self, config: Optional[AppConfig] = None):
        """
        Initialize the pipeline orchestrator.
        
        Args:
            config: Application configuration
        """
        self.config = config or load_config()
        self.repository = JsonFileRepository(str(self.config.episodes_db_path))
        
        # Initialize all pipeline stages
        self.stages: Dict[PipelineStage, AbstractStage] = {
            PipelineStage.FETCH_METADATA: FetchMetadataStage(self.repository, self.config),
            PipelineStage.ANALYZE_EPISODES: AnalyzeEpisodesStage(self.repository, self.config),
            PipelineStage.DOWNLOAD_AUDIO: DownloadAudioStage(self.repository, self.config),
            PipelineStage.CONVERT_AUDIO: ConvertAudioStage(self.repository, self.config),
            PipelineStage.TRANSCRIBE_AUDIO: TranscribeAudioStage(self.repository, self.config),
            PipelineStage.IDENTIFY_SPEAKERS: IdentifySpeakersStage(self.repository, self.config)
        }
        
        # Track stage results
        self.stage_results: Dict[PipelineStage, StageResult] = {}
    
    def execute_stage(
        self, 
        stage: PipelineStage,
        episode_ids: Optional[List[str]] = None,
        check_dependencies: bool = True,
        **kwargs
    ) -> StageResult:
        """
        Execute a single pipeline stage.
        
        Args:
            stage: Stage to execute
            episode_ids: List of video IDs to process
            check_dependencies: Whether to check and execute dependencies first
            **kwargs: Additional arguments for stage execution
            
        Returns:
            StageResult containing the result of stage execution
        """
        # Check if we have an implementation for this stage
        if stage not in self.stages:
            return StageResult(
                success=False, 
                message=f"No implementation found for stage {stage.name}"
            )
            
        # Check dependencies if required
        if check_dependencies:
            dependencies = self.stages[stage].dependencies
            if dependencies:
                logger.info(f"Checking dependencies for {stage.name}: {[d.name for d in dependencies]}")
                
                for dep_stage in dependencies:
                    # If we've already executed this dependency, skip it
                    if dep_stage in self.stage_results and self.stage_results[dep_stage].success:
                        continue
                        
                    logger.info(f"Executing dependency: {dep_stage.name}")
                    dep_result = self.execute_stage(dep_stage, episode_ids, check_dependencies, **kwargs)
                    self.stage_results[dep_stage] = dep_result
                    
                    if not dep_result.success:
                        return StageResult(
                            success=False, 
                            message=f"Dependency {dep_stage.name} failed: {dep_result.message}",
                            error=dep_result.error
                        )
        
        # Execute this stage
        try:
            return self.stages[stage].execute(episode_ids, **kwargs)
        except Exception as e:
            logger.error(f"Error executing stage {stage.name}: {str(e)}")
            return StageResult(success=False, error=e, message=f"Exception during execution: {str(e)}")
    
    def execute_pipeline(
        self, 
        start_stage: Optional[PipelineStage] = None,
        end_stage: Optional[PipelineStage] = None,
        episode_ids: Optional[List[str]] = None,
        **kwargs
    ) -> Dict[PipelineStage, StageResult]:
        """
        Execute the pipeline from start_stage to end_stage.
        
        Args:
            start_stage: Starting stage of the pipeline, or None for first stage
            end_stage: Ending stage of the pipeline, or None for last stage
            episode_ids: Optional list of episode IDs to process
            **kwargs: Keyword arguments to pass to stages
            
        Returns:
            Dictionary mapping stages to their results
        """
        # Determine pipeline stages to execute
        if start_stage is None:
            start_stage = PipelineStage.FETCH_METADATA
            
        if end_stage is None:
            end_stage = PipelineStage.IDENTIFY_SPEAKERS
            
        # Get all stages in the pipeline
        all_stages = [
            PipelineStage.FETCH_METADATA,
            PipelineStage.ANALYZE_EPISODES,
            PipelineStage.DOWNLOAD_AUDIO,
            PipelineStage.CONVERT_AUDIO,
            PipelineStage.TRANSCRIBE_AUDIO,
            PipelineStage.IDENTIFY_SPEAKERS
        ]
        
        # Determine the slice of stages to execute
        start_idx = all_stages.index(start_stage)
        end_idx = all_stages.index(end_stage)
        stages_to_execute = all_stages[start_idx:end_idx+1]
        
        logger.info(f"Executing pipeline from {start_stage.name} to {end_stage.name}")
        
        # Execute the stages
        results = {}
        for stage in stages_to_execute:
            try:
                logger.info(f"Executing stage: {stage.name}")
                result = self.execute_stage(stage, episode_ids, **kwargs)
                results[stage] = result
                self.stage_results[stage] = result
                
                if not result.success:
                    logger.error(f"Stage {stage.name} failed: {result.message}")
                    break
                    
            except Exception as e:
                logger.error(f"Error executing stage {stage.name}: {str(e)}")
                results[stage] = StageResult(success=False, error=e, message=f"Failed to execute stage: {str(e)}")
                break
                
        return results


def main():
    """Module test function."""
    config = load_config()
    orchestrator = PipelineOrchestrator(config)
    
    # Example: Execute full pipeline for most recent 3 episodes
    results = orchestrator.execute_pipeline(limit=3)
    
    # Print results
    for stage, result in results.items():
        print(f"{stage.name}: {'Success' if result.success else 'Failed'} - {result.message}")


if __name__ == "__main__":
    main() 