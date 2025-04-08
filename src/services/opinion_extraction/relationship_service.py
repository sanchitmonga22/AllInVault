"""
Opinion Relationship Service

This module provides functionality for analyzing relationships between opinions
across different episodes.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime

from src.services.llm_service import LLMService
from src.services.opinion_extraction.base_service import BaseOpinionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RelationshipType:
    """Enum-like class for relationship types."""
    SAME_OPINION = "same_opinion"  # Same core opinion
    RELATED = "related"  # Related but distinct opinions
    EVOLUTION = "evolution"  # Evolution of an opinion over time
    CONTRADICTION = "contradiction"  # Contradicts another opinion
    NO_RELATION = "no_relation"  # No relation between opinions

class OpinionRelationshipService(BaseOpinionService):
    """Service for analyzing relationships between opinions."""
    
    def __init__(self, 
                 llm_service: Optional[LLMService] = None,
                 relation_batch_size: int = 20,
                 similarity_threshold: float = 0.7):
        """
        Initialize the opinion relationship service.
        
        Args:
            llm_service: LLM service for relationship analysis
            relation_batch_size: Maximum number of opinions to analyze in a batch
            similarity_threshold: Threshold for considering opinions similar
        """
        super().__init__(llm_service)
        self.relation_batch_size = relation_batch_size
        self.similarity_threshold = similarity_threshold
    
    def analyze_relationships(self, categorized_opinions: Dict[str, List[Dict]]) -> List[Dict]:
        """
        Analyze relationships between opinions in the same category.
        
        Args:
            categorized_opinions: Dictionary mapping categories to opinion lists
            
        Returns:
            List of relationship data dictionaries
        """
        all_relationship_data = []
        
        # Process each category separately to reduce context size
        for category, opinions in categorized_opinions.items():
            logger.info(f"Analyzing relationships for {len(opinions)} opinions in category: {category}")
            
            # Sort opinions chronologically
            opinions.sort(key=lambda op: op.get("episode_date", datetime.min))
            
            # Process in batches to avoid context limits
            for i in range(0, len(opinions), self.relation_batch_size):
                batch = opinions[i:i+self.relation_batch_size]
                relationship_data = self._analyze_opinion_batch(batch, category)
                all_relationship_data.extend(relationship_data)
        
        logger.info(f"Found {len(all_relationship_data)} relationships across all categories")
        return all_relationship_data
    
    def _analyze_opinion_batch(self, opinions: List[Dict], category: str) -> List[Dict]:
        """
        Analyze relationships between opinions in the same batch.
        
        Args:
            opinions: List of opinions to analyze
            category: Category name
            
        Returns:
            List of relationship data dictionaries
        """
        if not self.llm_service:
            # Use basic heuristics if LLM not available
            return self._analyze_relationships_heuristic(opinions)
        
        try:
            # Prepare opinions for LLM
            formatted_opinions = self._format_opinions_for_relationship_analysis(opinions)
            
            # Call LLM for relationship analysis
            llm_results = self._call_llm_for_relationship_analysis(
                formatted_opinions=formatted_opinions,
                category=category
            )
            
            # Process LLM results
            processed_relationships = self._process_relationship_results(llm_results, opinions)
            return processed_relationships
            
        except Exception as e:
            logger.error(f"Error in relationship analysis: {e}")
            # Fall back to heuristic approach
            return self._analyze_relationships_heuristic(opinions)
    
    def _format_opinions_for_relationship_analysis(self, opinions: List[Dict]) -> str:
        """
        Format opinions for LLM relationship analysis.
        
        Args:
            opinions: List of opinions to format
            
        Returns:
            Formatted opinions text
        """
        formatted_text = ""
        
        for i, opinion in enumerate(opinions):
            # Format basic opinion metadata
            formatted_text += f"""
