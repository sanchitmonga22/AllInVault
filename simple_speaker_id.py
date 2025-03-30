#!/usr/bin/env python3
"""
Simple Speaker Identification

This script identifies speakers in a podcast transcript using existing services.
It takes a video ID, uses the existing SpeakerIdentificationService with the LLM
to identify which speaker is which from the transcript text file.
"""

import argparse
import logging
import sys
from pathlib import Path
from dotenv import load_dotenv

# Add parent directory to path to allow importing modules
sys.path.insert(0, str(Path(__file__).resolve().parent))

from src.repositories.episode_repository import JsonFileRepository
from src.services.speaker_identification_service import SpeakerIdentificationService

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Load environment variables from .env file
load_dotenv()

def main():
    """Main entry point for the script."""
    parser = argparse.ArgumentParser(description="Simple speaker identification using LLM")
    parser.add_argument("--video-id", type=str, required=True, help="YouTube video ID of the episode")
    parser.add_argument("--episodes", type=str, default="data/json/episodes.json", help="Path to episodes JSON file")
    parser.add_argument("--transcripts", type=str, default="data/transcripts", help="Directory containing transcript files")
    parser.add_argument("--use-llm", action="store_true", help="Use LLM (Large Language Model) for speaker identification")
    parser.add_argument("--llm-provider", type=str, choices=["openai", "deepseq"], default="openai", help="LLM provider to use")
    parser.add_argument("--force", action="store_true", help="Force reprocessing even if speakers already identified")
    args = parser.parse_args()
    
    try:
        # Initialize repository
        episode_repo = JsonFileRepository(args.episodes)
        
        # Get the episode
        episode = episode_repo.get_episode(args.video_id)
        if not episode:
            logger.error(f"Episode with video ID {args.video_id} not found")
            return 1
        
        # Check if the episode has a transcript
        if not episode.transcript_filename:
            logger.error(f"Episode {args.video_id} does not have a transcript file")
            return 1
        
        # Check if the episode already has speaker data and force is not enabled
        if not args.force and episode.metadata and "speakers" in episode.metadata:
            logger.info(f"Episode {args.video_id} already has speaker data. Use --force to reprocess.")
            return 0
        
        # Initialize speaker service
        speaker_service = SpeakerIdentificationService(
            use_llm=args.use_llm,
            llm_provider=args.llm_provider
        )
        
        # Process the episode to identify speakers
        logger.info(f"Processing episode: {episode.title}")
        updated_episode = speaker_service.process_episode(episode, args.transcripts)
        
        # Save updated episode
        episode_repo.update_episode(updated_episode)
        
        # Display results
        if "speakers" in updated_episode.metadata:
            logger.info(f"\nSpeakers in {updated_episode.title}:")
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
        else:
            logger.info("No speakers identified in this episode")
        
        logger.info(f"Speaker identification completed for {updated_episode.title}")
        return 0
        
    except Exception as e:
        logger.error(f"Error: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main()) 