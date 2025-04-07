#!/usr/bin/env python3
"""
Run opinion extraction for the first 10 episodes in chronological order.

This script:
1. Loads all episodes from the repository
2. Sorts them by published date
3. Selects the first 10 episodes
4. Processes them one by one with a delay between each to avoid API rate limiting
5. Supports opinion evolution tracking across episodes

Usage:
  python run_opinion_extraction_for_first_10.py [--count N] [--max-transcript-tokens N] [--delay N]
  
Options:
  --count N                  Number of episodes to process (default: 10)
  --max-transcript-tokens N  Maximum transcript tokens to process (default: 10000)
  --delay N                  Delay between episodes in seconds (default: 120)
  --max-opinions N           Maximum opinions per episode (default: 10)
  --max-context N            Maximum context opinions (default: 10)
  --batch-size N             Process episodes in batches of N (default: 1)
  --transcript-format        Format of transcript files to use (json or txt) (default: json)
"""

import logging
import sys
import time
import json
import argparse
from typing import List, Dict, Any
from datetime import datetime
import uuid
from pathlib import Path
from collections import defaultdict

from src.services.pipeline_orchestrator import PipelineOrchestrator, PipelineStage
from src.repositories.episode_repository import JsonFileRepository
from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository
from src.utils.config import load_config
from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion
from src.models.opinions.category import Category

