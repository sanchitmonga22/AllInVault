"""
Category Repository

This module provides functionality for managing opinion categories storage.
"""

import json
import os
import uuid
import logging
from typing import Dict, List, Optional, Set, Any
from datetime import datetime

from src.models.opinions.category import Category

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CategoryRepository:
    """Repository for category data with JSON file storage."""
    
    DEFAULT_CATEGORIES = [
        {"id": "politics", "name": "Politics", "description": "Political opinions and views"},
        {"id": "economics", "name": "Economics", "description": "Economic theories, markets, investments"},
        {"id": "technology", "name": "Technology", "description": "Technology trends, companies, products"},
        {"id": "science", "name": "Science", "description": "Scientific topics and discoveries"},
        {"id": "philosophy", "name": "Philosophy", "description": "Philosophical concepts and ethical discussions"},
        {"id": "society", "name": "Society", "description": "Social trends and issues"},
        {"id": "business", "name": "Business", "description": "Business strategies and operations"},
        {"id": "markets", "name": "Markets", "description": "Financial markets and trading"},
        {"id": "policy", "name": "Policy", "description": "Government policies and regulations"},
        {"id": "startups", "name": "Startups", "description": "Startup companies and entrepreneurship"},
        {"id": "health", "name": "Health", "description": "Health and healthcare topics"},
        {"id": "crypto", "name": "Cryptocurrency", "description": "Cryptocurrency and blockchain"},
    ]
    
    def __init__(self, categories_file_path: str = "data/json/categories.json"):
        """
        Initialize the category repository.
        
        Args:
            categories_file_path: Path to the categories JSON file
        """
        self.categories_file_path = categories_file_path
        self.categories: Dict[str, Category] = {}
        self._ensure_file_exists()
        self._load_categories()
        
        # Initialize with default categories if empty
        if not self.categories:
            self._initialize_default_categories()
    
    def _ensure_file_exists(self) -> None:
        """Ensure the categories file exists, creating it if necessary."""
        # Create directory if it doesn't exist
        os.makedirs(os.path.dirname(self.categories_file_path), exist_ok=True)
        
        # Create file if it doesn't exist
        if not os.path.exists(self.categories_file_path):
            with open(self.categories_file_path, 'w') as f:
                json.dump({"categories": []}, f)
    
    def _load_categories(self) -> None:
        """Load categories from the JSON file."""
        try:
            with open(self.categories_file_path, 'r') as f:
                data = json.load(f)
                
            categories_list = data.get("categories", [])
            self.categories = {}
            
            for category_data in categories_list:
                try:
                    category = Category.from_dict(category_data)
                    self.categories[category.id] = category
                except Exception as e:
                    logger.error(f"Error parsing category data: {e}")
                    
            logger.info(f"Loaded {len(self.categories)} categories from {self.categories_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to load categories file: {e}")
            self.categories = {}
    
    def _save_categories(self) -> None:
        """Save categories to the JSON file."""
        try:
            categories_list = [category.to_dict() for category in self.categories.values()]
            data = {"categories": categories_list}
            
            with open(self.categories_file_path, 'w') as f:
                json.dump(data, f, indent=2)
                
            logger.info(f"Saved {len(self.categories)} categories to {self.categories_file_path}")
            
        except Exception as e:
            logger.error(f"Failed to save categories file: {e}")
    
    def _initialize_default_categories(self) -> None:
        """Initialize the repository with default categories."""
        for category_data in self.DEFAULT_CATEGORIES:
            category = Category.from_dict(category_data)
            self.categories[category.id] = category
        
        self._save_categories()
        logger.info(f"Initialized repository with {len(self.categories)} default categories")
    
    def get_all_categories(self) -> List[Category]:
        """
        Get all categories.
        
        Returns:
            List of all categories
        """
        return list(self.categories.values())
    
    def get_category(self, category_id: str) -> Optional[Category]:
        """
        Get a category by ID.
        
        Args:
            category_id: ID of the category to get
            
        Returns:
            The category if found, or None
        """
        return self.categories.get(category_id)
    
    def get_category_by_name(self, name: str) -> Optional[Category]:
        """
        Get a category by name.
        
        Args:
            name: Name of the category
            
        Returns:
            The category if found, or None
        """
        for category in self.categories.values():
            if category.name.lower() == name.lower():
                return category
        return None
    
    def find_or_create_category(self, name: str) -> Category:
        """
        Find a category by name or create it if it doesn't exist.
        
        Args:
            name: Name of the category
            
        Returns:
            The found or created category
        """
        # First, check for exact match
        category = self.get_category_by_name(name)
        if category:
            return category
        
        # Then check for case-insensitive match
        lowercase_name = name.lower()
        for category in self.categories.values():
            if category.name.lower() == lowercase_name:
                return category
        
        # Create a new category
        new_id = self._generate_id_from_name(name)
        new_category = Category(
            id=new_id,
            name=name,
            description=f"Opinions related to {name}"
        )
        
        self.categories[new_id] = new_category
        self._save_categories()
        
        return new_category
    
    def _generate_id_from_name(self, name: str) -> str:
        """
        Generate a unique ID from a category name.
        
        Args:
            name: Category name
            
        Returns:
            Generated ID
        """
        # Create slug from name
        base_id = name.lower().replace(' ', '_').replace('-', '_')
        # Remove special characters
        base_id = ''.join(c for c in base_id if c.isalnum() or c == '_')
        
        # Check if this ID already exists
        if base_id not in self.categories:
            return base_id
        
        # If exists, add number suffix
        count = 1
        while f"{base_id}_{count}" in self.categories:
            count += 1
        
        return f"{base_id}_{count}"
    
    def save_category(self, category: Category) -> None:
        """
        Save a category to the repository.
        
        Args:
            category: The category to save
        """
        self.categories[category.id] = category
        self._save_categories()
    
    def save_categories(self, categories: List[Category]) -> None:
        """
        Save multiple categories to the repository.
        
        Args:
            categories: List of categories to save
        """
        for category in categories:
            self.categories[category.id] = category
        self._save_categories()
    
    def delete_category(self, category_id: str) -> bool:
        """
        Delete a category from the repository.
        
        Args:
            category_id: ID of the category to delete
            
        Returns:
            True if the category was deleted, False if not found
        """
        if category_id in self.categories:
            del self.categories[category_id]
            self._save_categories()
            return True
        return False 