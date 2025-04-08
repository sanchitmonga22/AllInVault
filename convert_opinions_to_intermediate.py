#!/usr/bin/env python3
"""
Convert existing opinions from data/json/opinions.json to intermediate formats.

This script:
1. Loads existing opinions from data/json/opinions.json
2. Converts them to raw opinions format
3. Creates categorized opinions by category
4. Extracts relationship data
5. Saves all intermediate formats for use with the staged pipeline

Usage:
  python convert_opinions_to_intermediate.py
"""

import json
import os
import logging
from pathlib import Path
from collections import defaultdict

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# File paths
OPINIONS_FILE = "data/json/opinions.json"
RAW_OPINIONS_FILE = "data/intermediate/raw_opinions.json"
CATEGORIZED_OPINIONS_FILE = "data/intermediate/categorized_opinions.json"
RELATIONSHIPS_FILE = "data/intermediate/relationships.json"

def ensure_dir_exists(file_path):
    """Ensure the directory for a file exists."""
    directory = os.path.dirname(file_path)
    if directory and not os.path.exists(directory):
        os.makedirs(directory)

def load_opinions():
    """Load opinions from the JSON file."""
    with open(OPINIONS_FILE, 'r') as f:
        data = json.load(f)
    
    return data.get('opinions', [])

def convert_to_raw_opinions(opinions):
    """Convert structured opinions to raw opinion format."""
    raw_opinions = []
    
    for opinion in opinions:
        # For each appearance, create a separate raw opinion
        for appearance in opinion.get('appearances', []):
            raw_opinion = {
                'id': f"raw-{opinion['id']}-{appearance['episode_id']}",
                'title': opinion['title'],
                'description': opinion['description'],
                'category': opinion['category_id'],
                'episode_id': appearance['episode_id'],
                'episode_title': appearance['episode_title'],
                'episode_date': appearance['date'],
                'content': appearance['content'],
                'speakers': []
            }
            
            # Add speakers
            for speaker in appearance.get('speakers', []):
                raw_opinion['speakers'].append({
                    'speaker_id': speaker['speaker_id'],
                    'speaker_name': speaker['speaker_name'],
                    'stance': speaker['stance'],
                    'reasoning': speaker.get('reasoning', ''),
                    'start_time': speaker.get('start_time', 0),
                    'end_time': speaker.get('end_time', 0)
                })
            
            # Add keywords
            if 'keywords' in opinion:
                raw_opinion['keywords'] = opinion['keywords']
            
            raw_opinions.append(raw_opinion)
    
    return raw_opinions

def categorize_opinions(raw_opinions):
    """Group raw opinions by category."""
    categorized_opinions = defaultdict(list)
    
    for opinion in raw_opinions:
        category = opinion.get('category', 'uncategorized')
        # Make a copy without the category field to match expected format
        opinion_copy = opinion.copy()
        categorized_opinions[category].append(opinion_copy)
    
    return dict(categorized_opinions)

def extract_relationships(opinions):
    """Extract relationship data from structured opinions."""
    relationships = []
    
    # Process related opinions
    for opinion in opinions:
        for related_id in opinion.get('related_opinions', []):
            relationships.append({
                'source_id': f"raw-{opinion['id']}-*",  # Wildcard for any episode
                'target_id': f"raw-{related_id}-*",     # Wildcard for any episode
                'relation_type': "RELATED",
                'notes': "Opinions are related according to existing data"
            })
        
        # Process contradictions
        if opinion.get('is_contradiction', False) and opinion.get('contradicts_opinion_id'):
            relationships.append({
                'source_id': f"raw-{opinion['id']}-*",  # Wildcard for any episode
                'target_id': f"raw-{opinion['contradicts_opinion_id']}-*",  # Wildcard for any episode
                'relation_type': "CONTRADICTION",
                'notes': opinion.get('contradiction_notes', "Opinions contradict each other")
            })
        
        # Process evolutions
        if opinion.get('evolution_chain'):
            for i in range(len(opinion['evolution_chain']) - 1):
                curr_id = opinion['evolution_chain'][i]
                next_id = opinion['evolution_chain'][i + 1]
                relationships.append({
                    'source_id': f"raw-{curr_id}-*",  # Wildcard for any episode
                    'target_id': f"raw-{next_id}-*",  # Wildcard for any episode
                    'relation_type': "EVOLUTION",
                    'notes': opinion.get('evolution_notes', "Opinion evolved over time")
                })
    
    return relationships

def save_json(data, file_path):
    """Save data to a JSON file."""
    ensure_dir_exists(file_path)
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=2)
    logger.info(f"Saved data to {file_path}")

def main():
    """Main function to convert and save opinions in intermediate formats."""
    logger.info("Starting conversion of opinions to intermediate formats")
    
    # 1. Load existing opinions
    logger.info(f"Loading opinions from {OPINIONS_FILE}")
    opinions = load_opinions()
    logger.info(f"Loaded {len(opinions)} opinions")
    
    # 2. Convert to raw opinions
    logger.info("Converting to raw opinions format")
    raw_opinions = convert_to_raw_opinions(opinions)
    logger.info(f"Created {len(raw_opinions)} raw opinions")
    
    # 3. Categorize opinions
    logger.info("Categorizing opinions")
    categorized_opinions = categorize_opinions(raw_opinions)
    categories_count = len(categorized_opinions)
    total_categorized = sum(len(ops) for ops in categorized_opinions.values())
    logger.info(f"Grouped opinions into {categories_count} categories with {total_categorized} total opinions")
    
    # 4. Extract relationships
    logger.info("Extracting relationship data")
    relationships = extract_relationships(opinions)
    logger.info(f"Extracted {len(relationships)} relationships")
    
    # 5. Save intermediate files
    logger.info("Saving intermediate files")
    save_json(raw_opinions, RAW_OPINIONS_FILE)
    save_json(categorized_opinions, CATEGORIZED_OPINIONS_FILE)
    save_json(relationships, RELATIONSHIPS_FILE)
    
    logger.info("Conversion completed successfully")
    return 0

if __name__ == "__main__":
    main() 