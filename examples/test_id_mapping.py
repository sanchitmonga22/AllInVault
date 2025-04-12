#!/usr/bin/env python3
"""
Test script to analyze ID mapping between relationship data and raw opinions.
This helps debug issues with opinion merging by showing detailed information
about ID formats and matches/mismatches.
"""

import json
import os
import sys
import logging
from pathlib import Path
from typing import Dict, List, Set

# Add src to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.services.opinion_extraction.relationship_service import OpinionRelationshipService
from src.services.opinion_extraction.merger_service import OpinionMergerService
from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)

def load_data(raw_opinions_path: str, relationships_path: str = None) -> tuple:
    """Load raw opinions and relationships data from files."""
    # Load raw opinions
    with open(raw_opinions_path, 'r') as f:
        raw_opinions = json.load(f)
    
    # Load relationships if path provided
    relationships = None
    if relationships_path and os.path.exists(relationships_path):
        with open(relationships_path, 'r') as f:
            relationships = json.load(f)
    else:
        # If no relationship file provided, look for relationship files in the checkpoints directory
        checkpoint_dir = os.path.join(os.path.dirname(raw_opinions_path), "..", "checkpoints", "llm_responses", "relationship_analysis")
        if os.path.exists(checkpoint_dir):
            # Get a sample relationship file
            rel_files = [f for f in os.listdir(checkpoint_dir) if f.endswith('.json')]
            if rel_files:
                sample_rel_file = os.path.join(checkpoint_dir, rel_files[0])
                logger.info(f"No relationship file provided, using sample from checkpoint: {sample_rel_file}")
                with open(sample_rel_file, 'r') as f:
                    rel_data = json.load(f)
                    # Most checkpoint files have a 'response' field with the actual relationships
                    if 'response' in rel_data and 'relationships' in rel_data['response']:
                        relationships = rel_data['response']['relationships']
    
    return raw_opinions, relationships

def analyze_id_formats(raw_opinions: List[Dict]) -> Dict:
    """Analyze the different ID formats in the raw opinions."""
    id_formats = {}
    id_examples = {}
    
    # Count different ID patterns
    for opinion in raw_opinions:
        if 'id' not in opinion:
            continue
            
        opinion_id = opinion['id']
        pattern = "plain"
        
        if '_' in opinion_id:
            parts = opinion_id.split('_')
            if len(parts) == 2:
                pattern = "number_episode"
            elif len(parts) == 3 and parts[1] == parts[2]:
                pattern = "number_episode_episode"
            else:
                pattern = f"other_{len(parts)}_parts"
        
        if pattern not in id_formats:
            id_formats[pattern] = 0
            id_examples[pattern] = []
        
        id_formats[pattern] += 1
        if len(id_examples[pattern]) < 3:
            id_examples[pattern].append(opinion_id)
    
    return {"formats": id_formats, "examples": id_examples}

