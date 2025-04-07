"""
Opinion Categorization Service

This module provides functionality for categorizing and standardizing opinion categories
"""

import logging
from typing import Dict, List, Optional, Any

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
                 standard_categories: List[str] = None):
        """
        Initialize the opinion categorization service.
        
        Args:
            llm_service: LLM service for category mapping
            category_repository: Repository for category storage
            standard_categories: List of standard category names
        """
        super().__init__(llm_service)
        self.category_repository = category_repository
        
        # Define standard categories if not provided
        self.standard_categories = standard_categories or [
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
            existing_category = self.category_repository.find_category_by_name(raw_category)
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