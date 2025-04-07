#!/usr/bin/env python3
"""
Run opinion extraction for the first 10 episodes in chronological order.

This script:
1. Loads all episodes from the repository
2. Sorts them by published date
3. Selects the first 10 episodes
4. Processes them using the new multi-stage opinion extraction architecture
5. Tracks opinion evolution across episodes

Usage:
  python run_opinion_extraction_for_first_10.py [--count N] [--max-transcript-tokens N] [--delay N]
  
Options:
  --count N                  Number of episodes to process (default: 10)
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
"""

import logging
import sys
import time
import argparse
import json
import os
from typing import List, Dict, Any
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
    parser = argparse.ArgumentParser(description="Run opinion extraction for podcast episodes")
    parser.add_argument("--count", type=int, default=10, help="Number of episodes to process")
    parser.add_argument("--delay", type=int, default=10, 
                        help="Delay between episodes in seconds")
    parser.add_argument("--max-opinions", type=int, default=15,
                        help="Maximum opinions per episode")
    parser.add_argument("--relation-batch-size", type=int, default=20,
                        help="Batch size for relationship analysis")  
    parser.add_argument("--similarity-threshold", type=float, default=0.7,
                        help="Threshold for opinion similarity")
    parser.add_argument("--llm-model", type=str, default="gpt-4o",
                        help="LLM model to use")
    parser.add_argument("--skip-processed", action="store_true", default=True,
                        help="Skip episodes that already have opinions")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        default="INFO", help="Logging level")
    parser.add_argument("--log-file", type=str, default=None,
                        help="Path to log file (if not specified, logs will only go to console)")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Dry run - don't actually process episodes, just show what would be done")
    
    # Add new stage-specific arguments
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
    
    return parser.parse_args()

# Set up enhanced logging
def setup_logging(log_level=logging.INFO, log_file=None):
    """Set up enhanced logging with console and file output.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Path to log file (default: None)
        
    Returns:
        Configured logger
    """
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
    """
    Update the transcript filename for each episode to use TXT format.
    
    Args:
        episodes: List of podcast episodes
        
    Returns:
        Updated list of episodes with correct transcript filenames
    """
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

def get_first_n_episodes_chronologically(repository: JsonFileRepository, n: int = 10, start_from_id: str = None) -> List[PodcastEpisode]:
    """
    Get the first n episodes in chronological order.
    
    Args:
        repository: Episode repository
        n: Number of episodes to retrieve
        start_from_id: Episode ID to start from (skipping earlier episodes)
        
    Returns:
        List of episodes sorted by published date (oldest first)
    """
    # Get all episodes
    all_episodes = repository.get_all_episodes()
    
    # Sort episodes by published date (oldest first)
    sorted_episodes = sorted(all_episodes, key=lambda ep: ep.published_at if ep.published_at else datetime.min)
    
    # If start_from_id is provided, skip episodes until we find it
    if start_from_id:
        for i, episode in enumerate(sorted_episodes):
            if episode.video_id == start_from_id:
                sorted_episodes = sorted_episodes[i:]
                break
    
    # Return the first n episodes
    return sorted_episodes[:n]

# Function to display statistics about extracted opinions
def show_opinion_statistics(opinion_repo: OpinionRepository, category_repo: CategoryRepository, logger=None) -> None:
    """
    Display statistics about extracted opinions.
    
    Args:
        opinion_repo: Opinion repository
        category_repo: Category repository
        logger: Logger instance
    """
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

def migrate_opinions_to_categories(opinion_repo: OpinionRepository, category_repo: CategoryRepository, logger=None) -> None:
    """
    Ensure all opinions have valid category IDs.
    
    Args:
        opinion_repo: Opinion repository
        category_repo: Category repository
        logger: Logger instance
    """
    if logger is None:
        logger = logging.getLogger("OpinionExtraction")
    
    # Get all opinions and categories
    all_opinions = opinion_repo.get_all_opinions()
    
    # Count migrations
    migrated_count = 0
    
    # Check each opinion
    for opinion in all_opinions:
        # If category_id is a string name instead of ID, find or create the category
        if opinion.category_id and not opinion.category_id.startswith("cat_"):
            category_name = opinion.category_id
            category = category_repo.find_or_create_category(category_name)
            opinion.category_id = category.id
            migrated_count += 1
    
    # Save opinions if any were migrated
    if migrated_count > 0:
        logger.info(f"Migrated {migrated_count} opinions to use category IDs")
        opinion_repo.save_opinions(all_opinions)