def test_id_mapping(raw_opinions_path: str, relationships_path: str = None):
    """Test the ID mapping between relationship data and raw opinions."""
    # Load data
    raw_opinions, relationship_data = load_data(raw_opinions_path, relationships_path)
    
    logger.info(f"Loaded {len(raw_opinions)} raw opinions")
    if relationship_data:
        logger.info(f"Loaded {len(relationship_data)} relationships")
    
    # Analyze ID formats
    id_analysis = analyze_id_formats(raw_opinions)
    logger.info("ID Format Analysis:")
    for pattern, count in id_analysis["formats"].items():
        percentage = (count / len(raw_opinions)) * 100
        logger.info(f"  {pattern}: {count} opinions ({percentage:.1f}%), Examples: {id_analysis['examples'][pattern][:3]}")
    
    # Create repositories and services
    opinion_repo = OpinionRepository()
    category_repo = CategoryRepository()
    relationship_service = OpinionRelationshipService()
    merger_service = OpinionMergerService(opinion_repo, category_repo)
    
    # Build opinion ID map
    opinion_map = {}
    id_variants_map = {}
    
    for opinion in raw_opinions:
        if 'id' in opinion:
            canonical_id = opinion['id']
            opinion_map[canonical_id] = opinion
            id_variants_map[canonical_id] = canonical_id
            
            # Generate and map variant IDs
            if '_' in canonical_id:
                # Extract parts: opinion number and episode ID
                parts = canonical_id.split('_', 1)
                if len(parts) == 2:
                    opinion_num = parts[0]
                    episode_id = parts[1]
                    
                    # Create variants
                    id_variants_map[opinion_num] = canonical_id  # Just the number
                    id_variants_map[f"{opinion_num}_{episode_id}_{episode_id}"] = canonical_id  # Double episode format
    
    # Process relationships if available
    if relationship_data:
        # First, normalize the relationship IDs
        processed_relationships = relationship_service.get_relationships_from_data(relationship_data)
        logger.info(f"Processed {len(processed_relationships)} relationships for ID mapping")
        
        # Test ID lookup for each relationship
        successful_matches = 0
        failed_matches = 0
        
        for i, rel in enumerate(processed_relationships[:20]):  # Test first 20 for brevity
            source_id = rel.get('source_id')
            target_id = rel.get('target_id')
            source_episode_id = rel.get('source_episode_id', '')
            target_episode_id = rel.get('target_episode_id', '')
            
            logger.info(f"\nTesting relationship {i+1}:")
            logger.info(f"  Source: {source_id}, Episode: {source_episode_id}")
            logger.info(f"  Target: {target_id}, Episode: {target_episode_id}")
            logger.debug(f"  Relation type: {rel.get('relation_type')}")
            logger.debug(f"  Notes: {rel.get('notes', '')}")
            
            # Try all possible variations for source opinion
            possible_source_ids = [
                source_id,
                f"{source_id}_{source_episode_id}" if source_episode_id else None,
                f"{source_id}_{source_episode_id}_{source_episode_id}" if source_episode_id else None
            ]
            
            # Add additional ID formats if provided
            source_id_formats = rel.get('source_id_formats', [])
            if source_id_formats:
                possible_source_ids.extend([f for f in source_id_formats if f and f not in possible_source_ids])
            
            logger.info(f"  Possible source IDs: {[id for id in possible_source_ids if id]}")
            
            source_opinion = None
            source_matched_id = None
            
            for possible_id in possible_source_ids:
                if not possible_id:
                    continue
                    
                # Direct match
                if possible_id in opinion_map:
                    source_opinion = opinion_map[possible_id]
                    source_matched_id = possible_id
                    logger.info(f"  ✓ Found source with direct ID: {possible_id}")
                    break
                # Check variant map
                elif possible_id in id_variants_map:
                    canonical_id = id_variants_map[possible_id]
                    source_opinion = opinion_map[canonical_id]
                    source_matched_id = canonical_id
                    logger.info(f"  ✓ Found source using variant mapping: {possible_id} -> {canonical_id}")
                    break
            
            if not source_opinion:
                logger.info(f"  ✗ Failed to find source opinion with ID: {source_id}")
                # Show available IDs with similar patterns to help debug
                similar_ids = [id for id in opinion_map.keys() if source_id in id or (source_episode_id and source_episode_id in id)]
                if similar_ids:
                    logger.info(f"  Similar IDs in opinion map: {similar_ids[:5]}")
                failed_matches += 1
            
            # Similar process for target
            possible_target_ids = [
                target_id,
                f"{target_id}_{target_episode_id}" if target_episode_id else None,
                f"{target_id}_{target_episode_id}_{target_episode_id}" if target_episode_id else None
            ]
            
            # Add additional ID formats if provided
            target_id_formats = rel.get('target_id_formats', [])
            if target_id_formats:
                possible_target_ids.extend([f for f in target_id_formats if f and f not in possible_target_ids])
            
            logger.info(f"  Possible target IDs: {[id for id in possible_target_ids if id]}")
            
            target_opinion = None
            target_matched_id = None
            
            for possible_id in possible_target_ids:
                if not possible_id:
                    continue
                    
                # Direct match
                if possible_id in opinion_map:
                    target_opinion = opinion_map[possible_id]
                    target_matched_id = possible_id
                    logger.info(f"  ✓ Found target with direct ID: {possible_id}")
                    break
                # Check variant map
                elif possible_id in id_variants_map:
                    canonical_id = id_variants_map[possible_id]
                    target_opinion = opinion_map[canonical_id]
                    target_matched_id = canonical_id
                    logger.info(f"  ✓ Found target using variant mapping: {possible_id} -> {canonical_id}")
                    break
            
            if not target_opinion:
                logger.info(f"  ✗ Failed to find target opinion with ID: {target_id}")
                # Show available IDs with similar patterns to help debug
                similar_ids = [id for id in opinion_map.keys() if target_id in id or (target_episode_id and target_episode_id in id)]
                if similar_ids:
                    logger.info(f"  Similar IDs in opinion map: {similar_ids[:5]}")
                failed_matches += 1
            
            if source_opinion and target_opinion:
                logger.info(f"  ✓ Complete match: {source_matched_id} -> {target_matched_id}")
                successful_matches += 1
        
        logger.info(f"\nMatching summary for sample:")
        logger.info(f"  Successful complete matches: {successful_matches}")
        logger.info(f"  Failed matches: {failed_matches}")
        percentage = (successful_matches / (successful_matches + failed_matches)) * 100 if (successful_matches + failed_matches) > 0 else 0
        logger.info(f"  Success rate: {percentage:.1f}%")
    
    # Test running the merger service
    if relationship_data:
        try:
            logger.info("\nTesting merger service with improved ID mapping...")
            processed_relationships = relationship_service.get_relationships_from_data(relationship_data)
            
            # Run the merger service
            merged_opinions = merger_service.process_relationships(raw_opinions, processed_relationships)
            
            # Count relationships in result
            opinions_with_relationships = 0
            total_relationships = 0
            
            for opinion in merged_opinions:
                if 'related_opinions' in opinion and opinion['related_opinions']:
                    opinions_with_relationships += 1
                    total_relationships += len(opinion['related_opinions'])
            
            logger.info(f"Merger service results:")
            logger.info(f"  Total opinions after merging: {len(merged_opinions)}")
            logger.info(f"  Opinions with relationships: {opinions_with_relationships}")
            logger.info(f"  Total relationships established: {total_relationships // 2}")  # Divide by 2 because bidirectional
            
            # Sample of opinions with relationships
            if opinions_with_relationships > 0:
                sample_size = min(5, opinions_with_relationships)
                samples = []
                for opinion in merged_opinions:
                    if 'related_opinions' in opinion and opinion['related_opinions']:
                        samples.append(opinion)
                        if len(samples) >= sample_size:
                            break
                
                logger.info(f"\nSample opinions with relationships:")
                for i, opinion in enumerate(samples):
                    logger.info(f"  Opinion {i+1} (ID: {opinion['id']}):")
                    logger.info(f"    Title: {opinion.get('title', 'N/A')}")
                    logger.info(f"    Related opinions: {opinion['related_opinions']}")
                    if 'evolution_chain' in opinion and opinion['evolution_chain']:
                        logger.info(f"    Evolution chain: {opinion['evolution_chain']}")
                    if 'is_contradiction' in opinion and opinion['is_contradiction']:
                        logger.info(f"    Contradicts: {opinion.get('contradicts_opinion_id', 'N/A')}")
            
        except Exception as e:
            logger.error(f"Error testing merger service: {e}")
            logger.exception("Detailed error:")

if __name__ == "__main__":
    # Parse command line arguments
    import argparse
    
    parser = argparse.ArgumentParser(description="Test ID mapping between relationships and opinions")
    parser.add_argument("--raw-opinions", required=True, help="Path to raw opinions JSON file")
    parser.add_argument("--relationships", help="Path to relationships JSON file (optional)")
    
    args = parser.parse_args()
    
    # Run the test
    test_id_mapping(args.raw_opinions, args.relationships) 