# Parse command-line arguments
def parse_args():
    parser = argparse.ArgumentParser(description="Run opinion extraction for podcast episodes")
    parser.add_argument("--count", type=int, default=10, help="Number of episodes to process")
    parser.add_argument("--max-transcript-tokens", type=int, default=10000, 
                        help="Maximum transcript tokens to process")
    parser.add_argument("--delay", type=int, default=10, 
                        help="Delay between episodes in seconds")
    parser.add_argument("--max-opinions", type=int, default=10,
                        help="Maximum opinions per episode")  
    parser.add_argument("--max-context", type=int, default=10,
                        help="Maximum context opinions")
    parser.add_argument("--batch-size", type=int, default=1,
                        help="Process episodes in batches of this size")
    parser.add_argument("--restart-from", type=str, default=None,
                        help="Episode ID to restart processing from")
    parser.add_argument("--skip-processed", action="store_true", default=True,
                        help="Skip episodes that already have opinions")
    parser.add_argument("--reset-rate-limit", action="store_true", default=False,
                        help="Add an extended delay at the start to reset rate limits")
    parser.add_argument("--log-level", type=str, choices=["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
                        default="INFO", help="Logging level")
    parser.add_argument("--log-file", type=str, default=None,
                        help="Path to log file (if not specified, logs will only go to console)")
    parser.add_argument("--dry-run", action="store_true", default=False,
                        help="Dry run - don't actually process episodes, just show what would be done")
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

# Paths
DATA_DIR = Path("data")
EPISODE_DATA_DIR = DATA_DIR / "episodes"
TRANSCRIPT_DATA_DIR = DATA_DIR / "transcripts"
OPINION_DATA_DIR = DATA_DIR / "opinions"

# Create directories if they don't exist
OPINION_DATA_DIR.mkdir(parents=True, exist_ok=True)

OPINIONS_FILE = OPINION_DATA_DIR / "opinions.json"
CATEGORIES_FILE = OPINION_DATA_DIR / "categories.json"

# Initialize repositories
episode_repo = JsonFileRepository(str(EPISODE_DATA_DIR))
opinion_repo = OpinionRepository(opinions_file_path=str(OPINIONS_FILE))
category_repo = CategoryRepository(categories_file_path=str(CATEGORIES_FILE))

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
        txt_path = TRANSCRIPT_DATA_DIR / f"{video_id}.txt"
        
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
    sorted_episodes = sorted(all_episodes, key=lambda ep: ep.published_at)
    
    # If start_from_id is provided, skip episodes until we find it
    if start_from_id:
        for i, episode in enumerate(sorted_episodes):
            if episode.video_id == start_from_id:
                sorted_episodes = sorted_episodes[i:]
                break
    
    # Return the first n episodes
    return sorted_episodes[:n]

def migrate_opinions_to_categories(opinion_repo: OpinionRepository, category_repo: CategoryRepository, logger=None) -> None:
    """
    Migrate existing opinions to use the new category system.
    
    Args:
        opinion_repo: Opinion repository
        category_repo: Category repository
        logger: Logger instance (optional)
    """
    # Use module logger if none provided
    if logger is None:
        logger = logging.getLogger("OpinionExtraction")
        
    logger.info("Migrating existing opinions to use the category system...")
    opinions = opinion_repo.get_all_opinions()
    
    if not opinions:
        logger.info("No opinions found to migrate")
        return
    
    migrated_count = 0
    for opinion in opinions:
        needs_update = False
        
        # Check if the opinion already has a category_id
        if not hasattr(opinion, 'category_id') or not opinion.category_id:
            # Check if the opinion has the old category string field
            if hasattr(opinion, 'category') and opinion.category:
                # Find or create the appropriate category
                category = category_repo.find_or_create_category(opinion.category)
                # Set the category_id
                opinion.category_id = category.id
                needs_update = True
                migrated_count += 1
        
        # Initialize new fields if they don't exist
        if not hasattr(opinion, 'speaker_timestamps') or not opinion.speaker_timestamps:
            opinion.speaker_timestamps = {}
            # Initialize with default data from speaker_id
            if hasattr(opinion, 'speaker_id') and opinion.speaker_id:
                opinion.speaker_timestamps[opinion.speaker_id] = {
                    'start_time': getattr(opinion, 'start_time', 0.0),
                    'end_time': getattr(opinion, 'end_time', 0.0),
                    'stance': 'support',  # Default stance for the primary speaker
                    'episode_id': opinion.episode_id
                }
            needs_update = True
        
        if not hasattr(opinion, 'appeared_in_episodes') or not opinion.appeared_in_episodes:
            opinion.appeared_in_episodes = [opinion.episode_id]
            needs_update = True
            
        if not hasattr(opinion, 'is_contradiction'):
            opinion.is_contradiction = False
            needs_update = True
            
        if not hasattr(opinion, 'contradicts_opinion_id'):
            opinion.contradicts_opinion_id = None
            needs_update = True
            
        if not hasattr(opinion, 'contradiction_notes'):
            opinion.contradiction_notes = None
            needs_update = True
        
        if needs_update:
            migrated_count += 1
    
    # Save migrated opinions
    if migrated_count > 0:
        logger.info(f"Migrated {migrated_count} opinions to use new fields")
        opinion_repo.save_opinions(opinions)
    else:
        logger.info("No opinions needed migration")

def show_opinion_statistics(opinion_repo: OpinionRepository, category_repo: CategoryRepository, logger=None) -> None:
    """
    Display statistics about opinions and categories.
    
    Args:
        opinion_repo: Opinion repository
        category_repo: Category repository
        logger: Logger instance (optional)
    """
    # Use module logger if none provided
    if logger is None:
        logger = logging.getLogger("OpinionExtraction")
        
    opinions = opinion_repo.get_all_opinions()
    categories = category_repo.get_all_categories()
    
    if not opinions:
        logger.info("No opinions found in the repository")
        return
    
    # Count opinions by category
    category_counts = {}
    for opinion in opinions:
        category_id = getattr(opinion, 'category_id', None)
        if category_id:
            if category_id not in category_counts:
                category_counts[category_id] = 0
            category_counts[category_id] += 1
    
    # Count opinions by speaker (accounting for multi-speaker opinions)
    speaker_counts = {}
    shared_opinion_count = 0
    
    for opinion in opinions:
        # Check if it's a multi-speaker opinion
        is_multi_speaker = False
        speaker_ids = []
        
        # Get speaker IDs from speaker_timestamps if available
        if hasattr(opinion, 'speaker_timestamps') and opinion.speaker_timestamps:
            speaker_ids = list(opinion.speaker_timestamps.keys())
            if len(speaker_ids) > 1:
                is_multi_speaker = True
                shared_opinion_count += 1
        elif ',' in getattr(opinion, 'speaker_name', ''):
            # Handle legacy multi-speaker format with comma-separated names
            is_multi_speaker = True
            shared_opinion_count += 1
            speaker_names = [name.strip() for name in opinion.speaker_name.split(',')]
            for speaker_name in speaker_names:
                if speaker_name not in speaker_counts:
                    speaker_counts[speaker_name] = 0
                speaker_counts[speaker_name] += 1
        
        # Count speakers from speaker_timestamps
        if speaker_ids:
            for speaker_id in speaker_ids:
                # Get a speaker name from the ID or use the ID itself
                speaker_name = f"Speaker {speaker_id}"
                if speaker_name not in speaker_counts:
                    speaker_counts[speaker_name] = 0
                speaker_counts[speaker_name] += 1
        else:
            # Use single speaker_id and speaker_name
            speaker_name = getattr(opinion, 'speaker_name', 'Unknown')
            if speaker_name not in speaker_counts:
                speaker_counts[speaker_name] = 0
            speaker_counts[speaker_name] += 1
    
    # Count opinions by episode
    episode_counts = {}
    for opinion in opinions:
        # Use appeared_in_episodes if available
        episodes = getattr(opinion, 'appeared_in_episodes', [])
        if not episodes:
            episodes = [opinion.episode_id]
            
        for ep_id in episodes:
            if ep_id not in episode_counts:
                episode_counts[ep_id] = 0
            episode_counts[ep_id] += 1
    
    # Count opinions with evolution tracking and contradictions
    evolution_count = sum(1 for op in opinions if getattr(op, 'evolution_notes', None))
    related_count = sum(1 for op in opinions if getattr(op, 'related_opinions', []))
    contradiction_count = sum(1 for op in opinions if getattr(op, 'is_contradiction', False))
    
    # Count contentious opinions (those where speakers have opposing stances)
    contentious_count = 0
    
    # Count stances for multi-speaker opinions
    stance_counts = {"support": 0, "oppose": 0, "neutral": 0, "unknown": 0}
    cross_episode_count = 0
    
    for opinion in opinions:
        # Check for contentious opinions
        if hasattr(opinion, 'speaker_timestamps') and opinion.speaker_timestamps:
            has_support = False
            has_oppose = False
            
            for speaker_id, data in opinion.speaker_timestamps.items():
                stance = data.get('stance', 'unknown').lower()
                if stance in stance_counts:
                    stance_counts[stance] += 1
                else:
                    stance_counts["unknown"] += 1
                    
                if stance == 'support':
                    has_support = True
                elif stance == 'oppose':
                    has_oppose = True
            
            if has_support and has_oppose:
                contentious_count += 1
        
        # Count cross-episode opinions
        if hasattr(opinion, 'appeared_in_episodes') and len(getattr(opinion, 'appeared_in_episodes', [])) > 1:
            cross_episode_count += 1
    
    # Display statistics
    logger.info(f"Opinion Statistics:")
    logger.info(f"Total Opinions: {len(opinions)}")
    logger.info(f"Opinions with Evolution Notes: {evolution_count}")
    logger.info(f"Opinions with Related Opinions: {related_count}")
    logger.info(f"Multi-Speaker Opinions: {shared_opinion_count}")
    logger.info(f"Contradicting Opinions: {contradiction_count}")
    logger.info(f"Contentious Opinions (disagreement): {contentious_count}")
    logger.info(f"Cross-Episode Opinions: {cross_episode_count}")
    
    if sum(stance_counts.values()) > 0:
        logger.info("\nStance Distribution:")
        for stance, count in stance_counts.items():
            if count > 0:
                logger.info(f"  {stance.capitalize()}: {count}")
    
    logger.info("\nOpinions by Category:")
    category_dict = {cat.id: cat for cat in categories}
    for category_id, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True):
        category_name = category_dict.get(category_id, {}).name if category_id in category_dict else f"Category {category_id}"
        logger.info(f"  {category_name}: {count}")
    
    logger.info("\nOpinions by Speaker:")
    for speaker, count in sorted(speaker_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {speaker}: {count}")
    
    logger.info("\nOpinions by Episode:")
    for episode_id, count in sorted(episode_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info(f"  {episode_id}: {count}")

def main():
    """Run opinion extraction for episodes chronologically, one at a time."""
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
        episode_repo = JsonFileRepository(str(config.episodes_db_path))
        opinion_repo = OpinionRepository(str(OPINIONS_FILE))
        category_repo = CategoryRepository(str(CATEGORIES_FILE))
        logger.debug("Repositories initialized successfully")
        
        # Add a delay at the start if requested, to reset rate limits
        if args.reset_rate_limit:
            delay_seconds = 300
            logger.info(f"Adding an extended delay to reset rate limits ({delay_seconds//60} minutes)...")
            if not args.dry_run:
                for remaining in range(delay_seconds, 0, -30):
                    logger.debug(f"Rate limit reset: {remaining} seconds remaining")
                    time.sleep(min(30, remaining))
                logger.info("Rate limit reset delay completed")
            else:
                logger.info(f"[DRY RUN] Would wait {delay_seconds} seconds for rate limit reset")
        
        # Migrate existing opinions to use the category system
        logger.info("Starting opinion migration to category system")
        if not args.dry_run:
            migrate_start = time.time()
            migrate_opinions_to_categories(opinion_repo, category_repo, logger)
            migrate_duration = time.time() - migrate_start
            logger.info(f"Opinion migration completed in {migrate_duration:.2f} seconds")
        else:
            logger.info("[DRY RUN] Would migrate opinions to category system")
        
        # Display initial statistics
        logger.info("Initial opinion statistics:")
        show_opinion_statistics(opinion_repo, category_repo, logger)
        
        # Get episodes chronologically, optionally starting from a specific episode
        logger.info(f"Retrieving first {args.count} episodes chronologically" + 
                   (f" starting from ID {args.restart_from}" if args.restart_from else ""))
        episodes_start = time.time()
        episodes = get_first_n_episodes_chronologically(
            episode_repo, 
            args.count, 
            start_from_id=args.restart_from
        )
        episodes_duration = time.time() - episodes_start
        logger.debug(f"Retrieved episodes in {episodes_duration:.2f} seconds")
        
        if not episodes:
            logger.error("No episodes found in the repository")
            return 1
        
        logger.info(f"Found {len(episodes)} episodes to process")
        
        # Update transcript filenames to use TXT format
        logger.info("Updating transcript filenames to use TXT format")
        transcript_start = time.time()
        episodes = update_transcript_filenames(episodes)
        
        # Save the updated transcript filenames to the repository
        logger.info("Saving updated transcript filenames to the repository")
        for episode in episodes:
            if episode.transcript_filename:
                episode_repo.save_episode(episode)
                
        transcript_duration = time.time() - transcript_start
        logger.debug(f"Updated transcript filenames in {transcript_duration:.2f} seconds")
        
        # Log the episodes we're processing
        logger.info(f"Processing opinion extraction for the following {len(episodes)} episodes:")
        for i, episode in enumerate(episodes):
            published_date = episode.published_at.strftime('%Y-%m-%d')
            transcript_status = "Available" if episode.transcript_filename else "Not Found"
            logger.info(f"{i+1}. [{published_date}] {episode.title} (ID: {episode.video_id}, Transcript: {transcript_status})")
        
        # Initialize the pipeline orchestrator
        orchestrator = PipelineOrchestrator()
        
        # Process episodes in batches if requested
        total_batches = (len(episodes) + args.batch_size - 1) // args.batch_size
        successful_batches = 0
        failed_batches = 0
        skipped_batches = 0
        total_opinions_extracted = 0
        
        logger.info(f"Processing {len(episodes)} episodes in {total_batches} batch(es) of size {args.batch_size}")
        
        for i in range(0, len(episodes), args.batch_size):
            batch_num = i//args.batch_size + 1
            batch = episodes[i:i+args.batch_size]
            batch_start_time = time.time()
            logger.info(f"Processing batch {batch_num}/{total_batches} with {len(batch)} episodes")
            
            batch_episode_ids = []
            for episode in batch:
                # Skip episodes without transcripts
                if not episode.transcript_filename:
                    logger.warning(f"No transcript found for episode {episode.title} (ID: {episode.video_id}). Skipping.")
                    continue
                    
                # Check if opinions already exist for this episode
                if args.skip_processed:
                    existing_opinions = opinion_repo.get_all_opinions()
                    episode_opinions = [op for op in existing_opinions if op.episode_id == episode.video_id]
                    
                    if episode_opinions:
                        logger.info(f"Found {len(episode_opinions)} existing opinions for episode {episode.title} (ID: {episode.video_id}). Skipping.")
                        continue
                
                # Add this episode to the batch
                batch_episode_ids.append(episode.video_id)
            
            if not batch_episode_ids:
                logger.info("No episodes to process in this batch. Continuing.")
                skipped_batches += 1
                continue
                
            logger.info(f"Processing {len(batch_episode_ids)} episodes in this batch")
            
            # Implement retry logic with exponential backoff
            max_retries = 3
            retry_delay = 60  # Initial delay in seconds
            attempt = 0
            success = False
            batch_opinions_count = 0
            
            while attempt < max_retries and not success:
                try:
                    attempt += 1
                    if attempt > 1:
                        logger.info(f"Attempt {attempt}/{max_retries} after waiting {retry_delay}s")
                    
                    # Execute the opinion extraction stage for this batch
                    logger.debug(f"Executing opinion extraction for episode IDs: {batch_episode_ids}")
                    
                    if args.dry_run:
                        logger.info(f"[DRY RUN] Would extract opinions for {len(batch_episode_ids)} episodes")
                        # Simulate success in dry run mode
                        result = type('obj', (object,), {
                            'success': True,
                            'message': "Dry run simulation",
                            'data': {'opinions_count': 0}
                        })
                    else:
                        extraction_start = time.time()
                        result = orchestrator.execute_stage(
                            PipelineStage.EXTRACT_OPINIONS,
                            episode_ids=batch_episode_ids,
                            # Skip dependencies check to only run this stage
                            check_dependencies=False,
                            # Additional parameters for the opinion extraction stage
                            use_llm=True,
                            llm_provider="openai",
                            transcripts_dir=str(config.transcripts_dir),
                            max_context_opinions=args.max_context,     
                            max_opinions_per_episode=args.max_opinions,
                            # Add parameters to reduce transcript length
                            max_transcript_tokens=args.max_transcript_tokens,
                            transcript_chunk_size=args.max_transcript_tokens,
                            include_speaker_metadata=True
                        )
                        extraction_duration = time.time() - extraction_start
                        logger.debug(f"Opinion extraction completed in {extraction_duration:.2f} seconds")
                    
                    # Check for API rate limit errors in the result
                    if not result.success and "rate_limit_exceeded" in str(result.message).lower():
                        logger.warning(f"API rate limit exceeded. Retrying after backoff.")
                        retry_delay *= 2  # Exponential backoff
                        time.sleep(retry_delay)
                        continue
                        
                    # If we get here, either success or non-rate-limit error
                    success = result.success
                    
                    # Print result
                    if result.success:
                        # Get the number of opinions extracted in this batch
                        if hasattr(result, 'data') and result.data and 'opinions_count' in result.data:
                            batch_opinions_count = result.data['opinions_count']
                        else:
                            # Count opinions manually if not provided in result
                            existing_opinions = opinion_repo.get_all_opinions()
                            batch_opinions_count = sum(1 for op in existing_opinions if op.episode_id in batch_episode_ids)
                        
                        logger.info(f"Opinion extraction completed successfully: {result.message}")
                        logger.info(f"Extracted {batch_opinions_count} opinions from {len(batch_episode_ids)} episodes")
                        total_opinions_extracted += batch_opinions_count
                    else:
                        logger.error(f"Opinion extraction failed: {result.message}")
                        
                    break  # Exit retry loop
                    
                except Exception as e:
                    if "rate_limit" in str(e).lower() or "429" in str(e):
                        logger.warning(f"API rate limit error: {e}")
                        if attempt < max_retries:
                            logger.info(f"Retrying after {retry_delay} seconds (attempt {attempt}/{max_retries})...")
                            time.sleep(retry_delay)
                            retry_delay *= 2  # Exponential backoff
                        else:
                            logger.error(f"Max retries reached. Moving to next batch.")
                    else:
                        logger.error(f"Error processing batch: {e}")
                        break  # Non-rate-limit error, exit retry loop
            
            # Track batch success/failure
            batch_end_time = time.time()
            batch_duration = batch_end_time - batch_start_time
            
            if success:
                successful_batches += 1
                logger.info(f"Batch {batch_num}/{total_batches} completed successfully in {batch_duration:.2f} seconds")
            else:
                failed_batches += 1
                logger.warning(f"Batch {batch_num}/{total_batches} failed after {batch_duration:.2f} seconds")
            
            # Display updated statistics after each batch
            logger.info(f"Updated opinion statistics after batch {batch_num}/{total_batches}:")
            if not args.dry_run:
                show_opinion_statistics(opinion_repo, category_repo, logger)
            else:
                logger.info("[DRY RUN] Would show opinion statistics here")
            
            # Add delay between batches to avoid API rate limiting
            if i + args.batch_size < len(episodes):
                logger.info(f"Waiting {args.delay} seconds before processing next batch...")
                if not args.dry_run:
                    for remaining in range(args.delay, 0, -5):
                        logger.debug(f"Batch delay: {remaining} seconds remaining")
                        time.sleep(min(5, remaining))
                else:
                    logger.info(f"[DRY RUN] Would wait {args.delay} seconds")
        
        # Calculate and log overall statistics
        end_time = time.time()
        total_duration = end_time - start_time
        hours, remainder = divmod(total_duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        logger.info("Opinion extraction completed for all episodes!")
        logger.info(f"Total runtime: {int(hours)}h {int(minutes)}m {seconds:.2f}s")
        logger.info(f"Batch statistics: {successful_batches} successful, {failed_batches} failed, {skipped_batches} skipped")
        logger.info(f"Total opinions extracted: {total_opinions_extracted}")
        
        # Show final opinion statistics
        logger.info("Final opinion statistics:")
        if not args.dry_run:
            show_opinion_statistics(opinion_repo, category_repo, logger)
        else:
            logger.info("[DRY RUN] Would show final opinion statistics here")
        
        return 0
            
    except Exception as e:
        # Calculate runtime even in case of error
        end_time = time.time()
        total_duration = end_time - start_time
        hours, remainder = divmod(total_duration, 3600)
        minutes, seconds = divmod(remainder, 60)
        
        # Enhanced error logging with traceback
        logger.error(f"Error: {e}")
        logger.error(f"Runtime before error: {int(hours)}h {int(minutes)}m {seconds:.2f}s")
        logger.error("Traceback:", exc_info=True)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 