#!/usr/bin/env python3
"""
Speaker Identification Script

This script runs the speaker identification stage for all available transcript files
and updates the episodes.json file with the results.

The script will:
1. Load all available transcripts
2. For each transcript, run speaker identification using LLM
3. Update the episodes.json file with speaker information, including:
   - Speaker identification mapping (speaker ID to name)
   - Confidence scores for each identification
   - Word count per speaker
   - Utterance count per speaker

Usage:
    python src/speaker_identification_script.py [--episodes VIDEO_ID1,VIDEO_ID2,...] [--llm-provider openai|deepseek] [--batch-size 10]
"""

import argparse
import logging
import sys
import os
import time
from typing import List, Optional, Dict

from src.services.pipeline_orchestrator import PipelineOrchestrator, PipelineStage
from src.repositories.episode_repository import JsonFileRepository
from src.utils.config import load_config

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("speaker_identification.log")
    ]
)
logger = logging.getLogger("SpeakerIdentification")


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Run speaker identification on podcast transcripts.")
    
    parser.add_argument(
        "episodes", 
        type=str,
        nargs='?',  # Make it optional
        help="Comma-separated list of episode video IDs to process (default: all episodes with transcripts)"
    )
    
    parser.add_argument(
        "--llm-provider",
        type=str,
        choices=["openai", "deepseek"],
        default="openai",
        help="LLM provider to use for speaker identification (default: openai)"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="Force re-identification of speakers even if already processed"
    )
    
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5,
        help="Number of episodes to process in a single batch to avoid API rate limits (default: 5)"
    )
    
    parser.add_argument(
        "--delay",
        type=int,
        default=5,
        help="Delay in seconds between batch processing to avoid API rate limits (default: 5)"
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run without making any actual changes to episodes.json"
    )
    
    args = parser.parse_args()
    
    # Split episodes into list if provided
    if args.episodes:
        args.episodes = [ep.strip() for ep in args.episodes.split(',')]
    
    return args


def get_episodes_with_transcripts(repository: JsonFileRepository, specified_ids: Optional[List[str]] = None):
    """
    Get all episodes with transcripts from the repository.
    
    Args:
        repository: Episode repository
        specified_ids: Optional list of specific episode IDs to filter by
        
    Returns:
        List of episodes with transcripts
    """
    all_episodes = repository.get_all_episodes()
    
    # Filter to episodes with transcripts
    episodes_with_transcripts = [e for e in all_episodes if e.transcript_filename]
    
    if specified_ids:
        # Further filter to only specified episode IDs
        episodes_with_transcripts = [e for e in episodes_with_transcripts if e.video_id in specified_ids]
    
    # Sort by transcript filename to have a consistent order for processing
    episodes_with_transcripts.sort(key=lambda e: e.transcript_filename)
    
    return episodes_with_transcripts


def process_batch(
    orchestrator: PipelineOrchestrator,
    episode_batch: List[str],
    llm_provider: str = "openai",
    force_reidentify: bool = False,
    dry_run: bool = False
) -> Dict:
    """
    Process a batch of episodes.
    
    Args:
        orchestrator: Pipeline orchestrator
        episode_batch: List of episode video IDs to process
        llm_provider: LLM provider to use
        force_reidentify: Whether to force re-identification of speakers
        dry_run: Run without making actual changes
        
    Returns:
        Dictionary with batch statistics
    """
    logger.info(f"Processing batch of {len(episode_batch)} episodes")
    
    try:
        # Run speaker identification stage
        result = orchestrator.execute_stage(
            PipelineStage.IDENTIFY_SPEAKERS,
            episode_ids=episode_batch,
            check_dependencies=False,
            llm_provider=llm_provider,
            force_reidentify=force_reidentify,
            dry_run=dry_run
        )
        
        if result.success:
            logger.info(f"Batch processing completed successfully: {result.message}")
            if result.data:
                processed_episodes = result.data
                logger.info(f"Updated {len(processed_episodes)} episodes with speaker information")
                
                # Log speaker information for each episode
                for episode in processed_episodes:
                    if "speakers" in episode.metadata:
                        logger.info(f"Episode {episode.video_id} ({episode.title}):")
                        
                        # Sort speakers by word count
                        speakers_sorted = sorted(
                            episode.metadata["speakers"].items(),
                            key=lambda x: x[1].get("word_count", 0),
                            reverse=True
                        )
                        
                        for speaker_id, info in speakers_sorted:
                            confidence = info.get("confidence", 0)
                            word_count = info.get("word_count", 0)
                            word_pct = info.get("word_percentage", 0)
                            utterance_count = info.get("utterance_count", 0)
                            
                            logger.info(
                                f"  Speaker {speaker_id}: {info['name']} "
                                f"(confidence: {confidence:.2f}, "
                                f"utterances: {utterance_count}, "
                                f"words: {word_count} ({word_pct:.1f}%))"
                            )
                
                return {
                    "success": True,
                    "processed": len(processed_episodes),
                    "failed": 0
                }
            
            return {
                "success": True,
                "processed": 0,
                "failed": 0
            }
        else:
            logger.error(f"Batch processing failed: {result.message}")
            if result.error:
                logger.error(f"Error: {str(result.error)}")
            
            return {
                "success": False,
                "processed": 0,
                "failed": len(episode_batch)
            }
            
    except Exception as e:
        logger.error(f"Exception during batch processing: {str(e)}")
        return {
            "success": False,
            "processed": 0,
            "failed": len(episode_batch)
        }


