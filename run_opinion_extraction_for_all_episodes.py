#!/usr/bin/env python3
"""
Run opinion extraction for all episodes in chronological order.

This script:
1. Loads all episodes from the repository
2. Sorts them by published date
3. Processes all episodes (or a specified count)
4. Processes them using the multi-stage opinion extraction architecture
5. Tracks opinion evolution across episodes

Features:
- Incremental saving: Saves progress after each episode to minimize data loss
- Resumable: Can pick up where it left off if interrupted
- Checkpointing: Maintains a progress file to track completed episodes
- Flexible: Allows processing specific stages or episodes

Usage:
  python run_opinion_extraction_for_all_episodes.py [--count N] [--delay N]
  
Options:
  --count N                  Number of episodes to process (default: all)
  --delay N                  Delay between episodes in seconds (default: 10)
  --max-opinions N           Maximum opinions per episode (default: 15)
  --relation-batch-size N    Batch size for relationship analysis (default: 20)
  --similarity-threshold N   Threshold for opinion similarity (default: 0.7)
  --llm-model                LLM model to use (default: gpt-4o)
  --log-level                Logging level (default: INFO)
  --log-file                 Path to log file (optional)
  --stage                    Specific stage to run (extraction, categorization, relationships, merging, all)
  --skip-extraction          Skip the raw opinion extraction stage
  --skip-categorization      Skip the opinion categorization stage
  --skip-relationships       Skip the relationship analysis stage 
  --skip-merging             Skip the opinion merging stage
  --skip-shorts              Skip episodes labeled as SHORT
  --checkpoint-file          Path to the checkpoint file to track progress (default: data/intermediate/checkpoint.json)
"""

import logging
import sys
import time
import argparse
import json
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

from src.repositories.episode_repository import JsonFileRepository
from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository
from src.models.podcast_episode import PodcastEpisode
from src.utils.config import load_config
from src.services.opinion_extraction.extraction_service import OpinionExtractionService
from src.services.opinion_extraction.raw_extraction_service import RawOpinionExtractionService
from src.services.opinion_extraction.categorization_service import OpinionCategorizationService
from src.services.opinion_extraction.relationship_service import OpinionRelationshipService
from src.services.opinion_extraction.merger_service import OpinionMergerService
from src.services.llm_service import LLMService

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Run opinion extraction for all podcast episodes")
    parser.add_argument("--count", type=int, default=None, 
                        help="Number of episodes to process (default: all episodes)")
    parser.add_argument("--delay", type=int, default=10, 
                        help="Delay between episodes in seconds")
    parser.add_argument("--max-opinions", type=int, default=15,
                        help="Maximum opinions per episode")
    parser.add_argument("--relation-batch-size", type=int, default=20,
                        help="Batch size for relationship analysis")  
    parser.add_argument("--similarity-threshold", type=float, default=0.7,
                        help="Threshold for opinion similarity")
    parser.add_argument("--llm-model", type=str, default="deepseek-chat",
                        help="LLM model to use")
    parser.add_argument("--skip-processed", action="store_true", default=True,
                        help="Skip episodes that already have opinions")
    parser.add_argument("--skip-shorts", action="store_true", default=False,
                        help="Skip episodes labeled as SHORT")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        default="INFO", help="Logging level")
    parser.add_argument("--log-file", type=str, default=None,
                        help="Path to log file (if not specified, logs will only go to console)")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Dry run - don't actually process episodes, just show what would be done")
    
    # Add stage-specific arguments
    parser.add_argument("--stage", type=str, choices=["extraction", "categorization", "relationships", "merging", "all"],
                        default="all", help="Specific stage to run")
    parser.add_argument("--skip-extraction", action="store_true", default=False,
                        help="Skip the raw opinion extraction stage")
    parser.add_argument("--skip-categorization", action="store_true", default=False,
                        help="Skip the opinion categorization stage")
    parser.add_argument("--skip-relationships", action="store_true", default=False,
                        help="Skip the relationship analysis stage")
    parser.add_argument("--skip-merging", action="store_true", default=False,
                        help="Skip the opinion merging stage")
    parser.add_argument("--raw-opinions-file", type=str, default="data/intermediate/raw_opinions.json",
                        help="Path to save/load raw opinions")
    parser.add_argument("--categorized-opinions-file", type=str, default="data/intermediate/categorized_opinions.json",
                        help="Path to save/load categorized opinions")
    parser.add_argument("--relationships-file", type=str, default="data/intermediate/relationships.json",
                        help="Path to save/load relationship data")
    parser.add_argument("--checkpoint-file", type=str, default="data/intermediate/checkpoint.json",
                        help="Path to the checkpoint file to track progress")
    parser.add_argument("--start-from", type=str, default=None,
                        help="Start processing from this episode ID (skip earlier episodes)")
    parser.add_argument("--force-continue", action="store_true", default=False,
                        help="Continue processing even if an error occurs with an episode")
    
    return parser.parse_args()

