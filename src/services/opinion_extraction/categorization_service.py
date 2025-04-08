"""
Opinion Categorization Service

This module provides functionality for categorizing and standardizing opinion categories
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.models.opinions.category import Category
from src.repositories.category_repository import CategoryRepository
from src.services.llm_service import LLMService
from src.services.opinion_extraction.base_service import BaseOpinionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpinionCategorizationService(BaseOpinionService):
    """Service for categorizing and standardizing opinion categories."""
    
    def __init__(self, 
                 llm_service: Optional[LLMService] = None,
                 category_repository: Optional[CategoryRepository] = None,
                 min_confidence: float = 0.7,
                 checkpoint_service: Optional["CheckpointService"] = None):
        """
        Initialize the opinion categorization service.
        
        Args:
            llm_service: LLM service for categorization
            category_repository: Repository for category management
            min_confidence: Minimum confidence score for category assignment
            checkpoint_service: Checkpoint service for saving LLM responses
        """
        super().__init__(llm_service)
        self.category_repository = category_repository
        self.min_confidence = min_confidence
        self.checkpoint_service = checkpoint_service
        
        # Define standard categories if not provided
        self.standard_categories = [
            "Politics", "Economics", "Technology", "Society", "Philosophy", 
            "Science", "Business", "Culture", "Health", "Environment", 
            "Media", "Education", "Finance", "Sports", "Entertainment"
        ]
        
        # Create a lowercase map for easier matching
        self.standard_categories_lower = {cat.lower(): cat for cat in self.standard_categories}
        
        # Cache for category mappings to avoid redundant LLM calls
        self.category_mapping_cache = {}
    
    def categorize_opinions(self, raw_opinions: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Categorize raw opinions and group them by standard category.
        
        Args:
            raw_opinions: List of raw opinion dictionaries
            
        Returns:
            Dictionary mapping category names to lists of opinions
        """
        categorized_opinions = {}
        
        # Process each opinion to ensure proper categorization
        for opinion in raw_opinions:
            raw_category = opinion.get("category", "Uncategorized")
            
            # Skip if no category provided
            if not raw_category:
                raw_category = "Uncategorized"
            
            # Map to standard category
            standard_category = self._map_to_standard_category(raw_category)
            
            # Update the opinion with the standard category
            opinion["category"] = standard_category
            
            # Add to grouped opinions
            if standard_category not in categorized_opinions:
                categorized_opinions[standard_category] = []
            
            categorized_opinions[standard_category].append(opinion)
        
        logger.info(f"Categorized {len(raw_opinions)} opinions into {len(categorized_opinions)} categories")
        return categorized_opinions
    
    def _map_to_standard_category(self, raw_category: str) -> str:
        """
        Map a raw category name to a standard category.
        
        Args:
            raw_category: Raw category name
            
        Returns:
            Mapped standard category name
        """
        # Check if already a standard category (case-insensitive)
        raw_lower = raw_category.lower()
        
        # Check cache first
        if raw_lower in self.category_mapping_cache:
            return self.category_mapping_cache[raw_lower]
        
        # Direct match to standard category
        if raw_lower in self.standard_categories_lower:
            standard_category = self.standard_categories_lower[raw_lower]
            self.category_mapping_cache[raw_lower] = standard_category
            return standard_category
        
        # Try to match through the category repository if available
        if self.category_repository:
            existing_category = self.category_repository.get_category_by_name(raw_category)
            if existing_category:
                self.category_mapping_cache[raw_lower] = existing_category.name
                return existing_category.name
        
        # Use LLM to map to standard category if available
        if self.llm_service:
            try:
                mapped_category = self._map_category_with_llm(raw_category)
                if mapped_category:
                    self.category_mapping_cache[raw_lower] = mapped_category
                    return mapped_category
            except Exception as e:
                logger.error(f"Error mapping category with LLM: {e}")
        
        # If all else fails, use the original category
        self.category_mapping_cache[raw_lower] = raw_category
        return raw_category
    
    def _map_category_with_llm(self, raw_category: str) -> str:
        """
        Use LLM to map a non-standard category to a standard one.
        
        Args:
            raw_category: Raw category name
            
        Returns:
            Mapped standard category name or original if mapping fails
        """
        if not self.llm_service:
            return raw_category
        
        system_prompt = """
You are an expert at mapping specific categories to standardized categories.
Your task is to match the given category to the closest standard category from the provided list.
If there's no good match, you may suggest keeping the original category.
"""

        user_prompt = f"""
Given the category: "{raw_category}"

Map it to the most appropriate standard category from this list:
{", ".join(self.standard_categories)}

If none of the standard categories is appropriate, respond with "Keep original".
Provide only the mapped category name or "Keep original" without any other explanation.
"""

        try:
            # Call LLM for category mapping
            response = self.llm_service.call_simple(
                system_prompt=system_prompt,
                prompt=user_prompt
            )
            
            # Process the response
            if response and isinstance(response, str):
                response = response.strip()
                
                # Check if we should keep original
                if response.lower() == "keep original":
                    return raw_category
                
                # Check if response matches a standard category
                for standard_cat in self.standard_categories:
                    if response.lower() == standard_cat.lower():
                        return standard_cat
                
                # If response doesn't match exactly but is reasonable, use it
                if len(response) > 0:
                    return response
            
            # Default to original if response is invalid
            return raw_category
            
        except Exception as e:
            logger.error(f"Error in LLM category mapping: {e}")
            return raw_category
    
    def ensure_categories_exist(self, categories: List[str]) -> Dict[str, Category]:
        """
        Ensure all necessary categories exist in the repository.
        
        Args:
            categories: List of category names
            
        Returns:
            Dictionary mapping category names to Category objects
        """
        if not self.category_repository:
            logger.warning("Category repository not available, categories won't be persisted")
            return {}
        
        category_objects = {}
        
        for category_name in categories:
            try:
                # Find or create the category
                category = self.category_repository.find_or_create_category(category_name)
                category_objects[category_name] = category
            except Exception as e:
                logger.error(f"Error ensuring category exists: {category_name}, {e}")
        
        return category_objects

    def _categorize_opinions_batch(self, opinions: List[Dict]) -> Dict[str, List[Dict]]:
        """
        Categorize a batch of opinions using LLM.
        
        Args:
            opinions: List of opinion dictionaries
            
        Returns:
            Dictionary mapping category names to lists of opinions
        """
        if not self.llm_service:
            logger.warning("No LLM service available for categorization")
            return self._categorize_by_existing_category(opinions)
            
        # Generate a query ID based on a hash of the opinion IDs
        import hashlib
        opinion_ids = sorted([op.get('id', '') for op in opinions])
        opinions_hash = hashlib.md5(''.join(opinion_ids).encode('utf-8')).hexdigest()[:8]
        query_id = f"categorize_batch_{opinions_hash}"
        
        # Check if we already have a cached response
        if self.checkpoint_service and self.checkpoint_service.has_llm_response("categorization", query_id):
            cached_response = self.checkpoint_service.get_llm_response("categorization", query_id)
            if cached_response and "response" in cached_response:
                logger.info(f"Using cached LLM response for categorization of {len(opinions)} opinions")
                return cached_response["response"]
            
        # Get existing categories
        existing_categories = []
        if self.category_repository:
            existing_categories = [c.name for c in self.category_repository.get_all_categories()]
            
        # Format opinions for the LLM
        opinions_text = self._format_opinions_for_categorization(opinions)
        categories_text = "\n".join([f"- {cat}" for cat in existing_categories]) if existing_categories else "No existing categories"
            
        system_prompt = """
You are a categorization expert organizing opinions into topic-based categories.
Your task is to categorize each opinion into the most appropriate category based on its content.

You may use existing categories if they're appropriate, or create new ones if needed.
Focus on high-level topics rather than specific stances or details.
For example, "Immigration Policy" would be a good category, but "Pro-Immigration" or "Anti-Immigration" would not.

Output your categorization as a JSON dictionary where:
- Keys are category names (make them concise but descriptive)
- Values are arrays of opinion IDs that belong to that category

IMPORTANT:
- Each opinion must appear in exactly ONE category (the most appropriate one)
- Use existing categories when they fit well
- Create new categories when necessary, keeping them topic-focused
- Aim for 10-20 categories total, merging similar topics
"""

        user_prompt = f"""
Here are the existing categories:
{categories_text}

Please categorize these opinions:
{opinions_text}

Format your response as a JSON dictionary mapping category names to arrays of opinion IDs.
"""

        try:
            # Call LLM for categorization
            response = self.llm_service.call_simple(
                system_prompt=system_prompt,
                prompt=user_prompt
            )
            
            # Process LLM response
            import json
            categorized_opinions = {}
            
            # Check if the response is a string that contains a JSON object
            if isinstance(response, str):
                import re
                json_match = re.search(r'```(?:json)?(.*?)```', response, re.DOTALL)
                if json_match:
                    response = json_match.group(1).strip()
                try:
                    parsed_response = json.loads(response)
                    if isinstance(parsed_response, dict):
                        response = parsed_response
                except json.JSONDecodeError:
                    logger.error(f"Failed to parse LLM response: {response[:100]}...")
            
            # Process structured response
            if isinstance(response, dict):
                # Map opinions to categories based on LLM categorization
                for category_name, opinion_ids in response.items():
                    # Create a new category if it doesn't exist
                    if category_name not in categorized_opinions:
                        categorized_opinions[category_name] = []
                    
                    # Find matching opinions
                    for opinion_id in opinion_ids:
                        for opinion in opinions:
                            if opinion.get('id') == opinion_id:
                                # Add category to opinion
                                opinion_copy = opinion.copy()
                                opinion_copy['category'] = category_name
                                categorized_opinions[category_name].append(opinion_copy)
                                break
                                
                # Check for unprocessed opinions and add them to a default category
                all_processed_ids = set()
                for category, cat_opinions in categorized_opinions.items():
                    for opinion in cat_opinions:
                        all_processed_ids.add(opinion.get('id'))
                
                unprocessed_opinions = [op for op in opinions if op.get('id') not in all_processed_ids]
                if unprocessed_opinions:
                    if 'Uncategorized' not in categorized_opinions:
                        categorized_opinions['Uncategorized'] = []
                    
                    for opinion in unprocessed_opinions:
                        opinion_copy = opinion.copy()
                        opinion_copy['category'] = 'Uncategorized'
                        categorized_opinions['Uncategorized'].append(opinion_copy)
                
                # Save the result to checkpoint if available
                if self.checkpoint_service:
                    metadata = {
                        "num_opinions": len(opinions),
                        "num_categories": len(categorized_opinions),
                        "timestamp": datetime.now().isoformat()
                    }
                    self.checkpoint_service.save_llm_response(
                        stage="categorization",
                        query_id=query_id,
                        response=categorized_opinions,
                        metadata=metadata
                    )
                
                return categorized_opinions
            else:
                logger.error(f"Unexpected response format from LLM: {type(response)}")
                return self._categorize_by_existing_category(opinions)
                
        except Exception as e:
            logger.error(f"Error in opinion categorization: {e}")
            
            # Save the error to checkpoint if available
            if self.checkpoint_service:
                metadata = {
                    "num_opinions": len(opinions),
                    "error": str(e),
                    "timestamp": datetime.now().isoformat()
                }
                self.checkpoint_service.save_llm_response(
                    stage="categorization",
                    query_id=query_id,
                    response={"error": str(e)},
                    metadata=metadata
                )
                
            return self._categorize_by_existing_category(opinions) 