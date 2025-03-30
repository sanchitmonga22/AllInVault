#!/usr/bin/env python
"""
CLI tool for identifying speakers in podcast episode transcripts.
"""

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import List, Optional

# Add parent directory to path to allow running as script
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

from src.repositories.episode_repository import JsonFileRepository
from src.services.speaker_identification_service import SpeakerIdentificationService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Identify speakers in podcast transcripts.")
    parser.add_argument(
        "--episodes", type=str, default="data/json/episodes.json",
        help="Path to episodes JSON file (default: data/json/episodes.json)"
    )
    parser.add_argument(
        "--transcripts", type=str, default="data/transcripts",
        help="Directory containing transcript files (default: data/transcripts)"
    )
    parser.add_argument(
        "--video-id", type=str,
        help="Process only a specific episode by video ID"
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force reprocessing of episodes that already have speaker data"
    )
    parser.add_argument(
        "--use-llm", action="store_true",
        help="Use LLM (Large Language Model) for speaker identification"
    )
    parser.add_argument(
        "--llm-provider", type=str, choices=["openai", "deepseq"], default="openai",
        help="LLM provider to use (default: openai)"
    )
    parser.add_argument(
        "--llm-model", type=str,
        help="Model name to use with the LLM provider (provider-specific)"
    )
    parser.add_argument(
        "--unknown-only", action="store_true",
        help="Only show episodes with unknown speakers"
    )
    parser.add_argument(
        "--min-confidence", type=float, default=0.0,
        help="Only show speakers with confidence below this threshold (0.0-1.0)"
    )
    return parser.parse_args()


def identify_speakers(args) -> int:
    """
    Identify speakers in podcast episode transcripts.
    
    Args:
        args: Command-line arguments
        
    Returns:
        Exit code (0 for success, non-zero for error)
    """
    try:
        # Set up repository and services
        episodes_path = args.episodes
        transcripts_dir = args.transcripts
        
        # Ensure directories exist
        Path(transcripts_dir).mkdir(parents=True, exist_ok=True)
        
        # Set up repository
        episode_repo = JsonFileRepository(episodes_path)
        
        # Set up speaker service
        speaker_service = SpeakerIdentificationService(
            use_llm=args.use_llm,
            llm_provider=args.llm_provider,
            llm_model=args.llm_model
        )
        
        # Get episodes to process
        if args.video_id:
            episode = episode_repo.get_episode(args.video_id)
            if not episode:
                logger.error(f"Episode with video ID {args.video_id} not found")
                return 1
            episodes = [episode]
        else:
            episodes = episode_repo.get_all_episodes()
        
        # Filter episodes that have transcripts
        episodes_to_process = [
            ep for ep in episodes if ep.transcript_filename and (
                args.force or 
                "speakers" not in ep.metadata or 
                not ep.metadata["speakers"]
            )
        ]
        
        if not episodes_to_process:
            logger.info("No episodes to process")
            return 0
        
        # Process episodes
        logger.info(f"Processing {len(episodes_to_process)} episodes...")
        num_processed = 0
        
        for episode in episodes_to_process:
            try:
                # Process episode to identify speakers
                updated_episode = speaker_service.process_episode(episode, transcripts_dir)
                
                # Save updated episode
                episode_repo.update_episode(updated_episode)
                num_processed += 1
                
                # Display results
                if "speakers" in updated_episode.metadata:
                    logger.info(f"\nSpeakers in {updated_episode.title}:")
                    show_episode = not args.unknown_only  # Default show all episodes
                    
                    for speaker_id, speaker_info in updated_episode.metadata["speakers"].items():
                        name = speaker_info["name"]
                        confidence = speaker_info.get("confidence", 0)
                        utterances = speaker_info.get("utterance_count", 0)
                        is_unknown = speaker_info.get("is_unknown", False)
                        is_guest = speaker_info.get("is_guest", False)
                        
                        # Check if we should show this speaker (unknown or low confidence)
                        show_speaker = (
                            confidence < args.min_confidence or 
                            is_unknown or 
                            (args.unknown_only and name.startswith("Unknown Speaker"))
                        )
                        
                        if show_speaker:
                            show_episode = True
                        
                        if not args.unknown_only or show_speaker:
                            speaker_type = "GUEST" if is_guest else "HOST"
                            if is_unknown:
                                speaker_type = "UNKNOWN"
                            
                            logger.info(f"  Speaker {speaker_id}: {name} "
                                       f"({speaker_type}, confidence: {confidence:.2f}, "
                                       f"utterances: {utterances})")
                    
                    if not show_episode:
                        logger.info(f"  No unknown speakers found in this episode")
            except Exception as e:
                logger.error(f"Error processing episode {episode.video_id}: {e}")
        
        logger.info(f"\nProcessed {num_processed} episodes")
        return 0
    
    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


def main():
    """Main entry point for the script."""
    args = parse_args()
    return identify_speakers(args)


if __name__ == "__main__":
    sys.exit(main()) 