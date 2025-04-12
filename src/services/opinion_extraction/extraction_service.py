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
from src.services.opinion_extraction.evolution_service import EvolutionDetectionService
from src.services.opinion_extraction.speaker_tracking_service import SpeakerTrackingService
from src.services.opinion_extraction.checkpoint_service import CheckpointService

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
    5. Build evolution chains from relationships
    6. Track speaker stances and journeys across episodes
    """
    
    def __init__(self, 
                 use_llm: bool = True,
                 llm_provider: str = "deepseek",
                 llm_api_key: Optional[str] = None,
                 llm_model: Optional[str] = None,
                 opinions_file_path: str = "data/json/opinions.json",
                 categories_file_path: str = "data/json/categories.json",
                 checkpoint_path: str = CheckpointService.DEFAULT_CHECKPOINT_PATH,
                 raw_opinions_path: str = CheckpointService.DEFAULT_RAW_OPINIONS_PATH,
                 relation_batch_size: int = 20,
                 max_opinions_per_episode: int = 15,
                 similarity_threshold: float = 0.7):
        """
        Initialize the opinion extraction service.
        
        Args:
            use_llm: Whether to use LLM for opinion extraction
            llm_provider: LLM provider ('openai' or 'deepseek')
            llm_api_key: API key for the LLM provider
            llm_model: Model name for the LLM provider
            opinions_file_path: Path to store opinions
            categories_file_path: Path to store categories
            checkpoint_path: Path to store checkpoints
            raw_opinions_path: Path to store raw opinions
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
                    model=llm_model or "deepseek-chat"
                )
                logger.info(f"LLM integration enabled with provider: {llm_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                logger.warning("Opinion extraction will not work without LLM integration")
                self.use_llm = False
        
        # Initialize repositories
        self.opinion_repository = OpinionRepository(opinions_file_path)
        self.category_repository = CategoryRepository(categories_file_path)
        
        # Initialize checkpoint service
        self.checkpoint_service = CheckpointService(
            checkpoint_path=checkpoint_path,
            raw_opinions_path=raw_opinions_path
        )
        
        # Initialize component services
        self.raw_extraction_service = RawOpinionExtractionService(
            llm_service=self.llm_service,
            max_opinions_per_episode=max_opinions_per_episode
        )
        
        self.categorization_service = OpinionCategorizationService(
            llm_service=self.llm_service,
            category_repository=self.category_repository,
            min_confidence=0.7,
            checkpoint_service=self.checkpoint_service
        )
        
        self.relationship_service = OpinionRelationshipService(
            llm_service=self.llm_service,
            relation_batch_size=relation_batch_size,
            similarity_threshold=similarity_threshold,
            checkpoint_service=self.checkpoint_service
        )
        
        self.merger_service = OpinionMergerService(
            opinion_repository=self.opinion_repository,
            category_repository=self.category_repository
        )

        # Initialize evolution and speaker tracking services
        self.evolution_service = EvolutionDetectionService(
            opinion_repository=self.opinion_repository
        )
        
        self.speaker_tracking_service = SpeakerTrackingService(
            opinion_repository=self.opinion_repository
        )
        
        # Configuration
        self.relation_batch_size = relation_batch_size
        self.max_opinions_per_episode = max_opinions_per_episode
        self.similarity_threshold = similarity_threshold
    
    def extract_opinions(
        self, 
        episodes: List[PodcastEpisode], 
        transcripts_dir: str,
        resume_from_checkpoint: bool = True,
        save_checkpoints: bool = True,
        start_stage: str = "raw_extraction"
    ) -> List[PodcastEpisode]:
        """
        Extract opinions from multiple episodes using the multi-stage approach.
        
        Args:
            episodes: List of episodes to process
            transcripts_dir: Directory containing transcript files
            resume_from_checkpoint: Whether to resume from the last checkpoint
            save_checkpoints: Whether to save checkpoints during processing
            start_stage: Stage to start processing from
            
        Returns:
            List of updated episodes
        """
        if not self.use_llm or not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
            return episodes

        # Convert start_stage to int for comparison
        start_stage_int = {
            "raw_extraction": 0,
            "categorization": 1,
            "relationship_analysis": 2,
            "opinion_merging": 3,
            "evolution_detection": 4,
            "speaker_tracking": 5
        }.get(start_stage, 0)
        
        # Process episodes in chronological order
        sorted_episodes = sorted(
            episodes, 
            key=lambda ep: ep.published_at if ep.published_at else datetime.min,
            reverse=False
        )
        
        # Get checkpoint data if resuming
        all_raw_opinions = []
        if resume_from_checkpoint:
            # Load previously processed episodes and raw opinions
            processed_episode_ids = self.checkpoint_service.get_processed_episodes()
            logger.info(f"Resuming from checkpoint with {len(processed_episode_ids)} processed episodes")
            
            # Load raw opinions from previous run
            all_raw_opinions = self.checkpoint_service.load_raw_opinions() or []
            if all_raw_opinions:
                logger.info(f"Loaded {len(all_raw_opinions)} raw opinions from checkpoint")
            
            # Skip any episodes that were already processed
            sorted_episodes = [ep for ep in sorted_episodes if ep.video_id not in processed_episode_ids]
            
            # Check if we have already completed all stages
            last_completed_stage = self.checkpoint_service.get_episode_stage(self.checkpoint_service.checkpoint_data.get("last_processed_episode"))
            if last_completed_stage == "speaker_tracking" and not sorted_episodes:
                logger.info("All episodes have been processed and all stages are complete")
                # Return original episodes since they already have opinion metadata
                return episodes
        
        # Skip raw extraction if starting from a later stage
        if start_stage_int <= 0:
            # Stage 1: Extract raw opinions from each episode
            updated_episodes = []
            for episode in sorted_episodes:
                # Skip episodes without transcripts
                if not episode.transcript_filename:
                    logger.warning(f"Episode {episode.title} has no transcript")
                    updated_episodes.append(episode)
                    continue
                
                # Check if episode has already been processed
                if resume_from_checkpoint and self.checkpoint_service.is_episode_processed(episode.video_id):
                    logger.info(f"Skipping already processed episode: {episode.title}")
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
                    
                    # Mark episode as processed in checkpoint
                    if save_checkpoints:
                        self.checkpoint_service.mark_episode_complete(episode.video_id)
                        # Save raw opinions to checkpoint
                        self.checkpoint_service.save_raw_opinions(all_raw_opinions)
                        
                        # Save stage stats for raw extraction
                        stage_stats = self._generate_stage_stats(
                            stage="raw_extraction", 
                            all_raw_opinions=all_raw_opinions
                        )
                        self.checkpoint_service.update_extraction_stats({"raw_extraction": stage_stats})
                
                updated_episodes.append(episode)
        else:
            updated_episodes = sorted_episodes
            # Load existing raw opinions since we're skipping extraction
            all_raw_opinions = self.checkpoint_service.load_raw_opinions() or []
            if not all_raw_opinions:
                logger.error("No raw opinions found in checkpoint, cannot continue without raw opinions")
                return episodes
            logger.info(f"Loaded {len(all_raw_opinions)} existing raw opinions from checkpoint")
        
        # Skip further processing if there are no raw opinions
        if not all_raw_opinions:
            logger.warning("No raw opinions available, skipping further processing")
            return episodes
            
        # Mark raw extraction stage as complete if we loaded existing opinions
        if save_checkpoints and start_stage_int > 0:
            self.checkpoint_service.mark_episode_stage_complete(
                episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                stage="raw_extraction"
            )
        
        # Stage 2: Categorize and group opinions
        if start_stage_int <= 1:
            logger.info(f"Categorizing {len(all_raw_opinions)} raw opinions")
            categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
            
            # Ensure all categories exist in the repository
            self.categorization_service.ensure_categories_exist(list(categorized_opinions.keys()))
            
            # Save stage stats
            if save_checkpoints:
                stage_stats = self._generate_stage_stats(
                    stage="categorization", 
                    all_raw_opinions=all_raw_opinions,
                    categorized_opinions=categorized_opinions
                )
                self.checkpoint_service.update_extraction_stats({"categorization": stage_stats})
            
            # Mark categorization stage as complete
            if save_checkpoints:
                self.checkpoint_service.mark_episode_stage_complete(
                    episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                    stage="categorization"
                )
        
        # Stage 3: Analyze relationships between opinions
        if start_stage_int <= 2:
            logger.info("Analyzing relationships between opinions")
            categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
            relationship_data = self.relationship_service.analyze_relationships(categorized_opinions)
            
            # Save stage stats
            if save_checkpoints:
                stage_stats = self._generate_stage_stats(
                    stage="relationship_analysis", 
                    all_raw_opinions=all_raw_opinions,
                    categorized_opinions=categorized_opinions,
                    relationship_data=relationship_data
                )
                self.checkpoint_service.update_extraction_stats({"relationship_analysis": stage_stats})
            
            # Mark relationship analysis stage as complete
            if save_checkpoints:
                self.checkpoint_service.mark_episode_stage_complete(
                    episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                    stage="relationship_analysis"
                )
        
        # Stage 4: Process relationships and merge opinions
        if start_stage_int <= 3:
            logger.info("Processing relationships and merging opinions")
            categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
            relationship_data = self.relationship_service.analyze_relationships(categorized_opinions)
            final_opinions_data = self.merger_service.process_relationships(
                raw_opinions=all_raw_opinions,
                relationship_data=relationship_data
            )
            
            # Create structured Opinion objects
            logger.info("Creating final Opinion objects")
            final_opinions = self.merger_service.create_opinion_objects(final_opinions_data)
            
            # Save stage stats
            if save_checkpoints:
                stage_stats = self._generate_stage_stats(
                    stage="opinion_merging", 
                    all_raw_opinions=all_raw_opinions,
                    categorized_opinions=categorized_opinions,
                    relationship_data=relationship_data,
                    final_opinions=final_opinions
                )
                self.checkpoint_service.update_extraction_stats({"opinion_merging": stage_stats})
            
            # Mark merging stage as complete
            if save_checkpoints:
                self.checkpoint_service.mark_episode_stage_complete(
                    episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                    stage="opinion_merging"
                )
        
        # Stage 5: Evolution detection
        if start_stage_int <= 4:
            logger.info("Analyzing opinion evolution")
            categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
            relationship_data = self.relationship_service.analyze_relationships(categorized_opinions)
            final_opinions_data = self.merger_service.process_relationships(
                raw_opinions=all_raw_opinions,
                relationship_data=relationship_data
            )
            final_opinions = self.merger_service.create_opinion_objects(final_opinions_data)
            
            # Get relationships for evolution analysis
            relationships = self.relationship_service.get_relationships_from_data(relationship_data)
            
            # Analyze evolution
            evolution_data = self.evolution_service.analyze_opinion_evolution(
                opinions=final_opinions,
                relationships=relationships
            )
            
            # Save stage stats
            if save_checkpoints:
                stage_stats = self._generate_stage_stats(
                    stage="evolution_detection", 
                    all_raw_opinions=all_raw_opinions,
                    categorized_opinions=categorized_opinions,
                    relationship_data=relationship_data,
                    final_opinions=final_opinions,
                    evolution_data=evolution_data
                )
                self.checkpoint_service.update_extraction_stats({"evolution_detection": stage_stats})
            
            # Mark evolution detection stage as complete
            if save_checkpoints:
                self.checkpoint_service.mark_episode_stage_complete(
                    episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                    stage="evolution_detection"
                )
        
        # Stage 6: Speaker tracking
        if start_stage_int <= 5:
            logger.info("Tracking speaker behavior")
            categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
            relationship_data = self.relationship_service.analyze_relationships(categorized_opinions)
            final_opinions_data = self.merger_service.process_relationships(
                raw_opinions=all_raw_opinions,
                relationship_data=relationship_data
            )
            final_opinions = self.merger_service.create_opinion_objects(final_opinions_data)
            
            # Track speaker behavior
            speaker_data = self.speaker_tracking_service.analyze_speaker_behavior(
                opinions=final_opinions
            )
            
            # Get relationships for evolution analysis
            relationships = self.relationship_service.get_relationships_from_data(relationship_data)
            
            # Analyze evolution for complete data
            evolution_data = self.evolution_service.analyze_opinion_evolution(
                opinions=final_opinions,
                relationships=relationships
            )
            
            # Save stage stats
            if save_checkpoints:
                stage_stats = self._generate_stage_stats(
                    stage="speaker_tracking", 
                    all_raw_opinions=all_raw_opinions,
                    categorized_opinions=categorized_opinions,
                    relationship_data=relationship_data,
                    final_opinions=final_opinions,
                    evolution_data=evolution_data
                )
                # Add speaker-specific stats
                stage_stats.update({
                    "total_speakers_tracked": len(speaker_data.get("speaker_journeys", {})),
                    "speaker_names": list(speaker_data.get("speaker_journeys", {}).keys()),
                    "total_stance_changes": sum(len(journey.get("stance_changes", [])) 
                                              for journey in speaker_data.get("speaker_journeys", {}).values())
                })
                self.checkpoint_service.update_extraction_stats({"speaker_tracking": stage_stats})
            
            # Mark speaker tracking stage as complete
            if save_checkpoints:
                self.checkpoint_service.mark_episode_stage_complete(
                    episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                    stage="speaker_tracking"
                )
        
        # Save final results
        categorized_opinions = self.categorization_service.categorize_opinions(all_raw_opinions)
        relationship_data = self.relationship_service.analyze_relationships(categorized_opinions)
        final_opinions_data = self.merger_service.process_relationships(
            raw_opinions=all_raw_opinions,
            relationship_data=relationship_data
        )
        final_opinions = self.merger_service.create_opinion_objects(final_opinions_data)
        
        if final_opinions:
            logger.info(f"Saving {len(final_opinions)} opinions to repository")
            self.merger_service.save_opinions(final_opinions)
            
            # Get relationships for evolution analysis
            relationships = self.relationship_service.get_relationships_from_data(relationship_data)
            
            # Analyze evolution and save evolution data
            evolution_data = self.evolution_service.analyze_opinion_evolution(
                opinions=final_opinions, 
                relationships=relationships
            )
            
            # Save evolution chains and update opinions with evolution data
            self.evolution_service.save_evolution_data(
                opinions=final_opinions,
                evolution_chains=evolution_data.get('evolution_chains', []),
                speaker_journeys=evolution_data.get('speaker_journeys', [])
            )
            
            # Update extraction stats with detailed metrics
            detailed_stats = {
                "total_episodes": len(self.checkpoint_service.get_processed_episodes()),
                "total_opinions": len(final_opinions),
                "total_categories": len(categorized_opinions),
                "total_raw_opinions": len(all_raw_opinions),
                "total_relationships": len(relationship_data),
                "total_evolution_chains": len(evolution_data.get('evolution_chains', [])),
                "total_speaker_journeys": len(evolution_data.get('speaker_journeys', [])),
                "categories": list(categorized_opinions.keys()),
                "opinions_per_category": {cat: len(opinions) for cat, opinions in categorized_opinions.items()},
                "speakers": len(set([speaker['speaker_name'] for opinion in all_raw_opinions for speaker in opinion.get('speakers', [])])),
                "processed_episodes": self.checkpoint_service.get_processed_episodes(),
                "last_updated": datetime.now().isoformat()
            }
            
            # Save the detailed stats
            self.checkpoint_service.update_extraction_stats(detailed_stats)
            
            # Mark the process as complete
            if save_checkpoints:
                self.checkpoint_service.mark_episode_stage_complete(
                    episode_id=self.checkpoint_service.checkpoint_data.get("last_processed_episode", "initial"),
                    stage="complete"
                )
                logger.info("Opinion extraction process completed successfully")
                
                # Print extraction stats
                stats = self.checkpoint_service.get_extraction_stats()
                logger.info(f"Extraction stats: {stats}")
        
        # Get all processed episodes (including previously processed ones)
        all_updated_episodes = episodes.copy()
        for i, episode in enumerate(all_updated_episodes):
            for updated_ep in updated_episodes:
                if updated_ep.video_id == episode.video_id:
                    all_updated_episodes[i] = updated_ep
                    break
        
        return all_updated_episodes
    
    def extract_opinions_from_transcript(
        self, 
        episode: PodcastEpisode, 
        transcript_path: str,
        save_checkpoint: bool = True
    ) -> List[Opinion]:
        """
        Extract opinions from a single transcript.
        This is a convenience method that processes a single episode
        and returns the extracted opinions directly.
        
        Args:
            episode: The podcast episode metadata
            transcript_path: Path to the transcript TXT file
            save_checkpoint: Whether to save checkpoints during processing
            
        Returns:
            List of extracted opinions
        """
        if not self.use_llm or not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
            return []
        
        # Check if episode is already processed
        if self.checkpoint_service.is_episode_processed(episode.video_id):
            logger.info(f"Episode {episode.title} already processed, checking if extraction is complete")
            
            # If extraction is completed, load existing opinions for this episode
            if self.checkpoint_service.get_episode_stage(self.checkpoint_service.checkpoint_data.get("last_processed_episode")) == CheckpointService.STAGE_COMPLETE:
                existing_opinions = self.opinion_repository.get_all_opinions()
                episode_opinions = [op for op in existing_opinions if op.episode_id == episode.video_id]
                if episode_opinions:
                    logger.info(f"Found {len(episode_opinions)} opinions for episode {episode.title}")
                    return episode_opinions
        
        # Extract raw opinions
        raw_opinions = self.raw_extraction_service.extract_raw_opinions(
            episode=episode,
            transcript_path=transcript_path
        )
        
        if not raw_opinions:
            logger.warning(f"No raw opinions extracted from {episode.title}")
            return []
        
        # Save raw opinions to checkpoint
        if save_checkpoint:
            # Mark episode as processed
            self.checkpoint_service.mark_episode_complete(episode.video_id)
            
            # Save the raw opinions
            all_raw_opinions = self.checkpoint_service.load_raw_opinions() or []
            all_raw_opinions.extend(raw_opinions)
            self.checkpoint_service.save_raw_opinions(all_raw_opinions)
        
        # Categorize opinions
        categorized_opinions = self.categorization_service.categorize_opinions(raw_opinions)
        
        # Get existing opinions for context
        existing_opinions = self.opinion_repository.get_all_opinions()
        existing_opinions_data = []
        
        for opinion in existing_opinions:
            # Convert to dictionary format for relationship analysis
            opinion_dict = {
                "id": opinion.id,
                "title": opinion.title,
                "description": opinion.description,
                "category": opinion.category_id
            }
            existing_opinions_data.append(opinion_dict)
        
        # Combine with existing opinions for relationship analysis
        combined_opinions = {}
        for category, opinions in categorized_opinions.items():
            combined_opinions[category] = opinions + [op for op in existing_opinions_data if op.get("category") == category]
        
        # Analyze relationships
        relationship_data = self.relationship_service.analyze_relationships(combined_opinions)
        
        # Process relationships and merge opinions
        final_opinions_data = self.merger_service.process_relationships(
            raw_opinions=raw_opinions + existing_opinions_data,
            relationship_data=relationship_data
        )
        
        # Create Opinion objects
        opinions = self.merger_service.create_opinion_objects(final_opinions_data)
        
        # Get relationships
        relationships = self.relationship_service.get_relationships_from_data(relationship_data)
        
        # Analyze evolution
        evolution_data = self.evolution_service.analyze_opinion_evolution(
            opinions=opinions, 
            relationships=relationships
        )
        
        # Track speaker behavior
        speaker_data = self.speaker_tracking_service.analyze_speaker_behavior(
            opinions=opinions
        )
        
        # Save all data
        self.merger_service.save_opinions(opinions)
        self.evolution_service.save_evolution_data(
            opinions=opinions,
            evolution_chains=evolution_data.get('evolution_chains', []),
            speaker_journeys=evolution_data.get('speaker_journeys', [])
        )
        
        # Mark all stages as complete for this single episode
        if save_checkpoint:
            self.checkpoint_service.mark_stage_complete(CheckpointService.STAGE_COMPLETE)
        
        return opinions
    
    def reset_extraction_process(self) -> None:
        """
        Reset the extraction process by clearing all checkpoints.
        This allows starting the extraction process from scratch.
        """
        self.checkpoint_service.reset_checkpoint()
        logger.info("Extraction process has been reset, all checkpoints cleared")
    
    def _generate_stage_stats(self, stage: str, all_raw_opinions: List[Dict], categorized_opinions: Dict = None, relationship_data: List[Dict] = None, final_opinions: List[Opinion] = None, evolution_data: Dict = None) -> Dict[str, Any]:
        """
        Generate detailed statistics for a specific processing stage.
        
        Args:
            stage: Current processing stage
            all_raw_opinions: All raw opinions extracted
            categorized_opinions: Opinions categorized by category
            relationship_data: Relationship data between opinions
            final_opinions: Final processed opinion objects
            evolution_data: Evolution data for opinions
            
        Returns:
            Dictionary with detailed statistics
        """
        stage_stats = {
            "stage": stage,
            "total_raw_opinions": len(all_raw_opinions),
            "processed_episodes": self.checkpoint_service.get_processed_episodes(),
            "timestamp": datetime.now().isoformat()
        }
        
        # Add stage-specific metrics
        if stage == "raw_extraction":
            speaker_counts = {}
            for opinion in all_raw_opinions:
                for speaker in opinion.get('speakers', []):
                    speaker_name = speaker.get('speaker_name', 'Unknown')
                    if speaker_name not in speaker_counts:
                        speaker_counts[speaker_name] = 0
                    speaker_counts[speaker_name] += 1
            
            stage_stats.update({
                "total_speakers": len(speaker_counts),
                "speaker_opinion_counts": speaker_counts,
                "episodes_with_opinions": len(set([op.get('episode_id') for op in all_raw_opinions]))
            })
        
        if stage in ["categorization", "relationship_analysis", "opinion_merging"] and categorized_opinions:
            category_stats = {
                "total_categories": len(categorized_opinions),
                "categories": list(categorized_opinions.keys()),
                "opinions_per_category": {cat: len(opinions) for cat, opinions in categorized_opinions.items()}
            }
            stage_stats.update(category_stats)
        
        if stage in ["relationship_analysis", "opinion_merging", "evolution_detection"] and relationship_data:
            # Count relationship types
            relationship_types = {}
            for rel in relationship_data:
                rel_type = rel.get('relation_type')
                if rel_type not in relationship_types:
                    relationship_types[rel_type] = 0
                relationship_types[rel_type] += 1
            
            stage_stats.update({
                "total_relationships": len(relationship_data),
                "relationship_types": relationship_types
            })
        
        if stage in ["opinion_merging", "evolution_detection", "speaker_tracking", "complete"] and final_opinions:
            opinion_stats = {
                "total_final_opinions": len(final_opinions),
                "opinion_ids": [op.id for op in final_opinions]
            }
            stage_stats.update(opinion_stats)
        
        if stage in ["evolution_detection", "speaker_tracking", "complete"] and evolution_data:
            evolution_stats = {
                "total_evolution_chains": len(evolution_data.get('evolution_chains', [])),
                "total_speaker_journeys": len(evolution_data.get('speaker_journeys', [])),
            }
            stage_stats.update(evolution_stats)
        
        return stage_stats 