#!/usr/bin/env python3
"""
Continue Opinion Processing

This script continues the opinion extraction pipeline from existing raw opinions.
It assumes you already have raw opinions extracted in a JSON file and continues
with the next stages: categorization, relationship analysis, merging, evolution
detection, and speaker tracking.

The script can be configured to run a single stage at a time for debugging purposes.
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
        default='data/jsonepisodes.json',
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
        '--single-stage',
        action='store_true',
        help='Run only a single stage (the start-stage) and stop'
    )
    
    parser.add_argument(
        '--debug-output',
        action='store_true',
        help='Save debug output files for the stage being processed'
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

def run_single_stage(extraction_service, stage_name, episodes, transcripts_dir, debug_output=False, output_dir=None):
    """
    Run a single processing stage and save stage-specific output files.
    
    Args:
        extraction_service: OpinionExtractionService instance
        stage_name: Name of the stage to run
        episodes: List of podcast episodes to process
        transcripts_dir: Directory containing transcript files
        debug_output: Whether to save debug output files
        output_dir: Directory to save output files
        
    Returns:
        Dictionary with stage results
    """
    logger.info(f"Running single stage: {stage_name}")
    
    result = {}
    all_raw_opinions = extraction_service.checkpoint_service.load_raw_opinions() or []
    
    if stage_name == 'raw_extraction':
        # Raw extraction is handled differently (needs transcripts)
        # For simplicity, we'll just verify raw opinions are loaded
        result['raw_opinions'] = all_raw_opinions
        
    elif stage_name == 'categorization':
        # Run categorization
        logger.info("Categorizing opinions")
        categorized_opinions = extraction_service.categorization_service.categorize_opinions(all_raw_opinions)
        result['categorized_opinions'] = categorized_opinions
        
        # Save debug output
        if debug_output and output_dir:
            output_file = os.path.join(output_dir, f"debug_{stage_name}_output.json")
            with open(output_file, 'w') as f:
                # Convert to serializable format
                output_data = {cat: [op for op in ops] for cat, ops in categorized_opinions.items()}
                json.dump(output_data, f, indent=2)
            logger.info(f"Saved categorization debug output to {output_file}")
            
    elif stage_name == 'relationship_analysis':
        # Run categorization first
        categorized_opinions = extraction_service.categorization_service.categorize_opinions(all_raw_opinions)
        
        # Then run relationship analysis
        logger.info("Analyzing relationships between opinions")
        relationship_data = extraction_service.relationship_service.analyze_relationships(categorized_opinions)
        result['relationship_data'] = relationship_data
        
        # Save debug output
        if debug_output and output_dir:
            output_file = os.path.join(output_dir, f"debug_{stage_name}_output.json")
            with open(output_file, 'w') as f:
                json.dump(relationship_data, f, indent=2)
            logger.info(f"Saved relationship analysis debug output to {output_file}")
            
    elif stage_name == 'opinion_merging':
        # Run prerequisite stages first (for data)
        categorized_opinions = extraction_service.categorization_service.categorize_opinions(all_raw_opinions)
        relationship_data = extraction_service.relationship_service.analyze_relationships(categorized_opinions)
        
        # Then run opinion merging
        logger.info("Merging opinions based on relationships")
        final_opinions_data = extraction_service.merger_service.process_relationships(
            raw_opinions=all_raw_opinions,
            relationship_data=relationship_data
        )
        result['final_opinions_data'] = final_opinions_data
        result['merged_opinions_count'] = len(final_opinions_data)
        
        # Create opinion objects
        final_opinions = extraction_service.merger_service.create_opinion_objects(final_opinions_data)
        result['final_opinions'] = final_opinions
        
        # Save debug output
        if debug_output and output_dir:
            output_file = os.path.join(output_dir, f"debug_{stage_name}_data_output.json")
            with open(output_file, 'w') as f:
                json.dump(final_opinions_data, f, indent=2)
            logger.info(f"Saved opinion merging data debug output to {output_file}")
            
            output_file = os.path.join(output_dir, f"debug_{stage_name}_objects_output.json")
            with open(output_file, 'w') as f:
                # Convert objects to dictionaries for serialization
                opinions_data = [opinion.to_dict() for opinion in final_opinions]
                json.dump(opinions_data, f, indent=2)
            logger.info(f"Saved opinion objects debug output to {output_file}")
            
    elif stage_name == 'evolution_detection':
        # Run prerequisite stages first (for data)
        categorized_opinions = extraction_service.categorization_service.categorize_opinions(all_raw_opinions)
        relationship_data = extraction_service.relationship_service.analyze_relationships(categorized_opinions)
        final_opinions_data = extraction_service.merger_service.process_relationships(
            raw_opinions=all_raw_opinions,
            relationship_data=relationship_data
        )
        final_opinions = extraction_service.merger_service.create_opinion_objects(final_opinions_data)
        
        # Get relationships for evolution analysis
        relationships = extraction_service.relationship_service.get_relationships_from_data(relationship_data)
        
        # Run evolution detection
        logger.info("Detecting opinion evolution")
        evolution_data = extraction_service.evolution_service.analyze_opinion_evolution(
            opinions=final_opinions,
            relationships=relationships
        )
        result['evolution_data'] = evolution_data
        
        # Save debug output
        if debug_output and output_dir:
            output_file = os.path.join(output_dir, f"debug_{stage_name}_output.json")
            
            # Create serializable data for evolution chains and speaker journeys
            serializable_evolution_chains = []
            for chain in evolution_data.get('evolution_chains', []):
                serializable_chain = {
                    'id': chain.id if hasattr(chain, 'id') else str(id(chain)),
                    'opinions': [op.id if hasattr(op, 'id') else str(id(op)) for op in chain.opinions] if hasattr(chain, 'opinions') else [],
                    'timespan': chain.timespan if hasattr(chain, 'timespan') else None,
                    'category': chain.category if hasattr(chain, 'category') else None,
                    'speaker_ids': chain.speaker_ids if hasattr(chain, 'speaker_ids') else [],
                    'description': chain.description if hasattr(chain, 'description') else None,
                }
                serializable_evolution_chains.append(serializable_chain)
            
            serializable_speaker_journeys = []
            for journey in evolution_data.get('speaker_journeys', []):
                serializable_journey = {
                    'speaker_id': journey.speaker_id if hasattr(journey, 'speaker_id') else str(id(journey)),
                    'speaker_name': journey.speaker_name if hasattr(journey, 'speaker_name') else None,
                    'evolution_chains': [
                        chain.id if hasattr(chain, 'id') else str(id(chain))
                        for chain in journey.evolution_chains
                    ] if hasattr(journey, 'evolution_chains') else [],
                    'timespan': journey.timespan if hasattr(journey, 'timespan') else None,
                    'categories': journey.categories if hasattr(journey, 'categories') else [],
                    'description': journey.description if hasattr(journey, 'description') else None,
                }
                serializable_speaker_journeys.append(serializable_journey)
                
            # Convert to serializable format
            output_data = {
                "evolution_chains": serializable_evolution_chains,
                "speaker_journeys": serializable_speaker_journeys
            }
            
            with open(output_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Saved evolution detection debug output to {output_file}")
            
            # Also save a results file with more details for analysis
            results_file = os.path.join(output_dir, "evolution_results.json")
            with open(results_file, 'w') as f:
                json.dump(output_data, f, indent=2)
            logger.info(f"Saved detailed evolution results to {results_file}")
            
    elif stage_name == 'speaker_tracking':
        # Run prerequisite stages first (for data)
        categorized_opinions = extraction_service.categorization_service.categorize_opinions(all_raw_opinions)
        relationship_data = extraction_service.relationship_service.analyze_relationships(categorized_opinions)
        final_opinions_data = extraction_service.merger_service.process_relationships(
            raw_opinions=all_raw_opinions,
            relationship_data=relationship_data
        )
        final_opinions = extraction_service.merger_service.create_opinion_objects(final_opinions_data)
        
        # Get relationships for evolution analysis
        relationships = extraction_service.relationship_service.get_relationships_from_data(relationship_data)
        
        # Run evolution detection to get evolution data
        evolution_data = extraction_service.evolution_service.analyze_opinion_evolution(
            opinions=final_opinions,
            relationships=relationships
        )
        
        # Run speaker tracking
        logger.info("Tracking speaker opinions and journeys")
        speaker_data = extraction_service.speaker_service.track_speakers(
            opinions=final_opinions,
            evolution_data=evolution_data
        )
        result['speaker_data'] = speaker_data
        
        # Save debug output
        if debug_output and output_dir:
            output_file = os.path.join(output_dir, f"debug_{stage_name}_output.json")
            
            # Create serializable data for speaker tracking
            serializable_speaker_data = {}
            
            # Handle speaker journeys if available
            if 'speaker_journeys' in speaker_data:
                serializable_journeys = []
                for journey in speaker_data.get('speaker_journeys', []):
                    serializable_journey = {
                        'speaker_id': journey.speaker_id if hasattr(journey, 'speaker_id') else str(id(journey)),
                        'speaker_name': journey.speaker_name if hasattr(journey, 'speaker_name') else None,
                        'evolution_chains': [
                            chain.id if hasattr(chain, 'id') else str(id(chain))
                            for chain in journey.evolution_chains
                        ] if hasattr(journey, 'evolution_chains') else [],
                        'timespan': journey.timespan if hasattr(journey, 'timespan') else None,
                        'categories': journey.categories if hasattr(journey, 'categories') else [],
                        'description': journey.description if hasattr(journey, 'description') else None,
                    }
                    serializable_journeys.append(serializable_journey)
                serializable_speaker_data['speaker_journeys'] = serializable_journeys
            
            # Handle other speaker tracking data
            for key, value in speaker_data.items():
                if key != 'speaker_journeys':
                    if isinstance(value, (str, int, float, bool, type(None))):
                        serializable_speaker_data[key] = value
                    elif isinstance(value, (list, dict)):
                        serializable_speaker_data[key] = value
                    else:
                        # Convert complex objects to their string representation
                        serializable_speaker_data[key] = str(value)
            
            with open(output_file, 'w') as f:
                json.dump(serializable_speaker_data, f, indent=2)
            logger.info(f"Saved speaker tracking debug output to {output_file}")
            
            # Also save a results file with more details for analysis
            results_file = os.path.join(output_dir, "speaker_tracking_results.json")
            with open(results_file, 'w') as f:
                json.dump(serializable_speaker_data, f, indent=2)
            logger.info(f"Saved detailed speaker tracking results to {results_file}")
    
    # Mark stage as complete
    extraction_service.checkpoint_service.mark_episode_stage_complete(
        episode_id=extraction_service.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
        stage=stage_name
    )
    
    # Add stage stats
    result['stage_stats'] = extraction_service.checkpoint_service.get_extraction_stats().get(stage_name, {})
    
    return result

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
    logger.info(f"Target starting stage: {args.start_stage} (int: {target_stage})")
    
    # Check if we need to force processing
    if current_stage_int is not None and current_stage_int >= target_stage and not args.force:
        logger.warning(f"Stage {args.start_stage} is already completed. Use --force to process anyway.")
        if args.dry_run or input("Continue anyway? (y/n): ").lower() != 'y':
            return 0
        
        # Reset checkpoint to just before target stage
        checkpoint_service.reset_checkpoint()
        # Mark raw extraction as completed since we're starting from raw opinions
        checkpoint_service.mark_episode_stage_complete(
            episode_id=checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"), 
            stage="raw_extraction"
        )
    
    # If dry run, just show what would be done
    if args.dry_run:
        logger.info("DRY RUN: Would continue processing from raw opinions:")
        with open(args.raw_opinions_path, 'r') as f:
            raw_opinions = json.load(f)
        
        logger.info(f"Would process {len(raw_opinions)} raw opinions")
        logger.info(f"Would start from stage: {args.start_stage}")
        logger.info(f"Would process {len(episodes_with_transcripts)} episodes")
        if args.single_stage:
            logger.info(f"Would only run stage: {args.start_stage}")
        logger.info(f"Would save output to: {args.output_dir}")
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
        if args.single_stage:
            # Run only a single stage
            logger.info(f"Running only stage: {args.start_stage}")
            stage_result = run_single_stage(
                extraction_service=extraction_service,
                stage_name=args.start_stage,
                episodes=episodes_with_transcripts,
                transcripts_dir=args.transcripts_dir,
                debug_output=args.debug_output,
                output_dir=args.output_dir
            )
            
            # Display stage details
            logger.info(f"Stage {args.start_stage} completed")
            
            # Save stage stats
            stats_file = os.path.join(args.output_dir, f"{args.start_stage}_stats.json")
            with open(stats_file, 'w') as f:
                json.dump(stage_result.get('stage_stats', {}), f, indent=2)
            logger.info(f"Saved stage stats to {stats_file}")
            
            # Print summary
            logger.info("-" * 50)
            logger.info(f"STAGE {args.start_stage.upper()} SUMMARY:")
            
            if args.start_stage == 'raw_extraction':
                logger.info(f"Raw opinions: {len(stage_result.get('raw_opinions', []))}")
            
            elif args.start_stage == 'categorization':
                categories = stage_result.get('categorized_opinions', {})
                logger.info(f"Categories found: {len(categories)}")
                for cat, opinions in categories.items():
                    logger.info(f"  - {cat}: {len(opinions)} opinions")
            
            elif args.start_stage == 'relationship_analysis':
                relationships = stage_result.get('relationship_data', [])
                logger.info(f"Relationships found: {len(relationships)}")
                relation_types = {}
                for rel in relationships:
                    rel_type = rel.get('relation_type')
                    relation_types[rel_type] = relation_types.get(rel_type, 0) + 1
                for rel_type, count in relation_types.items():
                    logger.info(f"  - {rel_type}: {count} relationships")
            
            elif args.start_stage == 'opinion_merging':
                logger.info(f"Final merged opinions: {stage_result.get('merged_opinions_count', 0)}")
                logger.info(f"Original opinions count: {len(extraction_service.checkpoint_service.load_raw_opinions() or [])}")
            
            elif args.start_stage == 'evolution_detection':
                evolution_data = stage_result.get('evolution_data', {})
                logger.info(f"Evolution chains: {len(evolution_data.get('evolution_chains', []))}")
                logger.info(f"Speaker journeys: {len(evolution_data.get('speaker_journeys', []))}")
            
            elif args.start_stage == 'speaker_tracking':
                speaker_data = stage_result.get('speaker_data', {})
                logger.info(f"Speaker journeys: {len(speaker_data.get('speaker_journeys', {}))}")
                
            logger.info("-" * 50)
            
        else:
            # Run the full extraction process from the specified stage
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