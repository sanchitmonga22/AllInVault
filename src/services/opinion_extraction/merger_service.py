"""
Opinion Merger Service

This module provides functionality for merging related opinions
and creating final Opinion objects.
"""

import logging
import uuid
import os
import json
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance
from src.models.opinions.category import Category
from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository
from src.services.opinion_extraction.base_service import BaseOpinionService
from src.services.opinion_extraction.relationship_service import RelationshipType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpinionMergerService(BaseOpinionService):
    """Service for merging related opinions and creating final Opinion objects."""
    
    def __init__(self, 
                 opinion_repository: Optional[OpinionRepository] = None,
                 category_repository: Optional[CategoryRepository] = None):
        """
        Initialize the opinion merger service.
        
        Args:
            opinion_repository: Repository for opinion storage
            category_repository: Repository for category storage
        """
        super().__init__(llm_service=None)
        self.opinion_repository = opinion_repository
        self.category_repository = category_repository
    
    def process_relationships(
        self,
        raw_opinions: List[Dict],
        relationship_data: List[Dict]
    ) -> List[Dict]:
        """
        Process relationships between opinions and merge related opinions.
        
        Args:
            raw_opinions: List of raw opinion dictionaries
            relationship_data: List of relationship dictionaries
            
        Returns:
            List of merged opinion dictionaries
        """
        if not raw_opinions:
            logger.warning("No raw opinions provided for processing")
            return []
            
        if not relationship_data:
            logger.warning("No relationship data provided for processing")
            # Still format the opinions for proper return
            return raw_opinions
            
        # Create deep copy to avoid modifying input
        raw_opinions_copy = [opinion.copy() for opinion in raw_opinions]
        
        opinion_map = {}
        id_variants_map = {}  # Maps all possible variants of IDs to canonical IDs
        merged_map = {}  # Maps original IDs to merged IDs
        
        # Map opinions by ID and create variant mappings
        for opinion in raw_opinions_copy:
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
                        id_variants_map[f"{opinion_num}_{episode_id}"] = canonical_id  # Standard format

                        # Add more logging for debugging
                        logger.debug(f"ID variants for {canonical_id}: {opinion_num}, {opinion_num}_{episode_id}_{episode_id}")
                        
        logger.info(f"Built opinion map with {len(opinion_map)} entries and {len(id_variants_map)} ID variants")
        if len(raw_opinions_copy) > 0:
            sample_opinion = raw_opinions_copy[0]
            logger.debug(f"Sample opinion ID format: {sample_opinion.get('id', 'N/A')}")
        logger.debug(f"Opinion map keys (sample): {list(opinion_map.keys())[:5]}")
        logger.debug(f"ID variants (sample): {list(id_variants_map.items())[:5]}")
        
        # Track statistics for reporting
        stats = {
            "total": len(relationship_data),
            "processed": 0,
            "skipped_missing_id": 0,
            "skipped_already_merged": 0,
            "applied_same_opinion": 0,
            "applied_related": 0,
            "applied_evolution": 0,
            "applied_contradiction": 0,
            "errors": 0
        }
        
        logger.info(f"Processing {len(relationship_data)} relationships for {len(raw_opinions_copy)} opinions")
        
        # Process each relationship to establish links
        for i, relationship in enumerate(relationship_data):
            try:
                source_id = relationship.get('source_id')
                target_id = relationship.get('target_id')
                original_source_id = relationship.get('original_source_id', source_id)
                original_target_id = relationship.get('original_target_id', target_id)
                relation_type = relationship.get('relation_type')
                notes = relationship.get('notes')
                source_episode_id = relationship.get('source_episode_id', '')
                target_episode_id = relationship.get('target_episode_id', '')
                
                # Log every relationship for better debugging
                logger.info(f"Processing relationship {i+1}/{len(relationship_data)}: {source_id} -> {target_id} ({relation_type})")
                logger.debug(f"  Original IDs: {original_source_id} -> {original_target_id}")
                logger.debug(f"  Episode IDs: {source_episode_id} -> {target_episode_id}")
                
                # Try to find the opinions using multiple ID formats
                source_opinion = None
                target_opinion = None
                
                # Try all possible variations for source opinion
                possible_source_ids = [
                    source_id,
                    f"{source_id}_{source_episode_id}",
                    f"{source_id}_{source_episode_id}_{source_episode_id}",
                    original_source_id,
                    f"{original_source_id}_{source_episode_id}",
                    f"{original_source_id}_{source_episode_id}_{source_episode_id}"
                ]
                
                # Add additional ID formats if provided
                source_id_formats = relationship.get('source_id_formats', [])
                if source_id_formats:
                    possible_source_ids.extend([f for f in source_id_formats if f and f not in possible_source_ids])
                    
                logger.debug(f"Trying source IDs: {possible_source_ids}")
                
                for possible_id in possible_source_ids:
                    # Skip empty IDs
                    if not possible_id:
                        continue
                        
                    # Direct match
                    if possible_id in opinion_map:
                        source_opinion = opinion_map[possible_id]
                        logger.debug(f"Found source opinion with direct ID: {possible_id}")
                        break
                    # Check variant map
                    elif possible_id in id_variants_map:
                        canonical_id = id_variants_map[possible_id]
                        source_opinion = opinion_map[canonical_id]
                        logger.debug(f"Found source opinion using variant mapping: {possible_id} -> {canonical_id}")
                        break
                
                # Try all possible variations for target opinion
                possible_target_ids = [
                    target_id,
                    f"{target_id}_{target_episode_id}",
                    f"{target_id}_{target_episode_id}_{target_episode_id}",
                    original_target_id,
                    f"{original_target_id}_{target_episode_id}",
                    f"{original_target_id}_{target_episode_id}_{target_episode_id}"
                ]
                
                # Add additional ID formats if provided
                target_id_formats = relationship.get('target_id_formats', [])
                if target_id_formats:
                    possible_target_ids.extend([f for f in target_id_formats if f and f not in possible_target_ids])
                    
                logger.debug(f"Trying target IDs: {possible_target_ids}")
                
                for possible_id in possible_target_ids:
                    # Skip empty IDs
                    if not possible_id:
                        continue
                        
                    # Direct match
                    if possible_id in opinion_map:
                        target_opinion = opinion_map[possible_id]
                        logger.debug(f"Found target opinion with direct ID: {possible_id}")
                        break
                    # Check variant map
                    elif possible_id in id_variants_map:
                        canonical_id = id_variants_map[possible_id]
                        target_opinion = opinion_map[canonical_id]
                        logger.debug(f"Found target opinion using variant mapping: {possible_id} -> {canonical_id}")
                        break
                
                # If still not found, try fuzzy matching as last resort
                if not source_opinion:
                    # Log detailed information about the missing ID
                    logger.warning(f"Source opinion ID not found - Details:")
                    logger.warning(f"  ID variants tried: {possible_source_ids}")
                    logger.warning(f"  Original relationship data: {relationship}")
                    
                    # Try fuzzy matching
                    for op_id in opinion_map.keys():
                        if source_id in op_id or (source_episode_id and source_episode_id in op_id):
                            source_opinion = opinion_map[op_id]
                            logger.info(f"Found fuzzy match for source ID {source_id} -> {op_id}")
                            break
                
                if not target_opinion:
                    # Log detailed information about the missing ID
                    logger.warning(f"Target opinion ID not found - Details:")
                    logger.warning(f"  ID variants tried: {possible_target_ids}")
                    logger.warning(f"  Original relationship data: {relationship}")
                    
                    # Try fuzzy matching
                    for op_id in opinion_map.keys():
                        if target_id in op_id or (target_episode_id and target_episode_id in op_id):
                            target_opinion = opinion_map[op_id]
                            logger.info(f"Found fuzzy match for target ID {target_id} -> {op_id}")
                            break
                
                # Skip if either opinion is still not found
                if not source_opinion:
                    logger.warning(f"Source opinion ID {source_id} not found in opinion map")
                    stats["skipped_missing_id"] += 1
                    continue
                
                if not target_opinion:
                    logger.warning(f"Target opinion ID {target_id} not found in opinion map")
                    stats["skipped_missing_id"] += 1
                    continue
                
                # Get the actual IDs from the opinions
                source_id = source_opinion['id']
                target_id = target_opinion['id']
                
                # Handle merged opinions - redirect to their new IDs
                if source_id in merged_map:
                    original_source_id = source_id
                    source_id = merged_map[source_id]
                    logger.debug(f"Redirecting source ID {original_source_id} to merged ID {source_id}")
                    source_opinion = opinion_map[source_id]
                
                if target_id in merged_map:
                    original_target_id = target_id
                    target_id = merged_map[target_id]
                    logger.debug(f"Redirecting target ID {original_target_id} to merged ID {target_id}")
                    target_opinion = opinion_map[target_id]
                
                # Skip if source and target are already the same (already merged)
                if source_id == target_id:
                    logger.debug(f"Skipping relationship as source and target are the same: {source_id}")
                    stats["skipped_already_merged"] += 1
                    continue
                
                # Process the relationship based on its type
                if relation_type == RelationshipType.SAME_OPINION or relation_type == "SAME_OPINION":
                    # Merge these opinions - they represent the same core opinion
                    merged_id = self._merge_opinions(source_opinion, target_opinion, opinion_map, merged_map)
                    
                    # Update relationship redirects
                    merged_map[source_id] = merged_id
                    merged_map[target_id] = merged_id
                    stats["applied_same_opinion"] += 1
                    
                    logger.info(f"Merged opinions: {source_id} + {target_id} -> {merged_id}")
                    
                elif relation_type == RelationshipType.RELATED or relation_type == "RELATED":
                    # Add as related opinions
                    if 'related_opinions' not in source_opinion:
                        source_opinion['related_opinions'] = []
                    if target_id not in source_opinion['related_opinions']:
                        source_opinion['related_opinions'].append(target_id)
                        logger.debug(f"Added {target_id} to related_opinions of {source_id}")
                    
                    # Bidirectional relationship
                    if 'related_opinions' not in target_opinion:
                        target_opinion['related_opinions'] = []
                    if source_id not in target_opinion['related_opinions']:
                        target_opinion['related_opinions'].append(source_id)
                        logger.debug(f"Added {source_id} to related_opinions of {target_id}")
                    
                    stats["applied_related"] += 1
                    logger.info(f"Related opinions: {source_id} <-> {target_id}")
                    
                elif relation_type == RelationshipType.EVOLUTION or relation_type == "EVOLUTION":
                    # Add to evolution chain
                    if 'evolution_chain' not in source_opinion:
                        source_opinion['evolution_chain'] = []
                    if target_id not in source_opinion['evolution_chain']:
                        source_opinion['evolution_chain'].append(target_id)
                        logger.debug(f"Added {target_id} to evolution_chain of {source_id}")
                    
                    # Add evolution notes
                    source_opinion['evolution_notes'] = notes or "Opinion has evolved over time"
                    
                    stats["applied_evolution"] += 1
                    logger.info(f"Evolution relationship: {source_id} -> {target_id}")
                    
                elif relation_type == RelationshipType.CONTRADICTION or relation_type == "CONTRADICTION":
                    # Mark contradiction
                    source_opinion['is_contradiction'] = True
                    source_opinion['contradicts_opinion_id'] = target_id
                    source_opinion['contradiction_notes'] = notes or "This opinion contradicts another"
                    
                    # Bidirectional contradiction
                    target_opinion['is_contradiction'] = True
                    target_opinion['contradicts_opinion_id'] = source_id
                    target_opinion['contradiction_notes'] = notes or "This opinion is contradicted by another"
                    
                    stats["applied_contradiction"] += 1
                    logger.info(f"Contradiction relationship: {source_id} <-> {target_id}")
                
                stats["processed"] += 1
                
            except Exception as e:
                logger.error(f"Error processing relationship: {e}")
                logger.exception("Detailed error:")
                stats["errors"] += 1
        
        # Remove merged opinions from the final list and ensure all opinions have necessary fields
        final_opinions = []
        merged_ids = set(merged_map.values())
        skipped_ids = set(merged_map.keys()) - merged_ids  # IDs that were merged into others
        
        # Log merged mapping for debugging
        if merged_map:
            logger.info(f"Merged opinion mapping (sample of {min(5, len(merged_map))} out of {len(merged_map)}):")
            count = 0
            for original_id, merged_id in merged_map.items():
                if count < 5:
                    logger.info(f"  {original_id} -> {merged_id}")
                    count += 1
        
        # Process opinions for the final list - important to initialize fields on ALL opinions
        for opinion_id, opinion in opinion_map.items():
            # Initialize relationship fields if not present
            if 'related_opinions' not in opinion:
                opinion['related_opinions'] = []
            if 'evolution_chain' not in opinion:
                opinion['evolution_chain'] = []
            if 'is_contradiction' not in opinion:
                opinion['is_contradiction'] = False
            if 'contradicts_opinion_id' not in opinion and opinion['is_contradiction']:
                opinion['contradicts_opinion_id'] = None
            
            # Add opinion to final list if it's either:
            # 1. A merged opinion (appears in merged_ids)
            # 2. Not merged into another opinion (doesn't appear in skipped_ids)
            if opinion_id in merged_ids or opinion_id not in skipped_ids:
                final_opinions.append(opinion)
        
        # Save stats to file for analysis
        try:
            stats_path = "data/opinions/opinion_merging_stats.json"
            os.makedirs(os.path.dirname(stats_path), exist_ok=True)
            with open(stats_path, 'w') as f:
                json.dump(stats, f, indent=2)
            logger.info(f"Saved merging statistics to {stats_path}")
        except Exception as e:
            logger.error(f"Failed to save merging statistics: {e}")
        
        # Save debug output files for analysis
        try:
            # Save a copy of the relationship data used
            debug_data_path = "data/opinions/debug_opinion_merging_data_output.json"
            with open(debug_data_path, 'w') as f:
                json.dump(raw_opinions_copy, f, indent=2)
            
            # Save a copy of the final opinions with relationships
            debug_objects_path = "data/opinions/debug_opinion_merging_objects_output.json"
            with open(debug_objects_path, 'w') as f:
                json.dump(final_opinions, f, indent=2)
                
            logger.info(f"Saved debug output to {debug_data_path} and {debug_objects_path}")
        except Exception as e:
            logger.error(f"Failed to save debug output: {e}")
                
        # Log the statistics
        logger.info(f"Relationship processing statistics: {stats}")
        
        # Verify relationship application
        self._verify_relationship_application(final_opinions)
        
        logger.info(f"Processed {len(final_opinions)} final opinions after merging (reduced from {len(raw_opinions_copy)})")
        logger.info(f"Opinions with related opinions: {sum(1 for op in final_opinions if op.get('related_opinions'))}")
        logger.info(f"Opinions with evolution chains: {sum(1 for op in final_opinions if op.get('evolution_chain'))}")
        logger.info(f"Opinions with contradictions: {sum(1 for op in final_opinions if op.get('is_contradiction'))}")
        
        # Log sample of final opinions with relationship data
        sample_size = min(3, len(final_opinions))
        if sample_size > 0:
            logger.info("Sample of final opinions with relationship data:")
            for i, op in enumerate(final_opinions[:sample_size]):
                logger.info(f"Opinion {i+1} (ID: {op.get('id')}):")
                logger.info(f"  Title: {op.get('title')}")
                logger.info(f"  Related opinions: {op.get('related_opinions', [])}")
                logger.info(f"  Evolution chain: {op.get('evolution_chain', [])}")
                logger.info(f"  Is contradiction: {op.get('is_contradiction', False)}")
                if op.get('is_contradiction', False):
                    logger.info(f"  Contradicts opinion: {op.get('contradicts_opinion_id')}")
        
        return final_opinions
    
    def _merge_opinions(
        self,
        source: Dict,
        target: Dict,
        opinion_map: Dict[str, Dict],
        merged_map: Dict[str, str]
    ) -> str:
        """
        Merge two opinions that represent the same core opinion.
        
        Args:
            source: Source opinion dictionary
            target: Target opinion dictionary
            opinion_map: Map of opinion IDs to opinion dictionaries
            merged_map: Map of original IDs to merged IDs
            
        Returns:
            ID of the merged opinion
        """
        # Determine which opinion to keep (prefer the one with more details)
        source_score = len(source.get('description', '')) + len(source.get('content', ''))
        target_score = len(target.get('description', '')) + len(target.get('content', ''))
        
        base_opinion, merged_opinion = (source, target) if source_score >= target_score else (target, source)
        
        # Create or update the merged opinion
        merged_id = base_opinion['id']
        
        # Mark the merged opinion for tracking
        base_opinion['merged_from'] = [base_opinion['id'], merged_opinion['id']]
        
        # Ensure the merged opinion has all necessary fields
        if 'related_opinions' not in base_opinion:
            base_opinion['related_opinions'] = []
        
        # Copy over related opinions
        if 'related_opinions' in merged_opinion:
            for related_id in merged_opinion['related_opinions']:
                if related_id not in base_opinion['related_opinions']:
                    base_opinion['related_opinions'].append(related_id)
        
        # Handle speakers/appearances across both opinions
        if 'appearances' not in base_opinion:
            base_opinion['appearances'] = []
        
        # Create an appearance from the merged opinion's data
        merged_appearance = {
            'episode_id': merged_opinion.get('episode_id'),
            'episode_title': merged_opinion.get('episode_title'),
            'episode_date': merged_opinion.get('episode_date'),
            'speakers': merged_opinion.get('speakers', []),
            'content': merged_opinion.get('content')
        }
        
        # Add appearance from base opinion if not already there
        base_appearance = {
            'episode_id': base_opinion.get('episode_id'),
            'episode_title': base_opinion.get('episode_title'),
            'episode_date': base_opinion.get('episode_date'),
            'speakers': base_opinion.get('speakers', []),
            'content': base_opinion.get('content')
        }
        
        # Create appearances list if it doesn't exist
        if 'appearances' not in base_opinion:
            base_opinion['appearances'] = []
        
        # Add appearances
        base_opinion['appearances'].append(base_appearance)
        base_opinion['appearances'].append(merged_appearance)
        
        # Add or merge evolution information
        if 'evolution_chain' in merged_opinion:
            if 'evolution_chain' not in base_opinion:
                base_opinion['evolution_chain'] = []
            
            for chain_id in merged_opinion.get('evolution_chain', []):
                if chain_id not in base_opinion['evolution_chain']:
                    base_opinion['evolution_chain'].append(chain_id)
        
        if 'evolution_notes' in merged_opinion and merged_opinion.get('evolution_notes'):
            if 'evolution_notes' not in base_opinion or not base_opinion.get('evolution_notes'):
                base_opinion['evolution_notes'] = merged_opinion.get('evolution_notes')
            else:
                base_opinion['evolution_notes'] += f"\n\n{merged_opinion.get('evolution_notes')}"
        
        # Add or merge contradiction information
        if merged_opinion.get('is_contradiction', False):
            base_opinion['is_contradiction'] = True
            
            if 'contradicts_opinion_id' in merged_opinion:
                base_opinion['contradicts_opinion_id'] = merged_opinion.get('contradicts_opinion_id')
            
            if 'contradiction_notes' in merged_opinion and merged_opinion.get('contradiction_notes'):
                if 'contradiction_notes' not in base_opinion or not base_opinion.get('contradiction_notes'):
                    base_opinion['contradiction_notes'] = merged_opinion.get('contradiction_notes')
                else:
                    base_opinion['contradiction_notes'] += f"\n\n{merged_opinion.get('contradiction_notes')}"
        
        # Merge keywords
        if 'keywords' not in base_opinion:
            base_opinion['keywords'] = []
        
        for keyword in merged_opinion.get('keywords', []):
            if keyword not in base_opinion['keywords']:
                base_opinion['keywords'].append(keyword)
        
        # Update confidence score
        base_opinion['confidence'] = max(
            base_opinion.get('confidence', 0.0),
            merged_opinion.get('confidence', 0.0)
        )
        
        # Add metadata about the merge
        if 'metadata' not in base_opinion:
            base_opinion['metadata'] = {}
        
        base_opinion['metadata']['merged_from'] = merged_opinion['id']
        base_opinion['metadata']['merge_date'] = datetime.now().isoformat()
        
        # Update the opinion map
        opinion_map[merged_id] = base_opinion
        
        return merged_id
    
    def create_opinion_objects(self, final_opinions: List[Dict]) -> List[Opinion]:
        """
        Create structured Opinion objects from the processed opinion data.
        
        Args:
            final_opinions: List of finalized opinion dictionaries
            
        Returns:
            List of Opinion objects
        """
        opinion_objects = []
        
        # Process each opinion into a structured Opinion object
        for opinion_data in final_opinions:
            try:
                # Create the Opinion object
                opinion = self._create_opinion_object(opinion_data)
                
                # Add it to the list
                if opinion:
                    opinion_objects.append(opinion)
                
            except Exception as e:
                logger.error(f"Error creating opinion object: {e}")
                continue
        
        logger.info(f"Created {len(opinion_objects)} structured Opinion objects")
        return opinion_objects
    
    def _create_opinion_object(self, opinion_data: Dict) -> Optional[Opinion]:
        """
        Create a single Opinion object from opinion data.
        
        Args:
            opinion_data: Opinion data dictionary
            
        Returns:
            Opinion object or None if creation fails
        """
        try:
            # Extract basic fields
            opinion_id = opinion_data.get('id', str(uuid.uuid4()))
            title = opinion_data.get('title', '')
            description = opinion_data.get('description', '')
            category_name = opinion_data.get('category', 'Uncategorized')
            
            # Get or create category
            category_id = 'uncategorized'
            if self.category_repository:
                try:
                    category = self.category_repository.find_or_create_category(category_name)
                    category_id = category.id
                except Exception as e:
                    logger.error(f"Error getting category: {e}")
            
            # Process appearances
            appearances = []
            
            # Process single-episode opinion format
            if 'appearances' not in opinion_data:
                appearance = self._create_appearance(opinion_data)
                if appearance:
                    appearances.append(appearance)
            else:
                # Process multi-episode opinion format
                for appearance_data in opinion_data.get('appearances', []):
                    appearance = self._create_appearance(appearance_data)
                    if appearance:
                        appearances.append(appearance)
            
            # Skip if no valid appearances
            if not appearances:
                logger.warning(f"Skipping opinion with no valid appearances: {title}")
                return None
            
            # Create the Opinion object
            opinion = Opinion(
                id=opinion_id,
                title=title,
                description=description,
                category_id=category_id,
                related_opinions=opinion_data.get('related_opinions', []),
                evolution_notes=opinion_data.get('evolution_notes'),
                evolution_chain=opinion_data.get('evolution_chain', []),
                is_contradiction=opinion_data.get('is_contradiction', False),
                contradicts_opinion_id=opinion_data.get('contradicts_opinion_id'),
                contradiction_notes=opinion_data.get('contradiction_notes'),
                keywords=opinion_data.get('keywords', []),
                confidence=opinion_data.get('confidence', 0.0),
                metadata=opinion_data.get('metadata', {})
            )
            
            # Add appearances to the opinion
            for appearance in appearances:
                opinion.appearances.append(appearance)
            
            return opinion
            
        except Exception as e:
            logger.error(f"Error in opinion object creation: {e}")
            return None
    
    def _create_appearance(self, data: Dict) -> Optional[OpinionAppearance]:
        """
        Create an OpinionAppearance object from appearance data.
        
        Args:
            data: Appearance data dictionary
            
        Returns:
            OpinionAppearance object or None if creation fails
        """
        try:
            # Extract appearance data
            episode_id = data.get('episode_id')
            episode_title = data.get('episode_title')
            
            # Skip if missing required fields
            if not episode_id or not episode_title:
                return None
            
            # Process date
            date = data.get('episode_date')
            if isinstance(date, str):
                try:
                    date = datetime.fromisoformat(date)
                except (ValueError, TypeError):
                    date = None
            
            # Process speakers
            speakers = []
            for speaker_data in data.get('speakers', []):
                speaker = self._create_speaker_stance(speaker_data)
                if speaker:
                    speakers.append(speaker)
            
            # Create the appearance
            return OpinionAppearance(
                episode_id=episode_id,
                episode_title=episode_title,
                date=date,
                speakers=speakers,
                content=data.get('content'),
                context_notes=data.get('context_notes'),
                evolution_notes_for_episode=data.get('evolution_notes_for_episode')
            )
            
        except Exception as e:
            logger.error(f"Error creating appearance: {e}")
            return None
    
    def _create_speaker_stance(self, data: Dict) -> Optional[SpeakerStance]:
        """
        Create a SpeakerStance object from speaker data.
        
        Args:
            data: Speaker data dictionary
            
        Returns:
            SpeakerStance object or None if creation fails
        """
        try:
            # Extract speaker data
            speaker_id = data.get('speaker_id')
            speaker_name = data.get('speaker_name')
            
            # Skip if missing required fields
            if not speaker_id:
                return None
            
            # Default name if not provided
            if not speaker_name:
                speaker_name = f"Speaker {speaker_id}"
            
            # Create the speaker stance
            return SpeakerStance(
                speaker_id=speaker_id,
                speaker_name=speaker_name,
                stance=data.get('stance', 'support'),
                reasoning=data.get('reasoning'),
                start_time=data.get('start_time'),
                end_time=data.get('end_time')
            )
            
        except Exception as e:
            logger.error(f"Error creating speaker stance: {e}")
            return None
    
    def save_opinions(self, opinions: List[Opinion]) -> bool:
        """
        Save opinions to the opinion repository.
        
        Args:
            opinions: List of Opinion objects to save
            
        Returns:
            True if saved successfully, False otherwise
        """
        if not self.opinion_repository:
            logger.warning("Opinion repository not available, opinions won't be persisted")
            return False
        
        try:
            # Save the opinions
            self.opinion_repository.save_opinions(opinions)
            logger.info(f"Saved {len(opinions)} opinions to repository")
            return True
        except Exception as e:
            logger.error(f"Error saving opinions: {e}")
            return False
    
    def _verify_relationship_application(self, opinions: List[Dict]) -> None:
        """
        Verify that relationships were correctly applied to opinions.
        This helps to identify issues with relationship processing.
        
        Args:
            opinions: List of processed opinion dictionaries
        """
        # Create map for quick lookups
        opinion_map = {op.get('id', ''): op for op in opinions}
        
        # Count various relationship types
        stats = {
            "total_opinions": len(opinions),
            "with_related_opinions": 0,
            "with_evolution_chain": 0, 
            "with_contradictions": 0,
            "with_merged_from": 0,
            "total_related_links": 0,
            "total_evolution_links": 0,
            "total_contradiction_links": 0,
            "bidirectional_related_count": 0,
            "bidirectional_contradiction_count": 0
        }
        
        # Examine each opinion for relationship data
        for opinion in opinions:
            opinion_id = opinion.get('id', '')
            
            # Check related opinions
            related_opinions = opinion.get('related_opinions', [])
            if related_opinions:
                stats["with_related_opinions"] += 1
                stats["total_related_links"] += len(related_opinions)
                
                # Check bidirectional relationships
                for related_id in related_opinions:
                    if related_id in opinion_map:
                        related_opinion = opinion_map[related_id]
                        if 'related_opinions' in related_opinion and opinion_id in related_opinion.get('related_opinions', []):
                            stats["bidirectional_related_count"] += 1
            
            # Check evolution chains
            evolution_chain = opinion.get('evolution_chain', [])
            if evolution_chain:
                stats["with_evolution_chain"] += 1
                stats["total_evolution_links"] += len(evolution_chain)
            
            # Check contradictions
            if opinion.get('is_contradiction', False) and opinion.get('contradicts_opinion_id'):
                stats["with_contradictions"] += 1
                stats["total_contradiction_links"] += 1
                
                # Check bidirectional contradictions
                contradicts_id = opinion.get('contradicts_opinion_id')
                if contradicts_id in opinion_map:
                    contradict_opinion = opinion_map[contradicts_id]
                    if (contradict_opinion.get('is_contradiction', False) and 
                        contradict_opinion.get('contradicts_opinion_id') == opinion_id):
                        stats["bidirectional_contradiction_count"] += 1
            
            # Check merged opinions
            if 'merged_from' in opinion:
                stats["with_merged_from"] += 1
        
        # Log the validation results
        logger.info(f"Relationship application verification: {stats}")
        
        # Check for potential issues
        if stats["with_related_opinions"] == 0 and stats["total_related_links"] == 0:
            logger.warning("No related opinions were applied during processing")
            
        if stats["with_evolution_chain"] == 0 and stats["total_evolution_links"] == 0:
            logger.warning("No evolution chains were created during processing")
            
        if stats["with_contradictions"] == 0 and stats["total_contradiction_links"] == 0:
            logger.warning("No contradictions were identified during processing")
            
        if stats["bidirectional_related_count"] < stats["total_related_links"] / 2:
            logger.warning("Some related opinion links may not be properly bidirectional")
            
        if stats["bidirectional_contradiction_count"] < stats["total_contradiction_links"] / 2:
            logger.warning("Some contradiction links may not be properly bidirectional") 