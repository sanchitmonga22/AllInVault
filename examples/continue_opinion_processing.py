#!/usr/bin/env python3
"""
Continue Opinion Processing

This script continues the opinion extraction pipeline from existing raw opinions.
It assumes you already have raw opinions extracted in a JSON file and continues
with the next stages: categorization, relationship analysis, merging, evolution
detection, and speaker tracking.
"""

import os
import sys
import logging
import argparse
import json
from pathlib import Path
from datetime import datetime
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
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"opinion_processing_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Continue Opinion Processing from Raw Opinions')
    
    parser.add_argument(
        '--episodes-db',
        type=str,
        default='data/episodes.json',
        help='Path to episodes database JSON file'
    )
    
    parser.add_argument(
        '--raw-opinions-path',
        type=str,
        required=True,
        help='Path to existing raw opinions JSON file'
    )
    
    parser.add_argument(
        '--checkpoint-path',
        type=str,
        default='data/checkpoints/extraction_checkpoint.json',
        help='Path to store checkpoint data'
    )
    
    parser.add_argument(
        '--transcripts-dir',
        type=str,
        default='data/transcripts',
        help='Directory containing transcript files (needed for some operations)'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/opinions',
        help='Directory to store output files'
    )
    
    parser.add_argument(
        '--start-stage',
        type=str,
        choices=['raw_extraction', 'categorization', 'relationship_analysis', 'opinion_merging', 'evolution_detection', 'speaker_tracking'],
        default='categorization',
        help='Stage to start processing from'
    )
    
    parser.add_argument(
        '--llm-provider',
        type=str,
        default='deepseek',
        choices=['deepseek', 'openai'],
        help='LLM provider to use'
    )
    
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be done without actually processing'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force processing even if stages are already completed'
    )
    
    return parser.parse_args()

def get_stage_int(stage_name):
    """Convert stage name to integer constant."""
    stage_map = {
        'raw_extraction': 0,
        'categorization': 1,
        'relationship_analysis': 2,
        'opinion_merging': 3,
        'evolution_detection': 4,
        'speaker_tracking': 5
    }
    return stage_map.get(stage_name, 0)

def validate_raw_opinions(raw_opinions_path):
    """Validate that the raw opinions file exists and has valid content."""
    if not os.path.exists(raw_opinions_path):
        logger.error(f"Raw opinions file not found: {raw_opinions_path}")
        return False
    
    try:
        with open(raw_opinions_path, 'r') as f:
            data = json.load(f)
            
        # Check that it contains opinions
        if not isinstance(data, list) or len(data) == 0:
            logger.error(f"Raw opinions file does not contain a list of opinions")
            return False
            
        # Validate first opinion has required fields
        required_fields = ['id', 'title', 'description', 'speakers', 'category', 'episode_id']
        sample_opinion = data[0]
        
        for field in required_fields:
            if field not in sample_opinion:
                logger.error(f"Opinion missing required field: {field}")
                return False
                
        logger.info(f"Raw opinions file validated: {len(data)} opinions found")
        return True
        
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to read raw opinions file: {e}")
        return False

