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
from src.services.opinion_extraction.checkpoint_service import CheckpointService

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
                 similarity_threshold: float = 0.7,
                 checkpoint_service: Optional[CheckpointService] = None):
        """
        Initialize the opinion relationship service.
        
        Args:
            llm_service: LLM service for relationship analysis
            relation_batch_size: Maximum number of opinions to analyze in a batch
            similarity_threshold: Threshold for considering opinions similar
            checkpoint_service: Checkpoint service for saving progress
        """
        super().__init__(llm_service)
        self.relation_batch_size = relation_batch_size
        self.similarity_threshold = similarity_threshold
        self.checkpoint_service = checkpoint_service
    
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
            
        Raises:
            RuntimeError: If LLM service is not available
        """
        if not self.llm_service:
            # Fail explicitly instead of falling back to heuristics
            raise RuntimeError("LLM service is required for relationship analysis but not available")
        
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
            # Fail explicitly instead of falling back to heuristics
            raise RuntimeError(f"Failed to analyze relationships using LLM: {e}")
    
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
            # Format basic opinion metadata with a fully qualified ID
            opinion_id = opinion.get('id', str(uuid.uuid4()))
            episode_id = opinion.get('episode_id', 'unknown')
            
            # Create an opinion reference that includes episode info
            formatted_text += f"""
Opinion ID: {opinion_id}
Episode ID: {episode_id}
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
            
        Raises:
            RuntimeError: If LLM service is not available or fails to process the request
        """
        if not self.llm_service:
            raise RuntimeError("LLM service is required for relationship analysis but not available")
            
        # Generate a query ID based on the category and a hash of the formatted opinions
        import hashlib
        query_hash = hashlib.md5(formatted_opinions.encode('utf-8')).hexdigest()[:8]
        query_id = f"relationship_{category}_{query_hash}"
        
        # Check if we already have a cached response
        if self.checkpoint_service and self.checkpoint_service.has_llm_response("relationship_analysis", query_id):
            cached_response = self.checkpoint_service.get_llm_response("relationship_analysis", query_id)
            if cached_response and "response" in cached_response:
                logger.info(f"Using cached LLM response for relationship analysis of category {category}")
                return cached_response["response"]
            
        system_prompt = """
You are analyzing a set of opinions from the same category to identify relationships.
Your task is to analyze each pair of opinions and determine their relationship type:

1. SAME_OPINION - These represent the exact same core opinion
2. RELATED - These opinions are related but distinct
3. EVOLUTION - The second opinion represents an evolution of the first over time
4. CONTRADICTION - These opinions contradict each other
5. NO_RELATION - These opinions are not related

Output your analysis as a JSON array of relationship objects with these fields:
- source_id: ID of the first opinion (use the EXACT Opinion ID from the input)
- target_id: ID of the second opinion (use the EXACT Opinion ID from the input)
- relation_type: One of the relationship types above
- notes: Brief explanation of why this relationship exists (only for significant relationships)