Opinion ID: {opinion.get('id', str(uuid.uuid4()))}
Title: {opinion.get('title', '')}
Description: {opinion.get('description', '')}
Episode: {opinion.get('episode_title', '')}
Date: {opinion.get('episode_date', '')}
"""
            
            # Format speaker information
            speakers_info = opinion.get('speakers', [])
            if speakers_info:
                formatted_text += "Speakers:\n"
                for speaker in speakers_info:
                    stance = speaker.get('stance', 'support')
                    formatted_text += f"- {speaker.get('speaker_name', '')} ({stance})\n"
            
            # Format content excerpt
            content = opinion.get('content', '')
            if content:
                formatted_text += f"Content excerpt: {content[:200]}...\n"
            
            # Add separator between opinions
            if i < len(opinions) - 1:
                formatted_text += "\n----------\n"
        
        return formatted_text
    
    def _call_llm_for_relationship_analysis(
        self,
        formatted_opinions: str,
        category: str
    ) -> Dict:
        """
        Call LLM to analyze relationships between opinions.
        
        Args:
            formatted_opinions: Formatted opinions text
            category: Category name
            
        Returns:
            Dictionary with relationship analysis results
        """
        if not self.llm_service:
            return {}
            
        system_prompt = """
You are analyzing a set of opinions from the same category to identify relationships.
Your task is to analyze each pair of opinions and determine their relationship type:

1. SAME_OPINION - These represent the exact same core opinion
2. RELATED - These opinions are related but distinct
3. EVOLUTION - The second opinion represents an evolution of the first over time
4. CONTRADICTION - These opinions contradict each other
5. NO_RELATION - These opinions are not related

Output your analysis as a JSON array of relationship objects with these fields:
- source_id: ID of the first opinion
- target_id: ID of the second opinion  
- relation_type: One of the relationship types above
- notes: Brief explanation of why this relationship exists (only for significant relationships)

IMPORTANT: 
- For SAME_OPINION, focus on opinions that represent the same core viewpoint, even if phrased differently
- For EVOLUTION, ensure the opinions are from different dates with the newer one building on the older one
- For CONTRADICTION, identify when opinions are in direct opposition or represent conflicting viewpoints
"""

        user_prompt = f"""
Given the following opinions from the category "{category}", identify relationships between them:

{formatted_opinions}