def ensure_dir_exists(file_path):
    """Ensure the directory for a file exists."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def save_intermediate_data(data, file_path):
    """Save intermediate data to a JSON file."""
    ensure_dir_exists(file_path)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)

def load_intermediate_data(file_path, default=None):
    """Load intermediate data from a JSON file."""
    if not os.path.exists(file_path):
        return default or {}
    
    with open(file_path, 'r') as f:
        return json.load(f)

def main():
    """Run opinion extraction for the first 10 episodes chronologically."""
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
        logger.info("Starting opinion extraction script")
        logger.info(f"Command-line arguments: {vars(args)}")
        
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
            # Get the first N episodes chronologically
            logger.info(f"Getting the first {args.count} episodes chronologically")
            episodes = get_first_n_episodes_chronologically(episode_repo, args.count)
            logger.info(f"Found {len(episodes)} episodes")
            
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
                # Process each episode to extract raw opinions
                for episode in episodes_with_transcripts:
                    # Skip episodes without transcripts
                    if not episode.transcript_filename:
                        logger.warning(f"Episode {episode.title} has no transcript")
                        continue
                    
                    # Ensure we're using a TXT transcript
                    if not episode.transcript_filename.lower().endswith('.txt'):
                        logger.warning(f"Episode {episode.title} has non-TXT transcript: {episode.transcript_filename}")
                        continue
                        
                    transcript_path = os.path.join(str(config.transcripts_dir), episode.transcript_filename)
                    if not os.path.exists(transcript_path):
                        logger.warning(f"Transcript file {transcript_path} not found")
                        continue
                    
                    logger.info(f"Extracting raw opinions from episode: {episode.title}")
                    
                    # Extract raw opinions from this episode
                    raw_opinions = raw_extraction_service.extract_raw_opinions(
                        episode=episode,
                        transcript_path=transcript_path
                    )
                    
                    if raw_opinions:
                        logger.info(f"Extracted {len(raw_opinions)} raw opinions from {episode.title}")
                        all_raw_opinions.extend(raw_opinions)
                        
                        # Update the episode metadata
                        if "opinions" not in episode.metadata:
                            episode.metadata["opinions"] = {}
                        
                        # Add opinion IDs to episode metadata
                        for opinion in raw_opinions:
                            episode.metadata["opinions"][opinion["id"]] = {
                                "title": opinion["title"],
                                "category": opinion["category"]
                            }
                
                # Save the raw opinions to a file for future use
                save_intermediate_data(all_raw_opinions, args.raw_opinions_file)
                logger.info(f"Saved {len(all_raw_opinions)} raw opinions to {args.raw_opinions_file}")
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
                categorized_opinions = categorization_service.categorize_opinions(all_raw_opinions)
                
                # Ensure all categories exist in the repository
                categorization_service.ensure_categories_exist(list(categorized_opinions.keys()))
                
                # Save the categorized opinions to a file for future use
                save_intermediate_data(categorized_opinions, args.categorized_opinions_file)
                logger.info(f"Saved categorized opinions to {args.categorized_opinions_file}")
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
                relationship_data = relationship_service.analyze_relationships(categorized_opinions)
                
                # Save the relationship data to a file for future use
                save_intermediate_data(relationship_data, args.relationships_file)
                logger.info(f"Saved {len(relationship_data)} relationships to {args.relationships_file}")
        else:
            # Load previously analyzed relationships
            logger.info(f"Loading relationship data from {args.relationships_file}")
            relationship_data = load_intermediate_data(args.relationships_file, [])
            logger.info(f"Loaded {len(relationship_data)} relationships")
        
        # Stage 4: Opinion Merging and Saving
        if run_merging:
            if not all_raw_opinions or not relationship_data:
                logger.warning("Missing raw opinions or relationship data for merging")
            else:
                logger.info("Processing relationships and merging opinions")
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