# Set up enhanced logging
def setup_logging(log_level=logging.INFO, log_file=None):
    """Set up enhanced logging with console and file output."""
    # Create logs directory if it doesn't exist
    if log_file:
        log_dir = Path(log_file).parent
        log_dir.mkdir(parents=True, exist_ok=True)
    
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    
    # Remove existing handlers
    for handler in root_logger.handlers[:]:  
        root_logger.removeHandler(handler)
    
    # Create formatters
    detailed_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s'
    )
    console_formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (if log_file is provided)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(detailed_formatter)
        root_logger.addHandler(file_handler)
    
    # Create and return the application logger
    logger = logging.getLogger("OpinionExtraction")
    logger.info(f"Logging initialized at level {logging.getLevelName(log_level)}")
    if log_file:
        logger.info(f"Log file: {log_file}")
    
    return logger

# Function to update episode's transcript filename based on format
def update_transcript_filenames(episodes: List[PodcastEpisode]) -> List[PodcastEpisode]:
    """Update the transcript filename for each episode to use TXT format."""
    updated_episodes = []
    
    for episode in episodes:
        # Get episode video ID
        video_id = episode.video_id
        
        # Check if TXT transcript file exists
        txt_path = Path("data/transcripts") / f"{video_id}.txt"
        
        # Update transcript filename based on availability
        if txt_path.exists():
            episode.transcript_filename = f"{video_id}.txt"
            logging.debug(f"Found TXT transcript for episode {video_id}")
        else:
            # No transcript available
            episode.transcript_filename = None
            logging.warning(f"No TXT transcript found for episode {video_id}")
        
        updated_episodes.append(episode)
    
    return updated_episodes

class CheckpointManager:
    """Manages checkpoints for resumable processing."""
    
    def __init__(self, checkpoint_file: str):
        """Initialize the checkpoint manager.
        
        Args:
            checkpoint_file: Path to the checkpoint file
        """
        self.checkpoint_file = checkpoint_file
        self.data = self._load_checkpoint()
    
    def _load_checkpoint(self) -> Dict:
        """Load the checkpoint data from the file."""
        if not os.path.exists(self.checkpoint_file):
            return {
                "processed_episodes": [],
                "extraction_completed": False,
                "categorization_completed": False,
                "relationships_completed": False,
                "merging_completed": False,
                "last_processed_episode": None,
                "last_updated": None,
                "extraction_count": 0
            }
        
        with open(self.checkpoint_file, 'r') as f:
            return json.load(f)
    
    def save_checkpoint(self):
        """Save the current checkpoint data to the file."""
        # Update the last updated timestamp
        self.data["last_updated"] = datetime.now().isoformat()
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(self.checkpoint_file), exist_ok=True)
        
        # Save the checkpoint data
        processed_data = convert_datetime_to_iso(self.data)
        with open(self.checkpoint_file, 'w') as f:
            json.dump(processed_data, f, indent=2)
    
    def mark_episode_processed(self, episode_id: str):
        """Mark an episode as processed."""
        if episode_id not in self.data["processed_episodes"]:
            self.data["processed_episodes"].append(episode_id)
            self.data["last_processed_episode"] = episode_id
            self.data["extraction_count"] += 1
            self.save_checkpoint()
    
    def mark_stage_completed(self, stage: str):
        """Mark a processing stage as completed."""
        if stage == "extraction":
            self.data["extraction_completed"] = True
        elif stage == "categorization":
            self.data["categorization_completed"] = True
        elif stage == "relationships":
            self.data["relationships_completed"] = True
        elif stage == "merging":
            self.data["merging_completed"] = True
        
        self.save_checkpoint()
    
    def is_episode_processed(self, episode_id: str) -> bool:
        """Check if an episode has been processed."""
        return episode_id in self.data["processed_episodes"]
    
    def is_stage_completed(self, stage: str) -> bool:
        """Check if a processing stage has been completed."""
        if stage == "extraction":
            return self.data["extraction_completed"]
        elif stage == "categorization":
            return self.data["categorization_completed"]
        elif stage == "relationships":
            return self.data["relationships_completed"]
        elif stage == "merging":
            return self.data["merging_completed"]
        return False
    
    def get_processed_count(self) -> int:
        """Get the number of processed episodes."""
        return len(self.data["processed_episodes"])
    
    def get_last_processed_episode(self) -> Optional[str]:
        """Get the ID of the last processed episode."""
        return self.data["last_processed_episode"]
    
    def reset_stage(self, stage: str):
        """Reset a specific stage's completion status."""
        if stage == "extraction":
            self.data["extraction_completed"] = False
        elif stage == "categorization":
            self.data["categorization_completed"] = False
        elif stage == "relationships":
            self.data["relationships_completed"] = False
        elif stage == "merging":
            self.data["merging_completed"] = False
        elif stage == "all":
            self.data["extraction_completed"] = False
            self.data["categorization_completed"] = False
            self.data["relationships_completed"] = False
            self.data["merging_completed"] = False
        
        self.save_checkpoint()
    
    def reset_all(self):
        """Reset all checkpoint data."""
        self.data = {
            "processed_episodes": [],
            "extraction_completed": False,
            "categorization_completed": False,
            "relationships_completed": False,
            "merging_completed": False,
            "last_processed_episode": None,
            "last_updated": datetime.now().isoformat(),
            "extraction_count": 0
        }
        self.save_checkpoint()

