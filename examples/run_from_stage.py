#!/usr/bin/env python3
"""
Run From Current Stage

This script determines the last completed stage in the extraction process
and automatically continues from the next stage.
"""

import os
import sys
import logging
import argparse
import subprocess
from datetime import datetime

# Add the project root to the path to enable imports
script_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.abspath(os.path.join(script_dir, '..'))
sys.path.insert(0, project_root)

from src.services.opinion_extraction.checkpoint_service import CheckpointService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(f"run_from_stage_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")
    ]
)

logger = logging.getLogger(__name__)

def parse_arguments():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description='Run extraction from current stage')
    
    parser.add_argument(
        '--episodes-db',
        type=str,
        default='data/json/episodes.json',
        help='Path to episodes database JSON file'
    )
    
    parser.add_argument(
        '--raw-opinions-path',
        type=str,
        default='data/intermediate/raw_opinions.json',
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
        help='Directory containing transcript files'
    )
    
    parser.add_argument(
        '--output-dir',
        type=str,
        default='data/opinions',
        help='Directory to store output files'
    )
    
    parser.add_argument(
        '--llm-provider',
        type=str,
        default='deepseek',
        choices=['deepseek', 'openai'],
        help='LLM provider to use'
    )
    
    parser.add_argument(
        '--force',
        action='store_true',
        help='Force processing even if stages are already completed'
    )
    
    parser.add_argument(
        '--show-stats',
        action='store_true',
        help='Show statistics after determining stage'
    )
    
    return parser.parse_args()

def determine_next_stage(checkpoint_path):
    """Determine the next stage to run based on checkpoint data."""
    checkpoint_service = CheckpointService(checkpoint_path=checkpoint_path)
    
    # Get the current stage
    episode_id = checkpoint_service.checkpoint_data.get("last_processed_episode", "initial")
    current_stage = checkpoint_service.get_episode_stage(episode_id)
    
    # Stage order
    stages = [
        "raw_extraction",
        "categorization",
        "relationship_analysis",
        "opinion_merging",
        "evolution_detection",
        "speaker_tracking",
        "complete"
    ]
    
    # Find the next stage
    if not current_stage or current_stage not in stages:
        return "raw_extraction"
    
    if current_stage == "complete":
        return "complete"
    
    current_index = stages.index(current_stage)
    if current_index < len(stages) - 1:
        return stages[current_index + 1]
    else:
        return "complete"

def main():
    """Run the extraction process from the current stage."""
    args = parse_arguments()
    
    # Determine the next stage to run
    next_stage = determine_next_stage(args.checkpoint_path)
    
    logger.info(f"Determined next stage: {next_stage}")
    
    if next_stage == "complete":
        logger.info("All stages are already complete. Use --force to reprocess.")
        
        if args.show_stats:
            stats_cmd = [
                sys.executable,
                os.path.join(script_dir, "view_extraction_stats.py"),
                "--checkpoint-path", args.checkpoint_path
            ]
            subprocess.run(stats_cmd)
        
        if not args.force:
            return 0
        else:
            logger.info("Forcing reprocessing from evolution_detection stage")
            next_stage = "evolution_detection"
    
    # Show stats if requested
    if args.show_stats:
        stats_cmd = [
            sys.executable,
            os.path.join(script_dir, "view_extraction_stats.py"),
            "--checkpoint-path", args.checkpoint_path
        ]
        subprocess.run(stats_cmd)
    
    # Build and run the command to continue processing
    cmd = [
        sys.executable,
        os.path.join(script_dir, "continue_opinion_processing.py"),
        "--episodes-db", args.episodes_db,
        "--raw-opinions-path", args.raw_opinions_path,
        "--checkpoint-path", args.checkpoint_path,
        "--transcripts-dir", args.transcripts_dir,
        "--output-dir", args.output_dir,
        "--start-stage", next_stage,
        "--llm-provider", args.llm_provider
    ]
    
    if args.force:
        cmd.append("--force")
    
    logger.info(f"Running command: {' '.join(cmd)}")
    
    try:
        subprocess.run(cmd, check=True)
        logger.info("Processing completed successfully")
        
        # Show final stats
        logger.info("Final statistics:")
        stats_cmd = [
            sys.executable,
            os.path.join(script_dir, "view_extraction_stats.py"),
            "--checkpoint-path", args.checkpoint_path
        ]
        subprocess.run(stats_cmd)
        
        return 0
        
    except subprocess.CalledProcessError as e:
        logger.error(f"Processing failed with exit code {e.returncode}")
        return e.returncode
    
    except KeyboardInterrupt:
        logger.info("Processing interrupted by user")
        return 1

if __name__ == "__main__":
    sys.exit(main()) 