def setup_checkpoint(args, force_reset=False):
    """Set up the checkpoint service and prepare for processing."""
    # Create checkpoint directory if needed
    os.makedirs(os.path.dirname(args.checkpoint_path), exist_ok=True)
    
    # Initialize checkpoint service
    checkpoint_service = CheckpointService(
        checkpoint_path=args.checkpoint_path,
        raw_opinions_path=args.raw_opinions_path
    )
    
    # Reset checkpoint if requested or force reset
    if args.force or force_reset:
        logger.info("Forcing reset of checkpoint data")
        checkpoint_service.reset_checkpoint()
        
        # Mark raw extraction as complete since we're starting from raw opinions
        checkpoint_service.mark_episode_stage_complete(episode_id=checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"), stage="raw_extraction")
        
        # Copy raw opinions to checkpoint's expected location if different
        if args.raw_opinions_path != checkpoint_service.raw_opinions_path:
            with open(args.raw_opinions_path, 'r') as src_file:
                raw_opinions = json.load(src_file)
                
            checkpoint_service.save_raw_opinions(raw_opinions)
            logger.info(f"Copied {len(raw_opinions)} raw opinions to checkpoint location")
    
    return checkpoint_service

def main():
    """Run the opinion processing continuation."""
    args = parse_arguments()
    
    # Create output directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Validate raw opinions file
    if not validate_raw_opinions(args.raw_opinions_path):
        return 1
    
    # Initialize repository for episodes
    repository = JsonFileRepository(args.episodes_db)
    
    # Get all episodes
    all_episodes = repository.get_all_episodes()
    logger.info(f"Found {len(all_episodes)} episodes in the database")
    
    # Filter episodes that have transcripts
    episodes_with_transcripts = [ep for ep in all_episodes if ep.transcript_filename]
    logger.info(f"Found {len(episodes_with_transcripts)} episodes with transcripts")
    
    # Initialize checkpoint service
    checkpoint_service = setup_checkpoint(args)
    
    # Get current checkpoint status
    current_stage = checkpoint_service.get_episode_stage(checkpoint_service.checkpoint_data.get("last_processed_episode"))
    target_stage = get_stage_int(args.start_stage)
    current_stage_int = get_stage_int(current_stage) if current_stage else None
    
    logger.info(f"Current checkpoint stage: {current_stage}")
    logger.info(f"Target starting stage: {target_stage}")
    
    # Check if we need to force processing
    if current_stage_int is not None and current_stage_int >= target_stage and not args.force:
        logger.warning(f"Stage {args.start_stage} is already completed. Use --force to process anyway.")
        if args.dry_run or input("Continue anyway? (y/n): ").lower() != 'y':
            return 0
        
        # Reset checkpoint to just before target stage
        checkpoint_service.reset_checkpoint()
        checkpoint_service.mark_episode_stage_complete(episode_id=checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"), stage=args.start_stage)
    
    # If dry run, just show what would be done
    if args.dry_run:
        logger.info("DRY RUN: Would continue processing from raw opinions:")
        with open(args.raw_opinions_path, 'r') as f:
            raw_opinions = json.load(f)
        
        logger.info(f"Would process {len(raw_opinions)} raw opinions")
        logger.info(f"Would start from stage: {args.start_stage}")
        logger.info(f"Would process {len(episodes_with_transcripts)} episodes")
        return 0
    
    # Initialize the opinion extraction service
    extraction_service = OpinionExtractionService(
        use_llm=True,
        llm_provider=args.llm_provider,
        checkpoint_path=args.checkpoint_path,
        raw_opinions_path=args.raw_opinions_path
    )
    
    # Run the extraction process
    try:
        logger.info(f"Starting opinion processing from stage: {args.start_stage}")
        updated_episodes = extraction_service.extract_opinions(
            episodes=episodes_with_transcripts,
            transcripts_dir=args.transcripts_dir,
            resume_from_checkpoint=True,
            save_checkpoints=True,
            start_stage=args.start_stage
        )
        
        # Save updated episodes
        for episode in updated_episodes:
            repository.save_episode(episode)
        
        # Get final stats
        final_stats = extraction_service.checkpoint_service.get_extraction_stats()
        logger.info(f"Processing complete with stats: {final_stats}")
        
        # Save final results to output directory
        extracted_opinions = extraction_service.opinion_repository.get_all_opinions()
        
        output_file = os.path.join(args.output_dir, "processed_opinions.json")
        with open(output_file, 'w') as f:
            # Convert Opinion objects to dictionaries for serialization
            opinions_data = [opinion.to_dict() for opinion in extracted_opinions]
            json.dump(opinions_data, f, indent=2)
        
        logger.info(f"Saved {len(extracted_opinions)} processed opinions to {output_file}")
        
        # Save extraction stats
        stats_file = os.path.join(args.output_dir, "extraction_stats.json")
        with open(stats_file, 'w') as f:
            json.dump(final_stats, f, indent=2)
        
        logger.info(f"Saved extraction stats to {stats_file}")
        
        logger.info("Opinion processing completed successfully")
        return 0
        
    except KeyboardInterrupt:
        logger.info("Process interrupted by user")
        logger.info("You can resume the process later using the same command")
        return 1
        
    except Exception as e:
        logger.error(f"Error during opinion processing: {e}", exc_info=True)
        logger.info("You can resume the process later using the same command")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 