"""
Checkpoint Service for Opinion Extraction Pipeline

This module provides functionality for tracking and managing the progress
of the opinion extraction pipeline across multiple episodes, ensuring that
the process can be resumed from the last successful point.
"""

import json
import os
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class CheckpointService:
    """
    Manages checkpoints for the opinion extraction pipeline.
    
    This service tracks the progress of opinion extraction across episodes,
    including which stages have been completed for each episode, allowing
    the extraction process to be resumed efficiently after interruptions.
    """
    
    # Default paths
    DEFAULT_CHECKPOINT_PATH = "data/checkpoints/extraction_checkpoint.json"
    DEFAULT_RAW_OPINIONS_PATH = "data/intermediate/raw_opinions.json"
    
    # Extraction stages
    STAGES = [
        "raw_extraction",
        "categorization",
        "relationship_analysis",
        "opinion_merging",
        "evolution_detection",
        "speaker_tracking"
    ]
    
    def __init__(
        self,
        checkpoint_path: str = DEFAULT_CHECKPOINT_PATH,
        raw_opinions_path: str = DEFAULT_RAW_OPINIONS_PATH
    ):
        """
        Initialize the checkpoint service.
        
        Args:
            checkpoint_path: Path to the checkpoint file
            raw_opinions_path: Path to store raw opinions
        """
        self.checkpoint_path = checkpoint_path
        self.raw_opinions_path = raw_opinions_path
        
        # Ensure directories exist
        os.makedirs(os.path.dirname(checkpoint_path), exist_ok=True)
        os.makedirs(os.path.dirname(raw_opinions_path), exist_ok=True)
        
        # Load checkpoint data
        self.checkpoint_data = self._load_checkpoint()
    
    def _load_checkpoint(self) -> Dict[str, Any]:
        """
        Load checkpoint data from file, or create a new checkpoint if none exists.
        
        Returns:
            Dictionary containing checkpoint data
        """
        if os.path.exists(self.checkpoint_path):
            try:
                with open(self.checkpoint_path, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded checkpoint: {len(data.get('processed_episodes', []))} episodes processed")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load checkpoint file: {e}")
                logger.warning("Creating new checkpoint data")
        
        # Default checkpoint structure
        return {
            "processed_episodes": [],
            "last_processed_episode": None,
            "completed_stages": {},
            "extraction_stats": {
                "total_episodes": 0,
                "total_opinions": 0,
                "total_categories": 0,
                "total_speakers": 0,
                "total_evolution_chains": 0,
                "total_speaker_journeys": 0
            },
            "last_updated": datetime.now().isoformat()
        }
    
    def save_checkpoint(self) -> None:
        """
        Save current checkpoint data to file.
        """
        self.checkpoint_data["last_updated"] = datetime.now().isoformat()
        
        try:
            with open(self.checkpoint_path, 'w') as f:
                json.dump(self.checkpoint_data, f, indent=2)
            logger.info(f"Saved checkpoint: {len(self.checkpoint_data.get('processed_episodes', []))} episodes")
        except IOError as e:
            logger.error(f"Failed to save checkpoint file: {e}")
    
    def get_processed_episodes(self) -> List[str]:
        """
        Get list of episode IDs that have been fully processed.
        
        Returns:
            List of episode IDs
        """
        return self.checkpoint_data.get("processed_episodes", [])
    
    def is_episode_processed(self, episode_id: str) -> bool:
        """
        Check if an episode has been fully processed.
        
        Args:
            episode_id: Episode ID to check
            
        Returns:
            True if the episode has been processed, False otherwise
        """
        return episode_id in self.checkpoint_data.get("processed_episodes", [])
    
    def get_episode_stage(self, episode_id: str) -> str:
        """
        Get the last completed stage for an episode.
        
        Args:
            episode_id: Episode ID to check
            
        Returns:
            Name of the last completed stage, or None if no stages completed
        """
        stages = self.checkpoint_data.get("completed_stages", {})
        return stages.get(episode_id, {}).get("current_stage")
    
    def mark_episode_stage_complete(
        self,
        episode_id: str,
        stage: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Mark a stage as complete for an episode.
        
        Args:
            episode_id: Episode ID
            stage: Stage name (one of STAGES)
            metadata: Optional metadata about the stage completion
        """
        if stage not in self.STAGES:
            logger.warning(f"Unknown stage: {stage}, ignoring")
            return
        
        # Update completed stages
        if "completed_stages" not in self.checkpoint_data:
            self.checkpoint_data["completed_stages"] = {}
        
        if episode_id not in self.checkpoint_data["completed_stages"]:
            self.checkpoint_data["completed_stages"][episode_id] = {
                "stages": [],
                "current_stage": None,
                "stage_metadata": {}
            }
        
        episode_data = self.checkpoint_data["completed_stages"][episode_id]
        
        if stage not in episode_data["stages"]:
            episode_data["stages"].append(stage)
        
        episode_data["current_stage"] = stage
        
        if metadata:
            if "stage_metadata" not in episode_data:
                episode_data["stage_metadata"] = {}
            
            episode_data["stage_metadata"][stage] = metadata
        
        # Check if all stages are complete
        all_stages_complete = all(s in episode_data["stages"] for s in self.STAGES)
        
        if all_stages_complete and episode_id not in self.checkpoint_data["processed_episodes"]:
            self.checkpoint_data["processed_episodes"].append(episode_id)
            self.checkpoint_data["last_processed_episode"] = episode_id
        
        # Save checkpoint
        self.save_checkpoint()
    
    def mark_episode_complete(self, episode_id: str, stats: Optional[Dict[str, Any]] = None) -> None:
        """
        Mark an episode as fully processed.
        
        Args:
            episode_id: Episode ID
            stats: Optional statistics about the extraction
        """
        if episode_id not in self.checkpoint_data["processed_episodes"]:
            self.checkpoint_data["processed_episodes"].append(episode_id)
        
        self.checkpoint_data["last_processed_episode"] = episode_id
        
        if stats:
            extraction_stats = self.checkpoint_data.get("extraction_stats", {})
            
            # Update statistics
            extraction_stats["total_episodes"] = extraction_stats.get("total_episodes", 0) + 1
            extraction_stats["total_opinions"] = extraction_stats.get("total_opinions", 0) + stats.get("opinions", 0)
            extraction_stats["total_categories"] = stats.get("categories", extraction_stats.get("total_categories", 0))
            extraction_stats["total_speakers"] = stats.get("speakers", extraction_stats.get("total_speakers", 0))
            extraction_stats["total_evolution_chains"] = stats.get("evolution_chains", extraction_stats.get("total_evolution_chains", 0))
            extraction_stats["total_speaker_journeys"] = stats.get("speaker_journeys", extraction_stats.get("total_speaker_journeys", 0))
            
            self.checkpoint_data["extraction_stats"] = extraction_stats
        
        # Save checkpoint
        self.save_checkpoint()
    
    def save_raw_opinions(self, raw_opinions: List[Dict[str, Any]]) -> None:
        """
        Save raw opinions to intermediate file.
        
        Args:
            raw_opinions: List of raw opinion dictionaries
        """
        try:
            with open(self.raw_opinions_path, 'w') as f:
                json.dump(raw_opinions, f, indent=2)
            logger.info(f"Saved {len(raw_opinions)} raw opinions to {self.raw_opinions_path}")
        except IOError as e:
            logger.error(f"Failed to save raw opinions: {e}")
    
    def load_raw_opinions(self) -> List[Dict[str, Any]]:
        """
        Load raw opinions from intermediate file.
        
        Returns:
            List of raw opinion dictionaries
        """
        if os.path.exists(self.raw_opinions_path):
            try:
                with open(self.raw_opinions_path, 'r') as f:
                    raw_opinions = json.load(f)
                    logger.info(f"Loaded {len(raw_opinions)} raw opinions from {self.raw_opinions_path}")
                    return raw_opinions
            except (json.JSONDecodeError, IOError) as e:
                logger.error(f"Failed to load raw opinions: {e}")
        
        return []
    
    def get_extraction_stats(self) -> Dict[str, Any]:
        """
        Get statistics about the extraction process.
        
        Returns:
            Dictionary of statistics
        """
        return self.checkpoint_data.get("extraction_stats", {})
    
    def reset_checkpoint(self) -> None:
        """
        Reset the checkpoint data to start extraction from scratch.
        """
        self.checkpoint_data = {
            "processed_episodes": [],
            "last_processed_episode": None,
            "completed_stages": {},
            "extraction_stats": {
                "total_episodes": 0,
                "total_opinions": 0,
                "total_categories": 0,
                "total_speakers": 0,
                "total_evolution_chains": 0,
                "total_speaker_journeys": 0
            },
            "last_updated": datetime.now().isoformat()
        }
        
        self.save_checkpoint()
        logger.info("Reset checkpoint data")
    
    def get_extraction_progress(self) -> Dict[str, Any]:
        """
        Get a summary of the extraction progress.
        
        Returns:
            Dictionary containing progress summary
        """
        total_episodes = self.checkpoint_data.get("extraction_stats", {}).get("total_episodes", 0)
        processed_episodes = len(self.checkpoint_data.get("processed_episodes", []))
        
        stage_counts = {stage: 0 for stage in self.STAGES}
        
        for ep_data in self.checkpoint_data.get("completed_stages", {}).values():
            for stage in ep_data.get("stages", []):
                if stage in stage_counts:
                    stage_counts[stage] += 1
        
        return {
            "total_episodes": total_episodes,
            "processed_episodes": processed_episodes,
            "stage_progress": stage_counts,
            "last_processed": self.checkpoint_data.get("last_processed_episode"),
            "last_updated": self.checkpoint_data.get("last_updated")
        } 