IMPORTANT: 
- Always use the COMPLETE Opinion ID exactly as provided in the input - DO NOT abbreviate, simplify, or modify the IDs in any way
- Pay attention to BOTH the Opinion ID and Episode ID in the input to ensure correct identification
- Opinion IDs are unique identifiers and must be preserved exactly as given
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
                    
                    # Save the response to checkpoint if available
                    if self.checkpoint_service:
                        metadata = {
                            "category": category,
                            "num_opinions": formatted_opinions.count("Opinion ID:"),
                            "timestamp": datetime.now().isoformat()
                        }
                        self.checkpoint_service.save_llm_response(
                            stage="relationship_analysis",
                            query_id=query_id,
                            response=parsed_response,
                            metadata=metadata
                        )
                    
                    return parsed_response
                except json.JSONDecodeError:
                    error_msg = f"Failed to parse LLM response as JSON: {response[:100]}..."
                    logger.error(error_msg)
                    raise RuntimeError(error_msg)
            
            if isinstance(response, dict):
                # Save the response to checkpoint if available
                if self.checkpoint_service:
                    metadata = {
                        "category": category,
                        "num_opinions": formatted_opinions.count("Opinion ID:"),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.checkpoint_service.save_llm_response(
                        stage="relationship_analysis",
                        query_id=query_id,
                        response=response,
                        metadata=metadata
                    )
                return response
            else:
                raise RuntimeError(f"Unexpected response type from LLM: {type(response)}")
            
        except Exception as e:
            error_msg = f"Error calling LLM for relationship analysis: {e}"
            logger.error(error_msg)
            
            # Save the error to checkpoint if available
            if self.checkpoint_service:
                metadata = {
                    "category": category,
                    "num_opinions": formatted_opinions.count("Opinion ID:"),
                    "timestamp": datetime.now().isoformat(),
                    "error": str(e)
                }
                self.checkpoint_service.save_llm_response(
                    stage="relationship_analysis",
                    query_id=query_id,
                    response={"error": str(e)},
                    metadata=metadata
                )
                
            raise RuntimeError(error_msg)
    
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
        relationships_data = []
        
        if isinstance(llm_results, dict) and "relationships" in llm_results:
            relationships_data = llm_results.get("relationships", [])
        elif isinstance(llm_results, list):
            relationships_data = llm_results
        
        # Process each relationship
        for rel in relationships_data:
            if not isinstance(rel, dict):
                logger.warning(f"Skipping invalid relationship format: {type(rel)}")
                continue
                
            source_id = rel.get("source_id")
            target_id = rel.get("target_id")
            relation_type = rel.get("relation_type")
            notes = rel.get("notes", "")
            
            # Skip invalid relationships
            if not source_id or not target_id or not relation_type:
                logger.warning(f"Skipping relationship with missing fields: {rel}")
                continue
                
            # Validate IDs are in our opinions list
            if source_id not in opinion_map:
                logger.warning(f"Source opinion ID not found: {source_id}")
                # Try to find it by numeric part if it's a UUID
                for op_id in opinion_map.keys():
                    if str(source_id) in str(op_id):
                        logger.info(f"Found approximate match for {source_id} -> {op_id}")
                        source_id = op_id
                        break
                else:
                    continue
                    
            if target_id not in opinion_map:
                logger.warning(f"Target opinion ID not found: {target_id}")
                # Try to find it by numeric part if it's a UUID
                for op_id in opinion_map.keys():
                    if str(target_id) in str(op_id):
                        logger.info(f"Found approximate match for {target_id} -> {op_id}")
                        target_id = op_id
                        break
                else:
                    continue
            
            # Ensure the relation type is valid
            if not hasattr(RelationshipType, relation_type.upper().replace("-", "_")):
                logger.warning(f"Invalid relationship type: {relation_type}")
                relation_type = RelationshipType.RELATED
            
            # Get source and target episode information
            source_episode_id = opinion_map[source_id].get("episode_id", "")
            source_episode_title = opinion_map[source_id].get("episode_title", "")
            target_episode_id = opinion_map[target_id].get("episode_id", "")
            target_episode_title = opinion_map[target_id].get("episode_title", "")
            
            # Create composite IDs that include episode information
            composite_source_id = f"{source_id}_{source_episode_id}"
            composite_target_id = f"{target_id}_{target_episode_id}"
            
            # Create the processed relationship
            processed_relationship = {
                "source_id": composite_source_id,
                "target_id": composite_target_id,
                "original_source_id": source_id,
                "original_target_id": target_id,
                "relation_type": relation_type,
                "notes": notes,
                "source_episode_id": source_episode_id,
                "source_episode_title": source_episode_title,
                "target_episode_id": target_episode_id,
                "target_episode_title": target_episode_title,
                "category": opinion_map[source_id].get("category", "")
            }
            
            processed_relationships.append(processed_relationship)
        
        logger.info(f"Processed {len(processed_relationships)} relationships from LLM response")
        return processed_relationships
    
    def get_relationships_from_data(self, relationship_data: List[Dict]) -> List[Dict]:
        """
        Get processed relationships from relationship data.
        
        Args:
            relationship_data: List of relationship dictionaries
            
        Returns:
            List of relationship dictionaries with original IDs for compatibility
        """
        relationships = []
        
        for rel in relationship_data:
            if not isinstance(rel, dict):
                continue
                
            # Extract the original opinion IDs if available, otherwise use the composite IDs
            source_id = rel.get("original_source_id", rel.get("source_id", ""))
            target_id = rel.get("original_target_id", rel.get("target_id", ""))
            
            # If we're using composite IDs, extract just the opinion part
            if "_" in source_id and "original_source_id" not in rel:
                source_id = source_id.split("_")[0]
            if "_" in target_id and "original_target_id" not in rel:
                target_id = target_id.split("_")[0]
                
            relationship = {
                "source_id": source_id,
                "target_id": target_id,
                "relation_type": rel.get("relation_type", RelationshipType.RELATED),
                "notes": rel.get("notes", ""),
                "source_episode_id": rel.get("source_episode_id", ""),
                "target_episode_id": rel.get("target_episode_id", "")
            }
            
            relationships.append(relationship)
            
        return relationships
    
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
                
                # Extract source and target information
                source_id = opinion1.get('id')
                source_episode_id = opinion1.get('episode_id', '')
                source_episode_title = opinion1.get('episode_title', '')
                
                target_id = opinion2.get('id')
                target_episode_id = opinion2.get('episode_id', '')
                target_episode_title = opinion2.get('episode_title', '')
                
                # Create composite IDs
                composite_source_id = f"{source_id}_{source_episode_id}"
                composite_target_id = f"{target_id}_{target_episode_id}"
                
                # Create relationship
                relationship = {
                    'source_id': composite_source_id,
                    'target_id': composite_target_id,
                    'original_source_id': source_id,
                    'original_target_id': target_id,
                    'relation_type': relation_type,
                    'notes': notes,
                    'source_episode_id': source_episode_id,
                    'source_episode_title': source_episode_title,
                    'target_episode_id': target_episode_id,
                    'target_episode_title': target_episode_title,
                    'category': opinion1.get('category', '')
                }
                
                relationships.append(relationship)
        
        return relationships 