def get_episodes_chronologically(repository: JsonFileRepository, count: Optional[int] = None, 
                                start_from_id: str = None, skip_shorts: bool = False,
                                checkpoint_manager: Optional[CheckpointManager] = None) -> List[PodcastEpisode]:
    """
    Get episodes in chronological order.
    
    Args:
        repository: Episode repository
        count: Number of episodes to retrieve (None for all)
        start_from_id: Episode ID to start from (skipping earlier episodes)
        skip_shorts: Whether to skip episodes labeled as SHORT
        checkpoint_manager: Optional checkpoint manager to skip already processed episodes
        
    Returns:
        List of episodes sorted by published date (oldest first)
    """
    # Get all episodes
    all_episodes = repository.get_all_episodes()
    
    # Filter out SHORT episodes if requested
    if skip_shorts:
        filtered_episodes = []
        for episode in all_episodes:
            # Check if episode has metadata.type and if it's "SHORT"
            if "metadata" in episode.__dict__ and episode.metadata and \
               "type" in episode.metadata and episode.metadata["type"] == "SHORT":
                continue
            filtered_episodes.append(episode)
        all_episodes = filtered_episodes
    
    # Sort episodes by published date (oldest first)
    sorted_episodes = sorted(all_episodes, key=lambda ep: ep.published_at if ep.published_at else datetime.min)
    
    # If start_from_id is provided, skip episodes until we find it
    if start_from_id:
        for i, episode in enumerate(sorted_episodes):
            if episode.video_id == start_from_id:
                sorted_episodes = sorted_episodes[i:]
                break
    
    # If checkpoint manager is provided, filter out already processed episodes
    if checkpoint_manager:
        remaining_episodes = []
        for episode in sorted_episodes:
            if not checkpoint_manager.is_episode_processed(episode.video_id):
                remaining_episodes.append(episode)
        logging.info(f"Filtered out {len(sorted_episodes) - len(remaining_episodes)} already processed episodes based on checkpoint")
        sorted_episodes = remaining_episodes
    
    # Return all or the first n episodes
    if count is not None:
        return sorted_episodes[:count]
    return sorted_episodes

