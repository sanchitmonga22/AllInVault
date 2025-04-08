#!/usr/bin/env python3
"""
Resumable Opinion Extraction Example

This script demonstrates how to use the checkpoint service for resumable
opinion extraction from podcast transcripts.

The opinion extraction pipeline produces structured data in the following format:

# Raw Opinion Structure
```json
{
  "opinions": [
    {
      "id": "unique-id-for-opinion",
      "title": "Short descriptive title of the opinion",
      "description": "Detailed description of the opinion",
      "content": "Direct quote or paraphrased content of the opinion",
      "speakers": [
        {
          "speaker_id": "speaker1",
          "speaker_name": "Speaker Name",
          "stance": "support", // or "oppose", "neutral"
          "reasoning": "Reasoning for their stance on this opinion",
          "start_time": 123.45, // Timestamp in seconds
          "end_time": 167.89    // Timestamp in seconds
        }
      ],
      "category": "Politics", // One of predefined categories or custom
      "keywords": ["keyword1", "keyword2"],
      "episode_id": "episode-123"
    }
  ]
}
```

# Final Opinion Structure
After processing through the pipeline, the final Opinion objects contain:

- Consolidated opinions across episodes
- Evolution chains showing opinion development
- Speaker stance tracking over time
- Contradiction detection
- Categorization and relationship analysis

The checkpoint system enables resuming this complex process at any stage.
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Add the project root to the path to enable imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.insert(0, project_root)

from src.repositories.episode_repository import JsonFileRepository
from src.services.opinion_extraction import OpinionExtractionService, CheckpointService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Resumable Opinion Extraction Example')
    
    parser.add_argument(
        '--episodes-db',
        type=str,
        default='data/episodes.json',
        help='Path to episodes database JSON file'
    )
    
    parser.add_argument(
        '--transcripts-dir',
        type=str,
        default='data/transcripts',
        help='Directory containing transcript files'
    )
    
    parser.add_argument(
        '--checkpoint-path',
        type=str,
        default='data/checkpoints/extraction_checkpoint.json',
        help='Path to store checkpoint data'
    )
    
    parser.add_argument(
        '--raw-opinions-path',
        type=str,
        default='data/checkpoints/raw_opinions.json',
        help='Path to store raw opinions data'
    )
    
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Limit the number of episodes to process'
    )
    
    parser.add_argument(
        '--no-resume',
        action='store_true',
        help='Start from scratch instead of resuming'
    )
    
    parser.add_argument(
        '--reset',
        action='store_true',
        help='Reset the checkpoint before starting'
    )
    
    parser.add_argument(
        '--model',
        type=str,
        default='deepseek',
        choices=['deepseek', 'openai'],
        help='LLM model provider to use'
    )
    
    return parser.parse_args()

def main():
    """Run the resumable opinion extraction example."""
    args = parse_arguments()
    
    # Create output directories if they don't exist
    checkpoint_dir = os.path.dirname(args.checkpoint_path)
    os.makedirs(checkpoint_dir, exist_ok=True)
    
    # Initialize the repository
    repository = JsonFileRepository(args.episodes_db)
    
    # Get episodes from repository
    all_episodes = repository.get_all_episodes()
    logger.info(f"Found {len(all_episodes)} episodes in the database")
    
    # Filter episodes that have transcripts
    episodes_with_transcripts = [ep for ep in all_episodes if ep.transcript_filename]
    logger.info(f"Found {len(episodes_with_transcripts)} episodes with transcripts")
    
    # Apply limit if specified
    if args.limit:
        episodes_to_process = episodes_with_transcripts[:args.limit]
        logger.info(f"Limited to {len(episodes_to_process)} episodes")
    else:
        episodes_to_process = episodes_with_transcripts
    
    # Initialize the opinion extraction service with checkpoint support
    extraction_service = OpinionExtractionService(
        use_llm=True,
        llm_provider=args.model,
        checkpoint_path=args.checkpoint_path,
        raw_opinions_path=args.raw_opinions_path
    )
    
    # Reset checkpoint if requested
    if args.reset:
        logger.info("Resetting checkpoint data")
        extraction_service.reset_extraction_process()
    
    # Get checkpoint status before processing
    if not args.no_resume and not args.reset:
        checkpoint_service = CheckpointService(
            checkpoint_path=args.checkpoint_path,
            raw_opinions_path=args.raw_opinions_path
        )
        
        processed_episodes = checkpoint_service.get_processed_episodes()
        last_stage = checkpoint_service.get_episode_stage(checkpoint_service.checkpoint_data.get("last_processed_episode"))
        
        logger.info(f"Resuming from checkpoint with {len(processed_episodes)} processed episodes")
        logger.info(f"Last completed stage: {last_stage}")
        
        # Print extraction stats if available
        stats = checkpoint_service.get_extraction_stats()
        if stats:
            logger.info(f"Extraction stats: {stats}")
    
    # Run the extraction process
    try:
        logger.info("Starting opinion extraction process")
        updated_episodes = extraction_service.extract_opinions(
            episodes=episodes_to_process,
            transcripts_dir=args.transcripts_dir,
            resume_from_checkpoint=not args.no_resume,
            save_checkpoints=True
        )
        
        # Save updated episodes
        for episode in updated_episodes:
            repository.save_episode(episode)
        
        # Print final stats
        final_stats = extraction_service.checkpoint_service.get_extraction_stats()
        logger.info(f"Extraction complete with stats: {final_stats}")
        
        logger.info("Opinion extraction completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        logger.info("You can resume the process later using the same command")
        return 1
        
    except Exception as e:
        logger.error(f"Error during opinion extraction: {e}")
        logger.info("You can resume the process later using the same command")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 