def run_speaker_identification(
    episode_ids: Optional[List[str]] = None,
    llm_provider: str = "openai",
    force_reidentify: bool = False,
    batch_size: int = 5,
    delay: int = 5,
    dry_run: bool = False
):
    """
    Run speaker identification on specified episodes or all episodes with transcripts.
    
    Args:
        episode_ids: List of episode video IDs to process (None for all episodes with transcripts)
        llm_provider: LLM provider to use ("openai" or "deepseek")
        force_reidentify: Whether to force re-identification of speakers
        batch_size: Number of episodes to process in a single batch
        delay: Delay in seconds between batch processing
        dry_run: Run without making actual changes
    """
    # Load application configuration
    config = load_config()
    
    # Initialize repository and pipeline orchestrator
    repository = JsonFileRepository(str(config.episodes_db_path))
    orchestrator = PipelineOrchestrator(config)
    
    # Get episodes with transcripts
    if episode_ids:
        logger.info(f"Filtering to specified episodes: {episode_ids}")
    
    episodes = get_episodes_with_transcripts(repository, episode_ids)
    
    if not episodes:
        logger.warning("No episodes with transcripts found")
        return
    
    logger.info(f"Found {len(episodes)} episodes with transcripts")
    
    # Process episodes in batches
    total_episodes = len(episodes)
    batch_count = (total_episodes + batch_size - 1) // batch_size
    
    logger.info(f"Processing {total_episodes} episodes in {batch_count} batches of size {batch_size}")
    
    stats = {
        "total": total_episodes,
        "processed": 0,
        "failed": 0
    }

    # If dry_run, log what would be processed
    if dry_run:
        logger.info("DRY RUN MODE: No changes will be made to episodes.json")
        for episode in episodes:
            logger.info(f"Would process: {episode.video_id} - {episode.title}")
        
        if not input("Continue with dry run? (y/n): ").lower().startswith('y'):
            logger.info("Dry run aborted")
            return
    
    try:
        for i in range(0, total_episodes, batch_size):
            # Get current batch
            batch_episodes = episodes[i:i+batch_size]
            batch_ids = [e.video_id for e in batch_episodes]
            
            logger.info(f"Processing batch {i//batch_size + 1}/{batch_count}: {batch_ids}")
            
            # Process the batch
            batch_stats = process_batch(
                orchestrator,
                batch_ids,
                llm_provider=llm_provider,
                force_reidentify=force_reidentify,
                dry_run=dry_run
            )
            
            # Update stats
            stats["processed"] += batch_stats.get("processed", 0)
            stats["failed"] += batch_stats.get("failed", 0)
            
            # If there are more batches, wait to avoid rate limits
            if i + batch_size < total_episodes:
                logger.info(f"Waiting {delay} seconds before processing next batch...")
                time.sleep(delay)
    
    except KeyboardInterrupt:
        logger.warning("Processing interrupted by user")
    except Exception as e:
        logger.error(f"Error during processing: {str(e)}")
    
    # Log final stats
    logger.info(f"Speaker identification completed with stats: {stats}")


def main():
    """Main entry point for speaker identification script."""
    args = parse_args()
    
    # Parse episode IDs if provided
    episode_ids = None
    if args.episodes:
        episode_ids = args.episodes
        logger.info(f"Processing specific episodes: {episode_ids}")
    else:
        logger.info("Processing all episodes with transcripts")
    
    # Run speaker identification
    run_speaker_identification(
        episode_ids=episode_ids,
        llm_provider=args.llm_provider,
        force_reidentify=args.force,
        batch_size=args.batch_size,
        delay=args.delay,
        dry_run=args.dry_run
    )
    
    logger.info("Speaker identification process completed")


if __name__ == "__main__":
    main() 