# Function to display statistics about extracted opinions
def show_opinion_statistics(opinion_repo: OpinionRepository, category_repo: CategoryRepository, logger=None) -> None:
    """Display statistics about extracted opinions."""
    if logger is None:
        logger = logging.getLogger("OpinionExtraction")
    
    # Get all opinions and categories
    all_opinions = opinion_repo.get_all_opinions()
    all_categories = category_repo.get_all_categories()
    
    # Count opinions by category
    opinions_by_category = {}
    for category in all_categories:
        opinions_by_category[category.name] = 0
    
    for opinion in all_opinions:
        # Find category name
        category_id = opinion.category_id
        category_name = "Uncategorized"
        
        for category in all_categories:
            if category.id == category_id:
                category_name = category.name
                break
        
        # Increment count
        if category_name in opinions_by_category:
            opinions_by_category[category_name] += 1
        else:
            opinions_by_category[category_name] = 1
    
    # Count opinions with relationships, contradictions, etc.
    opinions_with_related = 0
    opinions_with_contradiction = 0
    total_appearances = 0
    opinions_with_multiple_appearances = 0
    
    for opinion in all_opinions:
        if opinion.related_opinions:
            opinions_with_related += 1
        
        if opinion.is_contradiction:
            opinions_with_contradiction += 1
        
        if len(opinion.appearances) > 1:
            opinions_with_multiple_appearances += 1
        
        total_appearances += len(opinion.appearances)
    
    # Display statistics
    logger.info(f"Total opinions: {len(all_opinions)}")
    logger.info(f"Total opinion appearances: {total_appearances}")
    logger.info(f"Opinions with related opinions: {opinions_with_related}")
    logger.info(f"Opinions with contradictions: {opinions_with_contradiction}")
    logger.info(f"Opinions appearing in multiple episodes: {opinions_with_multiple_appearances}")
    
    # Display opinions by category
    logger.info("Opinions by category:")
    for category, count in sorted(opinions_by_category.items(), key=lambda x: x[1], reverse=True):
        if count > 0:
            logger.info(f"  {category}: {count}")

