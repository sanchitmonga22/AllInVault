"""
Opinion Merger Service

This module provides functionality for merging related opinions
and creating final Opinion objects.
"""

import logging
import uuid
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
        Process relationship data to merge and link opinions.
        
        Args:
            raw_opinions: List of raw opinion dictionaries
            relationship_data: List of relationship dictionaries
            
        Returns:
            List of finalized opinion dictionaries
        """
        # Create a map of opinion IDs to their objects
        opinion_map = {op['id']: op for op in raw_opinions}
        
        # Track merged opinions to avoid duplication
        merged_map = {}  # Maps original ID to merged ID
        
        # Process each relationship to establish links
        for relationship in relationship_data:
            try:
                source_id = relationship.get('source_id')
                target_id = relationship.get('target_id')
                relation_type = relationship.get('relation_type')
                notes = relationship.get('notes')
                
                # Skip if source or target don't exist
                if source_id not in opinion_map or target_id not in opinion_map:
                    continue
                
                # Handle merged opinions - redirect to their new IDs
                if source_id in merged_map:
                    source_id = merged_map[source_id]
                
                if target_id in merged_map:
                    target_id = merged_map[target_id]
                
                # Skip if source and target are already the same (already merged)
                if source_id == target_id:
                    continue
                
                # Get the source and target opinions
                source = opinion_map[source_id]
                target = opinion_map[target_id]
                
                if relation_type == RelationshipType.SAME_OPINION:
                    # Merge these opinions - they represent the same core opinion
                    merged_id = self._merge_opinions(source, target, opinion_map, merged_map)
                    
                    # Update relationship redirects
                    merged_map[source_id] = merged_id
                    merged_map[target_id] = merged_id
                    
                elif relation_type == RelationshipType.RELATED:
                    # Add as related opinions
                    if 'related_opinions' not in source:
                        source['related_opinions'] = []
                    if target_id not in source['related_opinions']:
                        source['related_opinions'].append(target_id)
                    
                    # Bidirectional relationship
                    if 'related_opinions' not in target:
                        target['related_opinions'] = []
                    if source_id not in target['related_opinions']:
                        target['related_opinions'].append(source_id)
                    
                elif relation_type == RelationshipType.EVOLUTION:
                    # Add to evolution chain
                    if 'evolution_chain' not in source:
                        source['evolution_chain'] = []
                    if target_id not in source['evolution_chain']:
                        source['evolution_chain'].append(target_id)
                    
                    # Add evolution notes
                    if notes:
                        if 'evolution_notes' not in source:
                            source['evolution_notes'] = notes
                        else:
                            source['evolution_notes'] += f"\n\n{notes}"
                    
                elif relation_type == RelationshipType.CONTRADICTION:
                    # Mark contradiction on source
                    source['is_contradiction'] = True
                    source['contradicts_opinion_id'] = target_id
                    if notes:
                        source['contradiction_notes'] = notes
                    
                    # Also mark contradiction on target (bidirectional)
                    target['is_contradiction'] = True
                    target['contradicts_opinion_id'] = source_id
                    if notes:
                        contradicting_note = f"Contradicted by: {notes}"
                        target['contradiction_notes'] = contradicting_note
            
            except Exception as e:
                logger.error(f"Error processing relationship: {e}")
                continue
        
        # Remove merged opinions from the final list
        final_opinions = []
        merged_ids = set(merged_map.values())
        
        for opinion_id, opinion in opinion_map.items():
            if opinion_id in merged_ids:
                final_opinions.append(opinion)
            elif opinion_id not in merged_map:
                final_opinions.append(opinion)
        
        logger.info(f"Processed {len(final_opinions)} final opinions after merging")
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