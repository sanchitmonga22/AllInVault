"""
Opinion Extraction Service

This module provides the main service for extracting opinions from podcast transcripts
and tracking them over time using a multi-stage approach with LLM.
"""

import logging
import os
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion
from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository
from src.services.llm_service import LLMService

from src.services.opinion_extraction.raw_extraction_service import RawOpinionExtractionService
from src.services.opinion_extraction.categorization_service import OpinionCategorizationService
from src.services.opinion_extraction.relationship_service import OpinionRelationshipService
from src.services.opinion_extraction.merger_service import OpinionMergerService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OpinionExtractionService:
    """
    Main service for extracting and tracking opinions from podcast transcripts.
    
    This service orchestrates the multi-stage opinion extraction process:
    1. Extract raw opinions from each episode individually
    2. Categorize and group opinions by category
    3. Analyze relationships between opinions in the same category
    4. Merge related opinions and create final Opinion objects
    """
    
    def __init__(self, 
                 use_llm: bool = True,
                 llm_provider: str = "openai",
                 llm_api_key: Optional[str] = None,
                 llm_model: Optional[str] = None,
                 opinions_file_path: str = "data/json/opinions.json",
                 categories_file_path: str = "data/json/categories.json",
                 relation_batch_size: int = 20,
                 max_opinions_per_episode: int = 15,
                 similarity_threshold: float = 0.7):
        """
        Initialize the opinion extraction service.
        
        Args:
            use_llm: Whether to use LLM for opinion extraction
            llm_provider: LLM provider ('openai' or other supported providers)
            llm_api_key: API key for the LLM provider
            llm_model: Model name for the LLM provider
            opinions_file_path: Path to store opinions
            categories_file_path: Path to store categories
            relation_batch_size: Maximum number of opinions to compare in relationship analysis
            max_opinions_per_episode: Maximum number of opinions to extract per episode
            similarity_threshold: Threshold for opinion similarity to be considered related
        """
        # LLM integration
        self.use_llm = use_llm
        self.llm_service = None
        
        if use_llm:
            try:
                self.llm_service = LLMService(
                    provider=llm_provider,
                    api_key=llm_api_key,
                    model=llm_model or "gpt-4o"
                )
                logger.info(f"LLM integration enabled with provider: {llm_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                logger.warning("Opinion extraction will not work without LLM integration")
                self.use_llm = False
        
        # Initialize repositories
        self.opinion_repository = OpinionRepository(opinions_file_path)
        self.category_repository = CategoryRepository(categories_file_path)
        
        # Initialize component services
        self.raw_extraction_service = RawOpinionExtractionService(
            llm_service=self.llm_service,
            max_opinions_per_episode=max_opinions_per_episode
        )
        
        self.categorization_service = OpinionCategorizationService(
            llm_service=self.llm_service,
            category_repository=self.category_repository
        )
        
        self.relationship_service = OpinionRelationshipService(
            llm_service=self.llm_service,
            relation_batch_size=relation_batch_size,
            similarity_threshold=similarity_threshold
        )
        
        self.merger_service = OpinionMergerService(
            opinion_repository=self.opinion_repository,
            category_repository=self.category_repository
        )
        
        # Configuration
        self.relation_batch_size = relation_batch_size
        self.max_opinions_per_episode = max_opinions_per_episode
        self.similarity_threshold = similarity_threshold
    
    def extract_opinions(
        self, 
        episodes: List[PodcastEpisode], 
        transcripts_dir: str
    ) -> List[PodcastEpisode]:
        """
        Extract opinions from multiple episodes using the multi-stage approach.
        
        Args:
            episodes: List of episodes to process
            transcripts_dir: Directory containing transcript files
            
        Returns:
            List of updated episodes
        """
        if not self.use_llm or not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
            return episodes
        
        # Process episodes in chronological order
        sorted_episodes = sorted(
            episodes, 
            key=lambda ep: ep.published_at if ep.published_at else datetime.min,
            reverse=False
        )
        
        # Stage 1: Extract raw opinions from each episode
        all_raw_opinions = []
        updated_episodes = []
        
        for episode in sorted_episodes:
            # Skip episodes without transcripts
            if not episode.transcript_filename:
                logger.warning(f"Episode {episode.title} has no transcript")
                updated_episodes.append(episode)
                continue
            
            # Ensure we're using a TXT transcript
            if not episode.transcript_filename.lower().endswith('.txt'):
                logger.warning(f"Episode {episode.title} has non-TXT transcript: {episode.transcript_filename}")
                updated_episodes.append(episode)
                continue
                
            transcript_path = os.path.join(transcripts_dir, episode.transcript_filename)
            if not os.path.exists(transcript_path):
                logger.warning(f"Transcript file {transcript_path} not found")
                updated_episodes.append(episode)
                continue
            
            logger.info(f"Extracting raw opinions from episode: {episode.title}")
            
            # Extract raw opinions from this episode
            raw_opinions = self.raw_extraction_service.extract_raw_opinions(
                episode=episode,
                transcript_path=transcript_path
            )
            
            if raw_opinions:
                logger.info(f"Extracted {len(raw_opinions)} raw opinions from {episode.title}")
                all_raw_opinions.extend(raw_opinions)
                
                # Update the episode metadata
                if "opinions" not in episode.metadata:
                    episode.metadata["opinions"] = {}
                
                # Add opinion IDs to episode metadata
                for opinion in raw_opinions:
                    episode.metadata["opinions"][opinion["id"]] = {
                        "title": opinion["title"],
                        "category": opinion["category"]
                    }
            
            updated_episodes.append(episode)
        
        # Stage 2: Categorize and group opinions
        logger.info(f"Categorizing {len(all_raw_opinions)} raw opinions")
        categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
        
        # Ensure all categories exist in the repository
        self.categorization_service.ensure_categories_exist(list(categorized_opinions.keys()))
        
        # Stage 3: Analyze relationships between opinions in the same category
        logger.info("Analyzing relationships between opinions")
        relationship_data = self.relationship_service.analyze_relationships(categorized_opinions)
        
        # Stage 4: Process relationships and merge opinions
        logger.info("Processing relationships and merging opinions")
        final_opinions_data = self.merger_service.process_relationships(
            raw_opinions=all_raw_opinions,
            relationship_data=relationship_data
        )
        
        # Stage 5: Create structured Opinion objects
        logger.info("Creating final Opinion objects")
        final_opinions = self.merger_service.create_opinion_objects(final_opinions_data)
        
        # Stage 6: Save opinions to repository
        if final_opinions:
            logger.info(f"Saving {len(final_opinions)} opinions to repository")
            self.merger_service.save_opinions(final_opinions)
        
        return updated_episodes
    
    def extract_opinions_from_transcript(
        self, 
        episode: PodcastEpisode, 
        transcript_path: str
    ) -> List[Opinion]:
        """
        Extract opinions from a single transcript.
        This is a convenience method that processes a single episode
        and returns the extracted opinions directly.
        
        Args:
            episode: The podcast episode metadata
            transcript_path: Path to the transcript TXT file
            
        Returns:
            List of extracted opinions
        """
        if not self.use_llm or not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
            return []
        
        # Extract raw opinions
        raw_opinions = self.raw_extraction_service.extract_raw_opinions(
            episode=episode,
            transcript_path=transcript_path
        )
        
        if not raw_opinions:
            logger.warning(f"No raw opinions extracted from {episode.title}")
            return []
        
        # Categorize opinions
        categorized_opinions = self.categorization_service.categorize_opinions(raw_opinions)
        
        # Get existing opinions for context
        existing_opinions = self.opinion_repository.get_all_opinions()
        existing_opinions_data = []
        
        for op in existing_opinions:
            # Convert Opinion objects to dictionaries for comparison
            op_dict = {
                "id": op.id,
                "title": op.title,
                "description": op.description,
                "category": op.category_id,
                "related_opinions": op.related_opinions,
                "is_contradiction": op.is_contradiction,
                "contradicts_opinion_id": op.contradicts_opinion_id,
                "keywords": op.keywords
            }
            
            # Add appearances
            appearances = []
            for app in op.appearances:
                app_dict = {
                    "episode_id": app.episode_id,
                    "episode_title": app.episode_title,
                    "episode_date": app.date,
                    "content": app.content
                }
                
                # Add speakers to the appearance
                speakers = []
                for spk in app.speakers:
                    spk_dict = {
                        "speaker_id": spk.speaker_id,
                        "speaker_name": spk.speaker_name,
                        "stance": spk.stance,
                        "reasoning": spk.reasoning,
                        "start_time": spk.start_time,
                        "end_time": spk.end_time
                    }
                    speakers.append(spk_dict)
                
                app_dict["speakers"] = speakers
                appearances.append(app_dict)
            
            op_dict["appearances"] = appearances
            existing_opinions_data.append(op_dict)
        
        # Combine all opinions for relationship analysis
        all_opinions = existing_opinions_data.copy()
        for category_opinions in categorized_opinions.values():
            all_opinions.extend(category_opinions)
        
        # Group all opinions by category
        all_categorized_opinions = {}
        for opinion in all_opinions:
            category = opinion.get("category", "Uncategorized")
            if category not in all_categorized_opinions:
                all_categorized_opinions[category] = []
            all_categorized_opinions[category].append(opinion)
        
        # Analyze relationships
        relationship_data = self.relationship_service.analyze_relationships(all_categorized_opinions)
        
        # Process relationships and merge
        final_opinions_data = self.merger_service.process_relationships(
            raw_opinions=all_opinions,
            relationship_data=relationship_data
        )
        
        # Create Opinion objects and save
        final_opinions = self.merger_service.create_opinion_objects(final_opinions_data)
        
        if final_opinions:
            self.merger_service.save_opinions(final_opinions)
        
        # Filter to return only opinions from this episode
        episode_opinions = []
        for opinion in final_opinions:
            for appearance in opinion.appearances:
                if appearance.episode_id == episode.video_id:
                    episode_opinions.append(opinion)
                    break
        
        return episode_opinions 