def ensure_dir_exists(file_path):
    """Ensure the directory for a file exists."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

# Custom JSON encoder to handle datetime objects
class DateTimeEncoder(json.JSONEncoder):
    """Custom JSON encoder that can handle datetime objects."""
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)

def convert_datetime_to_iso(obj):
    """
    Recursively convert all datetime objects in a dictionary/list to ISO format strings.
    
    Args:
        obj: Dictionary, list, or other object to process
        
    Returns:
        Object with all datetime objects converted to strings
    """
    if isinstance(obj, dict):
        return {key: convert_datetime_to_iso(value) for key, value in obj.items()}
    elif isinstance(obj, list):
        return [convert_datetime_to_iso(item) for item in obj]
    elif isinstance(obj, datetime):
        return obj.isoformat()
    else:
        return obj

def save_intermediate_data(data, file_path):
    """Save intermediate data to a JSON file."""
    ensure_dir_exists(file_path)
    # Convert any datetime objects to ISO format strings
    processed_data = convert_datetime_to_iso(data)
    with open(file_path, 'w') as f:
        json.dump(processed_data, f, indent=2)

def load_intermediate_data(file_path, default=None):
    """Load intermediate data from a JSON file."""
    if not os.path.exists(file_path):
        return default or {}
    
    with open(file_path, 'r') as f:
        return json.load(f)

def has_extracted_opinions(episode: PodcastEpisode) -> bool:
    """Check if an episode already has extracted opinions."""
    return "opinions" in episode.metadata and episode.metadata["opinions"]

def process_batch_of_raw_opinions(raw_opinions, categorization_service, raw_opinions_file, logger):
    """Process a batch of raw opinions and save to file."""
    # Append to existing raw opinions file if it exists
    existing_raw_opinions = []
    if os.path.exists(raw_opinions_file):
        try:
            with open(raw_opinions_file, 'r') as f:
                existing_raw_opinions = json.load(f)
        except json.JSONDecodeError:
            logger.warning(f"Could not decode existing raw opinions file: {raw_opinions_file}. Starting fresh.")
    
    # Combine existing and new raw opinions
    combined_raw_opinions = existing_raw_opinions + raw_opinions
    
    # Save to file
    save_intermediate_data(combined_raw_opinions, raw_opinions_file)
    logger.info(f"Saved combined {len(combined_raw_opinions)} raw opinions to {raw_opinions_file}")
    
    return combined_raw_opinions

def main():
    """Run opinion extraction for all episodes chronologically."""
    start_time = time.time()
    try:
        # Parse command-line arguments
        args = parse_args()
        
        # Set up logging with specified level and file
        log_level = getattr(logging, args.log_level)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_file = args.log_file or f"logs/opinion_extraction_{timestamp}.log"
        logger = setup_logging(log_level=log_level, log_file=log_file)
        
        # Log script start and arguments
        logger.info("Starting opinion extraction script for all episodes")
        logger.info(f"Command-line arguments: {vars(args)}")
        
        # Initialize checkpoint manager
        checkpoint_manager = CheckpointManager(args.checkpoint_file)
        logger.info(f"Using checkpoint file: {args.checkpoint_file}")
        
        if checkpoint_manager.get_processed_count() > 0:
            logger.info(f"Checkpoint found with {checkpoint_manager.get_processed_count()} processed episodes")
            if args.start_from:
                logger.info(f"--start-from flag will override checkpoint. Starting from episode ID: {args.start_from}")
                # Reset checkpoint for extraction stage when overriding
                checkpoint_manager.reset_stage("extraction")
            else:
                last_episode = checkpoint_manager.get_last_processed_episode()
                if last_episode:
                    logger.info(f"Will resume from after episode ID: {last_episode}")
        
        # Load config and initialize repositories
        logger.debug("Loading configuration and initializing repositories")
        config = load_config()
        
        # Initialize repositories
        episode_repo = JsonFileRepository(str(config.episodes_db_path))
        opinions_file_path = "data/json/opinions.json"
        categories_file_path = "data/json/categories.json"
        opinion_repo = OpinionRepository(opinions_file_path)
        category_repo = CategoryRepository(categories_file_path)
        
        # Initialize LLM service
        llm_service = LLMService(model=args.llm_model) if not args.dry_run else None
        
        # Determine which stages to run
        run_extraction = args.stage in ["extraction", "all"] and not args.skip_extraction
        run_categorization = args.stage in ["categorization", "all"] and not args.skip_categorization
        run_relationships = args.stage in ["relationships", "all"] and not args.skip_relationships
        run_merging = args.stage in ["merging", "all"] and not args.skip_merging
        
        # Check if stages were already completed according to checkpoint
        if checkpoint_manager.is_stage_completed("extraction") and run_extraction:
            logger.info("Extraction stage already completed according to checkpoint")
            if not args.start_from:  # Only skip if not explicitly starting from a specific episode
                run_extraction = False
        
        if checkpoint_manager.is_stage_completed("categorization") and run_categorization:
            logger.info("Categorization stage already completed according to checkpoint")
            if not args.force_continue:
                run_categorization = False
        
        if checkpoint_manager.is_stage_completed("relationships") and run_relationships:
            logger.info("Relationships stage already completed according to checkpoint")
            if not args.force_continue:
                run_relationships = False
        
        if checkpoint_manager.is_stage_completed("merging") and run_merging:
            logger.info("Merging stage already completed according to checkpoint")
            if not args.force_continue:
                run_merging = False
        
        # Create the necessary service instances based on stages
        raw_extraction_service = None
        categorization_service = None
        relationship_service = None
        merger_service = None
        
        if run_extraction:
            raw_extraction_service = RawOpinionExtractionService(
                llm_service=llm_service,
                max_opinions_per_episode=args.max_opinions
            )
        
        if run_categorization:
            categorization_service = OpinionCategorizationService(
                llm_service=llm_service,
                category_repository=category_repo
            )
        
        if run_relationships:
            relationship_service = OpinionRelationshipService(
                llm_service=llm_service,
                relation_batch_size=args.relation_batch_size,
                similarity_threshold=args.similarity_threshold
            )
        
        if run_merging:
            merger_service = OpinionMergerService(
                opinion_repository=opinion_repo,
                category_repository=category_repo
            )
        
        # Stage 1: Raw Opinion Extraction
        all_raw_opinions = []
        if run_extraction:
            # Get all episodes chronologically, filtering based on checkpoint
            episodes_description = "all episodes" if args.count is None else f"the first {args.count} episodes"
            logger.info(f"Getting {episodes_description} chronologically")
            
            episodes = get_episodes_chronologically(
                episode_repo, 
                args.count, 
                args.start_from, 
                args.skip_shorts,
                checkpoint_manager if not args.start_from else None  # Only use checkpoint if not explicitly starting from a specific episode
            )
            logger.info(f"Found {len(episodes)} episodes to process")
            
            # Update transcript filenames to use TXT format
            logger.info("Updating transcript filenames to use TXT format")
            episodes = update_transcript_filenames(episodes)
            
            # Count episodes with valid transcripts
            episodes_with_transcripts = [ep for ep in episodes if ep.transcript_filename]
            logger.info(f"Episodes with transcripts: {len(episodes_with_transcripts)}/{len(episodes)}")
            
            if args.dry_run:
                logger.info("[DRY RUN] Would extract raw opinions from episodes")
                for episode in episodes_with_transcripts:
                    logger.info(f"[DRY RUN] Would process episode: {episode.title}")
            else:
                # Initialize or load raw opinions from file
                batch_size = 5  # Process and save in batches to minimize potential data loss
                batch_raw_opinions = []
                
                # Process each episode to extract raw opinions
                for i, episode in enumerate(episodes_with_transcripts):
                    # Skip episodes without transcripts
                    if not episode.transcript_filename:
                        logger.warning(f"Episode {episode.title} has no transcript")
                        continue
                    
                    # Skip already processed episodes if requested
                    if args.skip_processed and has_extracted_opinions(episode):
                        logger.info(f"Skipping episode {episode.title} - already has opinions")
                        checkpoint_manager.mark_episode_processed(episode.video_id)
                        continue
                    
                    # Ensure we're using a TXT transcript
                    if not episode.transcript_filename.lower().endswith('.txt'):
                        logger.warning(f"Episode {episode.title} has non-TXT transcript: {episode.transcript_filename}")
                        continue
                        
                    transcript_path = os.path.join(str(config.transcripts_dir), episode.transcript_filename)
                    if not os.path.exists(transcript_path):
                        logger.warning(f"Transcript file {transcript_path} not found")
                        continue
                    
                    try:
                        logger.info(f"Extracting raw opinions from episode ({i+1}/{len(episodes_with_transcripts)}): {episode.title}")
                        
                        # Extract raw opinions from this episode
                        raw_opinions = raw_extraction_service.extract_raw_opinions(
                            episode=episode,
                            transcript_path=transcript_path
                        )
                        
                        if raw_opinions:
                            logger.info(f"Extracted {len(raw_opinions)} raw opinions from {episode.title}")
                            
                            # Convert any datetime objects to ISO format strings for JSON serialization
                            raw_opinions = convert_datetime_to_iso(raw_opinions)
                            
                            batch_raw_opinions.extend(raw_opinions)
                            
                            # Update the episode metadata
                            if "opinions" not in episode.metadata:
                                episode.metadata["opinions"] = {}
                            
                            # Add opinion IDs to episode metadata
                            for opinion in raw_opinions:
                                episode.metadata["opinions"][opinion["id"]] = {
                                    "title": opinion["title"],
                                    "category": opinion["category"]
                                }
                            
                            # Save the updated episode metadata
                            episode_repo.save_episode(episode)
                            
                            # Mark episode as processed in checkpoint
                            checkpoint_manager.mark_episode_processed(episode.video_id)
                        else:
                            logger.warning(f"No opinions extracted from episode: {episode.title}")
                            # Still mark as processed to avoid retrying
                            checkpoint_manager.mark_episode_processed(episode.video_id)
                        
                        # Process and save batch if we've reached the batch size
                        if len(batch_raw_opinions) >= batch_size:
                            logger.info(f"Processing batch of {len(batch_raw_opinions)} raw opinions")
                            all_raw_opinions = process_batch_of_raw_opinions(
                                batch_raw_opinions, 
                                categorization_service, 
                                args.raw_opinions_file,
                                logger
                            )
                            batch_raw_opinions = []
                    except Exception as e:
                        logger.error(f"Error processing episode {episode.title}: {e}", exc_info=True)
                        if not args.force_continue:
                            raise
                        else:
                            logger.warning("Continuing to next episode due to --force-continue flag")
                    
                    # Add delay between episodes if specified
                    if i < len(episodes_with_transcripts) - 1 and args.delay > 0:
                        logger.info(f"Waiting {args.delay} seconds before next episode...")
                        time.sleep(args.delay)
                
                # Process any remaining batch
                if batch_raw_opinions:
                    logger.info(f"Processing final batch of {len(batch_raw_opinions)} raw opinions")
                    all_raw_opinions = process_batch_of_raw_opinions(
                        batch_raw_opinions, 
                        categorization_service, 
                        args.raw_opinions_file,
                        logger
                    )
                else:
                    # Load all raw opinions if needed
                    with open(args.raw_opinions_file, 'r') as f:
                        all_raw_opinions = json.load(f)
                
                # Mark extraction stage as completed
                checkpoint_manager.mark_stage_completed("extraction")
                logger.info("Extraction stage completed")
        else:
            # Load previously extracted raw opinions
            logger.info(f"Loading raw opinions from {args.raw_opinions_file}")
            all_raw_opinions = load_intermediate_data(args.raw_opinions_file, [])
            logger.info(f"Loaded {len(all_raw_opinions)} raw opinions")
        
        # Stage 2: Opinion Categorization
        categorized_opinions = {}
        if run_categorization:
            if not all_raw_opinions:
                logger.warning("No raw opinions to categorize")
            else:
                logger.info(f"Categorizing {len(all_raw_opinions)} raw opinions")
                try:
                    categorized_opinions = categorization_service.categorize_opinions(all_raw_opinions)
                    
                    # Ensure all categories exist in the repository
                    categorization_service.ensure_categories_exist(list(categorized_opinions.keys()))
                    
                    # Save the categorized opinions to a file for future use
                    save_intermediate_data(categorized_opinions, args.categorized_opinions_file)
                    logger.info(f"Saved categorized opinions to {args.categorized_opinions_file}")
                    
                    # Mark categorization stage as completed
                    checkpoint_manager.mark_stage_completed("categorization")
                    logger.info("Categorization stage completed")
                except Exception as e:
                    logger.error(f"Error during categorization: {e}", exc_info=True)
                    if not args.force_continue:
                        raise
        else:
            # Load previously categorized opinions
            logger.info(f"Loading categorized opinions from {args.categorized_opinions_file}")
            categorized_opinions = load_intermediate_data(args.categorized_opinions_file, {})
            logger.info(f"Loaded categorized opinions for {len(categorized_opinions)} categories")
        
        # Stage 3: Relationship Analysis
        relationship_data = []
        if run_relationships:
            if not categorized_opinions:
                logger.warning("No categorized opinions for relationship analysis")
            else:
                logger.info("Analyzing relationships between opinions")
                try:
                    relationship_data = relationship_service.analyze_relationships(categorized_opinions)
                    
                    # Save the relationship data to a file for future use
                    save_intermediate_data(relationship_data, args.relationships_file)
                    logger.info(f"Saved {len(relationship_data)} relationships to {args.relationships_file}")
                    
                    # Mark relationships stage as completed
                    checkpoint_manager.mark_stage_completed("relationships")
                    logger.info("Relationship analysis stage completed")
                except Exception as e:
                    logger.error(f"Error during relationship analysis: {e}", exc_info=True)
                    if not args.force_continue:
                        raise
        else:
            # Load previously analyzed relationships
            logger.info(f"Loading relationship data from {args.relationships_file}")
            relationship_data = load_intermediate_data(args.relationships_file, [])
            logger.info(f"Loaded {len(relationship_data)} relationships")
        
        # Stage 4: Opinion Merging and Saving
        if run_merging:
            if not all_raw_opinions:
                logger.warning("Missing raw opinions for merging")
            else:
                logger.info("Processing relationships and merging opinions")
                try:
                    final_opinions_data = merger_service.process_relationships(
                        raw_opinions=all_raw_opinions,
                        relationship_data=relationship_data
                    )
                    
                    # Create Opinion objects
                    logger.info("Creating final Opinion objects")
                    final_opinions = merger_service.create_opinion_objects(final_opinions_data)
                    
                    # Save opinions to repository
                    if final_opinions:
                        logger.info(f"Saving {len(final_opinions)} opinions to repository")
                        merger_service.save_opinions(final_opinions)
                        
                        # Show opinion statistics
                        logger.info("Opinion extraction and merging completed")
                        show_opinion_statistics(opinion_repo, category_repo, logger)
                    
                    # Mark merging stage as completed
                    checkpoint_manager.mark_stage_completed("merging")
                    logger.info("Merging stage completed")
                except Exception as e:
                    logger.error(f"Error during merging: {e}", exc_info=True)
                    if not args.force_continue:
                        raise
        
        # Calculate and log overall statistics
        end_time = time.time()
        total_duration = end_time - start_time
        hours, remainder = divmod(total_duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        logger.info(f"Total runtime: {int(hours)}h {int(minutes)}m {seconds:.2f}s")
        
        return 0
    
    except Exception as e:
        logging.error(f"Error in opinion extraction: {e}", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 