Analyze all opinion pairs and identify meaningful relationships.
Don't list pairs with NO_RELATION - only include relationships of significance.
Format your response as a JSON array of relationship objects.
"""

        try:
            # Call LLM service for relationship analysis
            response = self.llm_service.call_simple(
                system_prompt=system_prompt,
                prompt=user_prompt
            )
            
            # Parse the response
            import json
            if isinstance(response, str):
                try:
                    # Try to extract JSON if it's within a markdown code block
                    import re
                    json_match = re.search(r'```(?:json)?(.*?)```', response, re.DOTALL)
                    if json_match:
                        response = json_match.group(1).strip()
                    
                    # Parse the JSON
                    parsed_response = json.loads(response)
                    return parsed_response
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse LLM response as JSON: {response[:100]}...")
                    return {}
            
            return response if isinstance(response, dict) else {}
            
        except Exception as e:
            logger.error(f"Error calling LLM for relationship analysis: {e}")
            return {}
    
    def _process_relationship_results(
        self,
        llm_results: Any,
        opinions: List[Dict]
    ) -> List[Dict]:
        """
        Process relationship analysis results from LLM.
        
        Args:
            llm_results: Raw LLM analysis results
            opinions: List of opinions that were analyzed
            
        Returns:
            List of processed relationship dictionaries
        """
        processed_relationships = []
        
        # Create a map of opinion IDs for quick lookup
        opinion_map = {op.get('id', ''): op for op in opinions}
        
        # Check if llm_results is a list or needs to be extracted
        relationship_data = []
        
        if isinstance(llm_results, dict) and 'relationships' in llm_results:
            relationship_data = llm_results.get('relationships', [])
        elif isinstance(llm_results, list):
            relationship_data = llm_results
        
        for relationship in relationship_data:
            try:
                # Skip if not a dict
                if not isinstance(relationship, dict):
                    continue
                
                # Extract relationship data
                source_id = relationship.get('source_id')
                target_id = relationship.get('target_id')
                relation_type = relationship.get('relation_type')
                notes = relationship.get('notes')
                
                # Skip if missing required fields or invalid relationship type
                if not source_id or not target_id or not relation_type:
                    continue
                
                # Skip if source or target don't exist in our opinions
                if source_id not in opinion_map or target_id not in opinion_map:
                    continue
                
                # Skip NO_RELATION
                if relation_type.lower() == RelationshipType.NO_RELATION.lower():
                    continue
                
                # Add validation to ensure relationship type is valid
                valid_types = [
                    RelationshipType.SAME_OPINION,
                    RelationshipType.RELATED,
                    RelationshipType.EVOLUTION,
                    RelationshipType.CONTRADICTION
                ]
                
                if relation_type.lower() not in [t.lower() for t in valid_types]:
                    continue
                
                # Standard case for relation type
                for valid_type in valid_types:
                    if relation_type.lower() == valid_type.lower():
                        relation_type = valid_type
                
                # Get the source and target opinions
                source_opinion = opinion_map.get(source_id)
                target_opinion = opinion_map.get(target_id)
                
                # Add chronology verification for EVOLUTION type
                if relation_type == RelationshipType.EVOLUTION:
                    source_date = source_opinion.get('episode_date')
                    target_date = target_opinion.get('episode_date')
                    
                    # Ensure target (evolution) is newer than source
                    if source_date and target_date and source_date > target_date:
                        # Swap source and target for correct chronology
                        source_id, target_id = target_id, source_id
                        notes = f"[Reversed] {notes}" if notes else "[Chronology corrected]"
                
                # Create the processed relationship
                processed_relationship = {
                    'source_id': source_id,
                    'target_id': target_id,
                    'relation_type': relation_type,
                    'notes': notes
                }
                
                processed_relationships.append(processed_relationship)
                
            except Exception as e:
                logger.error(f"Error processing relationship: {e}")
                continue
        
        return processed_relationships
    
    def _analyze_relationships_heuristic(self, opinions: List[Dict]) -> List[Dict]:
        """
        Analyze relationships between opinions using basic heuristics (without LLM).
        
        Args:
            opinions: List of opinions to analyze
            
        Returns:
            List of relationship dictionaries
        """
        relationships = []
        
        # Sort opinions chronologically
        opinions.sort(key=lambda op: op.get('episode_date', datetime.min))
        
        # Compare each pair of opinions
        for i, opinion1 in enumerate(opinions):
            for j in range(i+1, len(opinions)):
                opinion2 = opinions[j]
                
                # Skip if they're from the same episode
                if opinion1.get('episode_id') == opinion2.get('episode_id'):
                    continue
                
                # Check for title and description similarity
                title_similar = self._is_similar_text(
                    opinion1.get('title', '').lower(), 
                    opinion2.get('title', '').lower(),
                    self.similarity_threshold
                )
                
                desc_similar = self._is_similar_text(
                    opinion1.get('description', '').lower(), 
                    opinion2.get('description', '').lower(),
                    self.similarity_threshold
                )
                
                # Determine relationship type based on similarity
                relation_type = RelationshipType.NO_RELATION
                notes = None
                
                if title_similar and desc_similar:
                    relation_type = RelationshipType.SAME_OPINION
                    notes = "Highly similar title and description"
                elif title_similar or desc_similar:
                    relation_type = RelationshipType.RELATED
                    notes = "Similar title or description"
                
                # Skip NO_RELATION
                if relation_type == RelationshipType.NO_RELATION:
                    continue
                
                # Create relationship
                relationship = {
                    'source_id': opinion1.get('id'),
                    'target_id': opinion2.get('id'),
                    'relation_type': relation_type,
                    'notes': notes
                }
                
                relationships.append(relationship)
        
        return relationships 