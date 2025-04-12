#!/usr/bin/env python3
"""
Script to check if the opinion merger service ran correctly.
Analyzes the debug files and final output to identify any issues.
"""

import json
import os
import logging
from collections import Counter

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def check_debug_files_exist():
    """Check if the debug output files were created."""
    debug_data_path = "data/opinions/debug_opinion_merging_data_output.json"
    debug_objects_path = "data/opinions/debug_opinion_merging_objects_output.json"
    stats_path = "data/opinions/opinion_merging_stats.json"
    processed_path = "data/opinions/processed_opinions.json"
    
    files_exist = True
    for path in [debug_data_path, debug_objects_path, stats_path, processed_path]:
        if not os.path.exists(path):
            logger.error(f"Missing file: {path}")
            files_exist = False
        else:
            file_size = os.path.getsize(path)
            logger.info(f"File exists: {path} (size: {file_size} bytes)")
    
    return files_exist

def analyze_merging_stats():
    """Analyze the merging statistics file."""
    stats_path = "data/opinions/opinion_merging_stats.json"
    
    try:
        with open(stats_path, 'r') as f:
            stats = json.load(f)
        
        if not stats:
            logger.error("Stats file is empty or contains empty JSON object")
            return False
            
        logger.info("Merging stats summary:")
        for key, value in stats.items():
            logger.info(f"  {key}: {value}")
            
        # Check for errors
        if stats.get("errors", 0) > 0:
            logger.warning(f"Found {stats['errors']} errors in merging process")
            
        # Check relationship application
        processed = stats.get("processed", 0)
        total = stats.get("total", 0)
        skipped = stats.get("skipped_missing_id", 0) + stats.get("skipped_already_merged", 0)
        
        if processed + skipped != total:
            logger.error(f"Relationship accounting error: processed ({processed}) + skipped ({skipped}) != total ({total})")
            
        return True
    except Exception as e:
        logger.error(f"Error analyzing stats file: {e}")
        return False

def analyze_debug_outputs():
    """Analyze the debug output files to check for correct processing."""
    debug_data_path = "data/opinions/debug_opinion_merging_data_output.json"
    debug_objects_path = "data/opinions/debug_opinion_merging_objects_output.json"
    
    try:
        # Load raw opinions data
        with open(debug_data_path, 'r') as f:
            raw_opinions = json.load(f)
        
        # Load processed opinions
        with open(debug_objects_path, 'r') as f:
            processed_opinions = json.load(f)
            
        logger.info(f"Raw opinions count: {len(raw_opinions)}")
        logger.info(f"Processed opinions count: {len(processed_opinions)}")
        
        # Count opinions with relationships
        related_count = sum(1 for op in processed_opinions if op.get('related_opinions') and len(op['related_opinions']) > 0)
        evolution_count = sum(1 for op in processed_opinions if op.get('evolution_chain') and len(op['evolution_chain']) > 0)
        contradiction_count = sum(1 for op in processed_opinions if op.get('is_contradiction', False))
        
        logger.info(f"Opinions with related opinions: {related_count}")
        logger.info(f"Opinions with evolution chains: {evolution_count}")
        logger.info(f"Opinions with contradictions: {contradiction_count}")
        
        # Check if relationships were applied at all
        if related_count == 0 and evolution_count == 0 and contradiction_count == 0:
            logger.error("No relationships were applied to any opinions")
            
        # Sample some opinions with relationships
        if related_count > 0:
            sample_related = next((op for op in processed_opinions if op.get('related_opinions') and len(op['related_opinions']) > 0), None)
            if sample_related:
                logger.info(f"Sample opinion with related opinions:")
                logger.info(f"  ID: {sample_related.get('id')}")
                logger.info(f"  Title: {sample_related.get('title')}")
                logger.info(f"  Related opinions: {sample_related.get('related_opinions')}")
                
        # Check for final processed opinions
        final_path = "data/opinions/processed_opinions.json"
        if os.path.exists(final_path):
            with open(final_path, 'r') as f:
                final_opinions = json.load(f)
            
            logger.info(f"Final opinions count: {len(final_opinions)}")
            
            # Check if final output matches debug output
            if len(final_opinions) != len(processed_opinions):
                logger.warning(f"Final opinions count ({len(final_opinions)}) differs from processed opinions count ({len(processed_opinions)})")
                
            # Count opinions with relationships in final output
            final_related_count = sum(1 for op in final_opinions if op.get('related_opinions') and len(op['related_opinions']) > 0)
            logger.info(f"Final opinions with related opinions: {final_related_count}")
            
            if final_related_count != related_count:
                logger.warning(f"Final related opinions count ({final_related_count}) differs from debug output ({related_count})")
                
        return True
    except Exception as e:
        logger.error(f"Error analyzing debug outputs: {e}")
        return False

def check_relationship_consistency():
    """Check if relationships are bidirectional and consistent."""
    processed_path = "data/opinions/processed_opinions.json"
    
    try:
        with open(processed_path, 'r') as f:
            opinions = json.load(f)
            
        # Create ID to index mapping for quick lookups
        id_to_index = {op['id']: i for i, op in enumerate(opinions)}
        
        # Track inconsistencies
        inconsistent_relations = 0
        missing_targets = 0
        
        # Check for bidirectional related_opinions links
        for opinion in opinions:
            op_id = opinion.get('id')
            related_ids = opinion.get('related_opinions', [])
            
            for related_id in related_ids:
                # Check if target opinion exists
                if related_id not in id_to_index:
                    logger.warning(f"Opinion {op_id} references non-existent related opinion {related_id}")
                    missing_targets += 1
                    continue
                    
                # Check if relationship is bidirectional
                target_opinion = opinions[id_to_index[related_id]]
                target_related_ids = target_opinion.get('related_opinions', [])
                
                if op_id not in target_related_ids:
                    logger.warning(f"Inconsistent relationship: {op_id} -> {related_id}, but not vice versa")
                    inconsistent_relations += 1
                    
        logger.info(f"Relationship consistency check:")
        logger.info(f"  Missing target opinions: {missing_targets}")
        logger.info(f"  Inconsistent relationships: {inconsistent_relations}")
        
        return True
    except Exception as e:
        logger.error(f"Error checking relationship consistency: {e}")
        return False

def main():
    """Main function to run all checks."""
    logger.info("Starting merger service results check")
    
    # Check if debug files exist
    files_exist = check_debug_files_exist()
    if not files_exist:
        logger.error("Missing one or more required files")
        
    # Analyze merging stats
    stats_ok = analyze_merging_stats()
    
    # Analyze debug outputs
    outputs_ok = analyze_debug_outputs()
    
    # Check relationship consistency
    consistency_ok = check_relationship_consistency()
    
    # Overall assessment
    if files_exist and stats_ok and outputs_ok and consistency_ok:
        logger.info("Merger service appears to have completed successfully")
    else:
        logger.warning("Merger service may have encountered issues")
        
    logger.info("Check complete")

if __name__ == "__main__":
    main() 