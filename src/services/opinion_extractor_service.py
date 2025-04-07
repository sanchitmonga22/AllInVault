"""
Opinion Extractor Service

This module provides functionality for extracting opinions from podcast transcripts
and tracking them over time using an LLM.
"""

import json
import os
import uuid
import logging
import re
from typing import Dict, List, Optional, Any, Set
from datetime import datetime
from pathlib import Path

from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion
from src.models.opinions.category import Category
from src.services.llm_service import LLMService
from src.repositories.opinion_repository import OpinionRepository
from src.repositories.category_repository import CategoryRepository

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class OpinionExtractorService:
    """Service for extracting opinions from podcast transcripts using LLM."""
    
    def __init__(self, 
                 use_llm: bool = True,
                 llm_provider: str = "openai",
                 llm_api_key: Optional[str] = None,
                 llm_model: Optional[str] = None,
                 opinions_file_path: str = "data/json/opinions.json",
                 categories_file_path: str = "data/json/categories.json",
                 max_context_opinions: int = 20,
                 max_opinions_per_episode: int = 15):
        """
        Initialize the opinion extraction service.
        
        Args:
            use_llm: Whether to use LLM for opinion extraction
            llm_provider: LLM provider ('openai' or other supported providers)
            llm_api_key: API key for the LLM provider
            llm_model: Model name for the LLM provider
            opinions_file_path: Path to store opinions
            categories_file_path: Path to store categories
            max_context_opinions: Maximum number of previous opinions to include in context
            max_opinions_per_episode: Maximum number of opinions to extract per episode
        """
        # LLM integration
        self.use_llm = use_llm
        self.llm_service = None
        self.max_context_opinions = max_context_opinions
        self.max_opinions_per_episode = max_opinions_per_episode
        
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
    
    def load_transcript(self, transcript_path: str) -> Dict:
        """
        Load transcript data from TXT file.
        
        Args:
            transcript_path: Path to the transcript TXT file
            
        Returns:
            Dictionary with transcript data in a standardized format
        """
        try:
            # Only support TXT format
            if not transcript_path.lower().endswith('.txt'):
                logger.error(f"Only TXT transcripts are supported, but got: {transcript_path}")
                return {}
                
            return self._load_txt_transcript(transcript_path)
        except Exception as e:
            logger.error(f"Error loading transcript: {e}")
            return {}
    
    def _load_txt_transcript(self, transcript_path: str) -> Dict:
        """
        Load transcript data from a TXT file and convert to a standardized format.
        
        Args:
            transcript_path: Path to the TXT transcript file
            
        Returns:
            Dictionary with transcript data in standardized format
        """
        try:
            with open(transcript_path, 'r') as f:
                content = f.read()
                
            # Store the raw content for direct use in LLM prompt
            result = {
                "raw_content": content,
                "format": "txt"
            }
            
            # Extract metadata and segments for structured access if needed
            lines = content.split('\n')
            metadata = {}
            transcript_start_index = 0
            
            # Process header metadata (lines before the "====" separator)
            for i, line in enumerate(lines):
                line = line.strip()
                if line.startswith("===="):
                    transcript_start_index = i + 1
                    break
                elif ":" in line and not line.startswith("["):
                    key, value = line.split(":", 1)
                    metadata[key.strip("# ")] = value.strip()
                elif line and line.startswith("#"):
                    # Handle title line
                    metadata["title"] = line.strip("# ")
            
            # Process transcript content
            segments = []
            speaker_map = {}
            
            for line in lines[transcript_start_index:]:
                line = line.strip()
                if not line:
                    continue
                
                # Parse timestamps and speaker information
                # Format: [timestamp] Speaker N: text
                match = re.match(r'\[([\d\.]+)\]\s+Speaker\s+(\d+):\s+(.*)', line)
                if match:
                    timestamp, speaker_id, text = match.groups()
                    
                    segment = {
                        "speaker_id": speaker_id,
                        "start_time": float(timestamp),
                        "end_time": float(timestamp) + 5.0,  # Estimate 5 seconds per segment
                        "text": text,
                        "line": line  # Store the original line for direct use
                    }
                    segments.append(segment)
            
            # Add structured data to the result
            result["metadata"] = metadata
            result["segments"] = segments
            
            return result
            
        except Exception as e:
            logger.error(f"Error parsing TXT transcript: {e}")
            return {}
    
    def _format_transcript_for_llm(self, transcript_data: Dict) -> str:
        """
        Format transcript data for LLM processing.
        
        Args:
            transcript_data: Transcript data dictionary from _load_txt_transcript
            
        Returns:
            Formatted transcript text ready for LLM prompt
        """
        # For TXT transcripts, we can use the raw content directly
        if "raw_content" in transcript_data and transcript_data.get("format") == "txt":
            # Extract just the transcript portion (after the separator)
            content = transcript_data["raw_content"]
            lines = content.split('\n')
            
            transcript_start = False
            transcript_text = ""
            
            for line in lines:
                line = line.strip()
                if line.startswith("===="):
                    transcript_start = True
                    continue
                    
                if transcript_start and line:
                    transcript_text += line + "\n\n"
            
            return transcript_text
        
        # Fallback to segment-based formatting if raw content isn't available
        formatted_text = ""
        
        if "segments" in transcript_data:
            segments = transcript_data["segments"]
            
            for segment in segments:
                # Use the original line if available
                if "line" in segment:
                    formatted_text += segment["line"] + "\n\n"
                else:
                    # Format manually if needed
                    speaker_id = segment.get("speaker_id", "unknown")
                    timestamp = f"[{segment.get('start_time', 0):.1f}]"
                    text = segment.get("text", "")
                    formatted_text += f"{timestamp} Speaker {speaker_id}: {text}\n\n"
        
        return formatted_text
    
    def extract_opinions_from_transcript(
        self, 
        episode: PodcastEpisode, 
        transcript_path: str,
        existing_opinions: List[Opinion] = None
    ) -> List[Opinion]:
        """
        Extract opinions from a transcript using LLM.
        
        Args:
            episode: The podcast episode metadata
            transcript_path: Path to the transcript TXT file
            existing_opinions: List of existing opinions to consider for tracking
            
        Returns:
            List of extracted opinions
        """
        if not self.use_llm or not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
            return []
        
        # Check if transcript path exists
        if not os.path.exists(transcript_path):
            logger.warning(f"Transcript file not found: {transcript_path}")
            return []
        
        # Verify it's a TXT file
        if not transcript_path.lower().endswith('.txt'):
            logger.warning(f"Only TXT transcripts are supported, but got: {transcript_path}")
            return []
        
        # Load transcript data
        transcript_data = self.load_transcript(transcript_path)
        if not transcript_data:
            logger.warning(f"No valid transcript data found for {episode.title}")
            return []
        
        # Format the transcript for LLM processing
        transcript_text = self._format_transcript_for_llm(transcript_data)
        if not transcript_text:
            logger.warning(f"Failed to format transcript for {episode.title}")
            return []
        
        # Log success in transcript formatting
        logger.info(f"Successfully formatted transcript for {episode.title} (length: {len(transcript_text)} chars)")
        
        # Filter and prepare existing opinions for context
        filtered_opinions = self._filter_relevant_opinions(
            existing_opinions=existing_opinions or [],
            episode=episode
        )
        
        # Extract speaker information if available
        speakers_info = self._extract_speaker_info(episode)
        
        # Prepare episode metadata for the LLM
        episode_metadata = {
            "id": episode.video_id,
            "title": episode.title,
            "date": episode.published_at,
            "description": episode.description
        }
        
        # Call LLM to extract opinions
        try:
            extracted_opinions = self._call_llm_for_opinion_extraction(
                episode_metadata=episode_metadata,
                transcript_text=transcript_text,
                speakers_info=speakers_info,
                existing_opinions=filtered_opinions
            )
            
            # Process raw LLM results into Opinion objects
            processed_opinions = self._process_llm_results(
                extracted_opinions=extracted_opinions,
                episode=episode,
                existing_opinions=existing_opinions
            )
            
            return processed_opinions
            
        except Exception as e:
            logger.error(f"Error extracting opinions with LLM: {e}")
            logger.error(f"Exception details: {str(e)}")
            return []
    
    def _extract_speaker_info(self, episode: PodcastEpisode) -> Dict[str, Dict]:
        """
        Extract speaker information from episode metadata.
        
        Args:
            episode: The podcast episode
            
        Returns:
            Dictionary mapping speaker IDs to speaker information
        """
        speakers_info = {}
        if episode.metadata and "speakers" in episode.metadata:
            for speaker_id, speaker_data in episode.metadata["speakers"].items():
                # Extract name, defaulting to a placeholder if not available
                name = speaker_data.get("name", f"Speaker {speaker_id}")
                
                # Determine if host/guest and add other available metadata
                is_guest = speaker_data.get("is_guest", False)
                is_unknown = speaker_data.get("is_unknown", False)
                role = "Guest" if is_guest else "Host"
                if is_unknown:
                    role = "Unknown"
                
                speakers_info[speaker_id] = {
                    "name": name,
                    "is_guest": is_guest,
                    "is_unknown": is_unknown,
                    "role": role,
                    # Include any additional metadata that might be useful
                    "metadata": {k: v for k, v in speaker_data.items() 
                                if k not in ["name", "is_guest", "is_unknown"]}
                }
                
                logger.info(f"Resolved speaker ID {speaker_id} to name: {name} ({role})")
        else:
            logger.warning(f"No speaker information found in episode metadata for {episode.title}")
        
        return speakers_info
    
    def _filter_relevant_opinions(
        self, 
        existing_opinions: List[Opinion],
        episode: PodcastEpisode
    ) -> List[Opinion]:
        """
        Filter existing opinions to find the most relevant ones for context.
        
        Args:
            existing_opinions: All existing opinions
            episode: The current episode
            
        Returns:
            Filtered list of most relevant opinions for context
        """
        if not existing_opinions:
            return []
            
        # Sort opinions by date (newest first)
        sorted_opinions = sorted(
            existing_opinions,
            key=lambda op: op.date if op.date else datetime.min,
            reverse=True
        )
        
        # Different buckets for opinions by relevance
        speaker_opinions = []  # Opinions by the same speakers
        recent_opinions = []   # Recent opinions (regardless of speaker)
        topic_opinions = {}    # Opinions by category
        
        # Extract speakers from episode
        episode_speakers = set()
        if episode.metadata and "speakers" in episode.metadata:
            episode_speakers = set(episode.metadata["speakers"].keys())
        
        # Get all categories
        all_categories = self.category_repository.get_all_categories()
        category_mapping = {cat.id: cat for cat in all_categories}
        
        # Filter and organize opinions
        for opinion in sorted_opinions:
            # Opinions by the same speakers
            if opinion.speaker_id in episode_speakers:
                speaker_opinions.append(opinion)
                
            # Organize by category
            category_id = opinion.category_id
            if category_id:
                if category_id not in topic_opinions:
                    topic_opinions[category_id] = []
                if len(topic_opinions[category_id]) < 3:  # Limit to 3 opinions per category
                    topic_opinions[category_id].append(opinion)
                    
            # Recent opinions (past 5 episodes)
            if len(recent_opinions) < 10:
                recent_opinions.append(opinion)
                
        # Combine the different opinion buckets with preference order:
        # 1. Speaker opinions (same speakers)
        # 2. Topic opinions (same categories)
        # 3. Recent opinions
        
        combined_opinions = []
        
        # First add speaker opinions (limited)
        combined_opinions.extend(speaker_opinions[:10])
        
        # Then add topic opinions
        for category_id, opinions in topic_opinions.items():
            # Only add opinions not already included
            for opinion in opinions:
                if opinion not in combined_opinions and len(combined_opinions) < self.max_context_opinions:
                    combined_opinions.append(opinion)
        
        # Finally add recent opinions
        for opinion in recent_opinions:
            if opinion not in combined_opinions and len(combined_opinions) < self.max_context_opinions:
                combined_opinions.append(opinion)
        
        # Truncate to max context limit
        return combined_opinions[:self.max_context_opinions]
    
    def _call_llm_for_opinion_extraction(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict,
        existing_opinions: List[Opinion] = None
    ) -> Dict:
        """
        Call LLM to extract opinions from transcript.
        
        Args:
            episode_metadata: Metadata about the episode
            transcript_text: Formatted transcript text
            speakers_info: Information about speakers in the episode
            existing_opinions: List of existing opinions for context
            
        Returns:
            Dictionary with extracted opinions
        """
        if not self.llm_service:
            return {}
            
        # Construct prompt for opinion extraction
        prompt = self._construct_opinion_extraction_prompt(
            episode_metadata=episode_metadata,
            transcript_text=transcript_text,
            speakers_info=speakers_info,
            existing_opinions=existing_opinions
        )
            
        # Call LLM service
        try:
            response = self.llm_service.extract_opinions_from_transcript(
                prompt=prompt,
                episode_metadata=episode_metadata
            )
            
            return response
        except Exception as e:
            logger.error(f"Error calling LLM for opinion extraction: {e}")
            return {}
    
    def _format_opinions_for_context(self, opinions: List[Opinion]) -> str:
        """
        Format a list of opinions into a concise text for LLM context.
        
        Args:
            opinions: List of opinions to format
            
        Returns:
            Formatted opinions text
        """
        if not opinions:
            return ""
            
        # Group opinions by category
        categories = {}
        uncategorized = []
        
        for opinion in opinions:
            if opinion.category_id:
                if opinion.category_id not in categories:
                    # Get category name if available
                    category = self.category_repository.get_category(opinion.category_id)
                    category_name = category.name if category else opinion.category_id
                    categories[opinion.category_id] = {
                        "name": category_name,
                        "opinions": []
                    }
                categories[opinion.category_id]["opinions"].append(opinion)
            else:
                uncategorized.append(opinion)
        
        # Format opinions by category
        formatted_text = "PREVIOUSLY IDENTIFIED OPINIONS:\n\n"
        
        for category_id, category_data in categories.items():
            category_name = category_data["name"]
            category_opinions = category_data["opinions"]
            
            formatted_text += f"CATEGORY: {category_name}\n"
            
            for i, op in enumerate(category_opinions, 1):
                formatted_text += f"{i}. ID: {op.id}\n"
                formatted_text += f"   Title: {op.title}\n"
                formatted_text += f"   Speaker: {op.speaker_name}\n"
                formatted_text += f"   Content: {op.content}\n"
                
                # Add evolution information if available
                if op.evolution_notes:
                    formatted_text += f"   Evolution: {op.evolution_notes}\n"
                
                formatted_text += "\n"
        
        # Add uncategorized opinions
        if uncategorized:
            formatted_text += "UNCATEGORIZED OPINIONS:\n"
            for i, op in enumerate(uncategorized, 1):
                formatted_text += f"{i}. ID: {op.id}\n"
                formatted_text += f"   Title: {op.title}\n"
                formatted_text += f"   Speaker: {op.speaker_name}\n"
                formatted_text += f"   Content: {op.content}\n"
                
                # Add evolution information if available
                if op.evolution_notes:
                    formatted_text += f"   Evolution: {op.evolution_notes}\n"
                
                formatted_text += "\n"
        
        return formatted_text
    
    def _construct_opinion_extraction_prompt(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict,
        existing_opinions: List[Opinion] = None
    ) -> str:
        """
        Construct prompt for the LLM to extract opinions.
        
        Args:
            episode_metadata: Metadata about the episode
            transcript_text: Formatted transcript text
            speakers_info: Information about speakers in the episode
            existing_opinions: List of existing opinions for context
            
        Returns:
            Formatted prompt for the LLM
        """
        # Basic episode information
        episode_id = episode_metadata.get("id", "")
        episode_title = episode_metadata.get("title", "")
        episode_date = episode_metadata.get("date", "")
        
        # Format speakers information
        speakers_text = "SPEAKERS IN THIS EPISODE:\n"
        for speaker_id, speaker_info in speakers_info.items():
            name = speaker_info.get("name", f"Speaker {speaker_id}")
            role = speaker_info.get("role", "Unknown")
            speakers_text += f"Speaker {speaker_id}: {name} ({role})\n"
        
        # Format existing opinions in a more concise and structured way
        existing_opinions_text = self._format_opinions_for_context(existing_opinions) if existing_opinions else ""
        
        # Get available categories for the LLM to use
        categories = self.category_repository.get_all_categories()
        categories_text = "AVAILABLE CATEGORIES:\n"
        categories_text += "\n".join([f"- {category.name}: {category.description}" for category in categories])
        categories_text += "\n\nNOTE: If you identify an opinion that doesn't fit into any of these categories, you can suggest a new category."
        
        # Use double curly braces to escape them in f-strings
        json_structure = """
        {
          "opinions": [
            {
              "title": "Short descriptive title",
              "description": "Detailed description of the opinion",
              "content": "Direct quote or close paraphrase of the opinion",
              "speakers": [
                {
                  "speaker_id": "ID of the speaker",
                  "stance": "support" or "oppose" or "neutral",
                  "reasoning": "Brief explanation of why the speaker holds this stance",
                  "start_time": float value of start time when this speaker discusses the opinion,
                  "end_time": float value of end time when this speaker finishes discussing the opinion
                }
              ],
              "primary_speaker_id": "ID of the main speaker who originated this opinion",
              "category": "Category name (use existing or suggest new if needed)",
              "keywords": ["keyword1", "keyword2", ...],
              "sentiment": float value between -1 (negative) and 1 (positive),
              "confidence": float value between 0 and 1,
              "related_opinion_ids": ["id1", "id2", ...] (IDs of related opinions from previous list),
              "evolution_notes": "Detailed notes on how this opinion relates to or evolves from previous opinions",
              "is_contentious": boolean indicating if there's significant disagreement about this opinion,
              "contradicts_opinion_id": "ID of an opinion this directly contradicts (if applicable)",
              "contradiction_notes": "Explanation of the contradiction (if applicable)"
            }
          ],
          "new_categories": [
            {
              "name": "New Category Name",
              "description": "Description of what this category encompasses"
            }
          ],
          "cross_episode_opinions": [
            {
              "opinion_id": "ID of a previously identified opinion that also appears in this episode",
              "evolution_notes": "How the opinion evolved in this episode",
              "speakers": [
                {
                  "speaker_id": "ID of the speaker",
                  "stance": "support" or "oppose" or "neutral",
                  "reasoning": "Brief explanation of why the speaker holds this stance",
                  "start_time": float value of start time,
                  "end_time": float value of end time
                }
              ]
            }
          ]
        }
        """
        
        # Add instructions for multi-speaker opinions and contradictions
        prompt = f"""
        # OPINION EXTRACTION AND EVOLUTION TRACKING

        Your task is to extract, categorize and track how opinions evolve over time by analyzing this podcast transcript.

        ## EPISODE INFORMATION:
        ID: {episode_id}
        Title: {episode_title}
        Date: {episode_date}

        ## {speakers_text}

        ## {categories_text}

        {existing_opinions_text}

        ## INSTRUCTIONS:
        1. Identify strong opinions expressed by speakers in the transcript
        2. IMPORTANT: Extract at most {self.max_opinions_per_episode} opinions from this episode
        3. For each opinion:
           - Create a concise title
           - Write a detailed description
           - Record ALL speakers who express a stance on this opinion
           - For each speaker, note their stance (support, oppose, neutral), reasoning, and start/end timestamps
           - Mark opinions with significant disagreement as contentious
           - Specify a primary speaker who originated the opinion
           - Categorize the opinion using an existing category OR suggest a new one
           - Extract keywords related to the opinion
           - Assess the sentiment (positive, negative, neutral)
           - If it's related to any previous opinions, include their IDs in related_opinion_ids
           - If it directly contradicts another opinion, note this with contradicts_opinion_id
           - If it's an evolution of a previous opinion, provide detailed evolution_notes

        ## OPINION EVOLUTION TRACKING:
        - Pay special attention to how opinions evolve over time
        - If a speaker changes their stance over time, capture this evolution
        - If a speaker refines, clarifies, or expands on a previous opinion, capture this progression
        - If speakers disagree with each other on the same topic, record their different stances
        - The evolution_notes should clearly explain how opinions change or develop
        - If you identify an opinion from a prior episode reappearing, include it in cross_episode_opinions

        ## CONTRADICTION HANDLING:
        - When speakers disagree on a topic, record this as a single opinion with different stances
        - Include each speaker's reasoning for their stance
        - Use exact quotes or close paraphrases to represent each position
        - Mark contentious opinions where there is significant disagreement

        ## IMPORTANT NOTES:
        - Extract NO MORE THAN {self.max_opinions_per_episode} opinions from this episode
        - Focus on substantive opinions, not casual remarks
        - Look for areas where speakers express strong views or make predictions
        - Capture diverse opinions across different categories
        - For each speaker discussing an opinion, record their exact timestamps
        - Always include the speaker's actual name in your analysis, not just their ID
        - Prioritize quality over quantity in opinion extraction

        ## TRANSCRIPT:
        {transcript_text}

        ## OUTPUT FORMAT:
        Provide your response as a JSON object with the following structure:
        ```json
{json_structure}
        ```
        
        Remember to be comprehensive but focused on meaningful opinions rather than trivial comments.
        """
        
        return prompt
    
    def _process_llm_results(
        self,
        extracted_opinions: Dict,
        episode: PodcastEpisode,
        existing_opinions: List[Opinion] = None
    ) -> List[Opinion]:
        """
        Process raw LLM results into Opinion objects.
        
        Args:
            extracted_opinions: Raw opinion data from LLM
            episode: The podcast episode
            existing_opinions: List of existing opinions
            
        Returns:
            List of processed Opinion objects
        """
        processed_opinions = []
        
        # Map existing opinions by ID for quick lookup
        existing_opinion_map = {}
        if existing_opinions:
            for op in existing_opinions:
                existing_opinion_map[op.id] = op
        
        # Process any new categories suggested by the LLM
        new_categories = extracted_opinions.get("new_categories", [])
        for new_cat in new_categories:
            if "name" in new_cat and new_cat["name"]:
                try:
                    # Check if this category already exists
                    existing_cat = self.category_repository.get_category_by_name(new_cat["name"])
                    if not existing_cat:
                        # Create the new category
                        description = new_cat.get("description", f"Opinions related to {new_cat['name']}")
                        self.category_repository.find_or_create_category(new_cat["name"])
                        logger.info(f"Created new category: {new_cat['name']}")
                except Exception as e:
                    logger.error(f"Error creating new category: {e}")
        
        # First process cross-episode opinions
        cross_episode_opinions = extracted_opinions.get("cross_episode_opinions", [])
        for cross_ep_op in cross_episode_opinions:
            opinion_id = cross_ep_op.get("opinion_id")
            if not opinion_id or opinion_id not in existing_opinion_map:
                logger.warning(f"Referenced opinion ID {opinion_id} not found in existing opinions")
                continue
                
            # Get the existing opinion
            existing_opinion = existing_opinion_map[opinion_id]
            
            # Add this episode to the opinion's appearance list
            existing_opinion.add_episode_occurrence(episode.video_id, episode.title)
            
            # Update evolution notes if provided
            if "evolution_notes" in cross_ep_op and cross_ep_op["evolution_notes"]:
                if existing_opinion.evolution_notes:
                    existing_opinion.evolution_notes += f"\n\nIn episode {episode.title}: {cross_ep_op['evolution_notes']}"
                else:
                    existing_opinion.evolution_notes = f"In episode {episode.title}: {cross_ep_op['evolution_notes']}"
            
            # Process speaker stances for this episode
            speakers = cross_ep_op.get("speakers", [])
            for speaker_data in speakers:
                speaker_id = speaker_data.get("speaker_id")
                if not speaker_id:
                    continue
                    
                # Add speaker timestamp data
                speaker_info = {
                    "start_time": speaker_data.get("start_time", 0.0),
                    "end_time": speaker_data.get("end_time", 0.0),
                    "stance": speaker_data.get("stance", "neutral"),
                    "reasoning": speaker_data.get("reasoning", ""),
                    "episode_id": episode.video_id
                }
                
                # Store in the speaker_timestamps dictionary
                if speaker_id not in existing_opinion.speaker_timestamps:
                    existing_opinion.speaker_timestamps[speaker_id] = {}
                
                # Store episode-specific data
                episode_key = f"episode_{episode.video_id}"
                existing_opinion.speaker_timestamps[speaker_id][episode_key] = speaker_info
            
            # Save the updated opinion
            self.opinion_repository.save_opinion(existing_opinion)
            
            # Add to processed opinions for return
            processed_opinions.append(existing_opinion)
        
        # Get the raw opinions list
        raw_opinions = extracted_opinions.get("opinions", [])
        
        # Extract speaker information from episode metadata
        speakers_by_id = {}
        if episode.metadata and "speakers" in episode.metadata:
            for speaker_id, speaker_data in episode.metadata["speakers"].items():
                speakers_by_id[speaker_id] = speaker_data.get("name", f"Speaker {speaker_id}")
                logger.debug(f"Mapped speaker ID {speaker_id} to name: {speakers_by_id[speaker_id]}")
        else:
            logger.warning(f"No speaker metadata found for episode {episode.title}")
        
        # Limit the number of opinions per episode
        if len(raw_opinions) > self.max_opinions_per_episode:
            logger.warning(f"LLM returned {len(raw_opinions)} opinions, limiting to {self.max_opinions_per_episode}")
            raw_opinions = raw_opinions[:self.max_opinions_per_episode]
        
        for raw_op in raw_opinions:
            try:
                # Generate a unique ID for this opinion
                opinion_id = str(uuid.uuid4())
                
                # Get the episode date
                if episode.published_at:
                    try:
                        if isinstance(episode.published_at, datetime):
                            episode_date = episode.published_at
                        else:
                            episode_date = datetime.fromisoformat(episode.published_at.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        episode_date = datetime.now()
                else:
                    episode_date = datetime.now()
                
                # Get category ID from name
                category_id = None
                category_name = raw_op.get("category", "")
                if category_name:
                    category = self.category_repository.find_or_create_category(category_name)
                    category_id = category.id
                
                # Prepare related opinions
                related_opinion_ids = raw_op.get("related_opinion_ids", [])
                
                # Filter to only include valid existing opinion IDs
                valid_related_ids = [op_id for op_id in related_opinion_ids if op_id in existing_opinion_map]
                
                # Process contradiction data
                is_contradiction = raw_op.get("is_contentious", False)
                contradicts_opinion_id = raw_op.get("contradicts_opinion_id")
                if contradicts_opinion_id and contradicts_opinion_id not in existing_opinion_map:
                    logger.warning(f"Referenced contradiction opinion ID {contradicts_opinion_id} not found")
                    contradicts_opinion_id = None
                
                contradiction_notes = raw_op.get("contradiction_notes", "")
                
                # Process speaker data
                speakers_data = raw_op.get("speakers", [])
                
                # Use primary speaker as the main speaker for the opinion
                primary_speaker_id = raw_op.get("primary_speaker_id")
                if not primary_speaker_id and speakers_data:
                    primary_speaker_id = speakers_data[0].get("speaker_id", "0")
                    
                speaker_id = primary_speaker_id or "0"
                
                # Determine speaker name
                speaker_name = "Unknown Speaker"
                if speaker_id in speakers_by_id:
                    speaker_name = speakers_by_id[speaker_id]
                elif episode.metadata and "speakers" in episode.metadata and speaker_id in episode.metadata["speakers"]:
                    speaker_data = episode.metadata["speakers"][speaker_id]
                    speaker_name = speaker_data.get("name", f"Speaker {speaker_id}")
                
                # If we have multiple speakers, create a combined speaker name
                speaker_names = []
                speaker_timestamps = {}
                
                for speaker_data in speakers_data:
                    s_id = speaker_data.get("speaker_id")
                    if not s_id:
                        continue
                        
                    # Get speaker name
                    s_name = "Unknown Speaker"
                    if s_id in speakers_by_id:
                        s_name = speakers_by_id[s_id]
                    elif episode.metadata and "speakers" in episode.metadata and s_id in episode.metadata["speakers"]:
                        s_info = episode.metadata["speakers"][s_id]
                        s_name = s_info.get("name", f"Speaker {s_id}")
                    
                    # Add to speaker names list if not already there
                    if s_name not in speaker_names:
                        speaker_names.append(s_name)
                    
                    # Add speaker timing and stance data
                    speaker_timestamps[s_id] = {
                        "start_time": speaker_data.get("start_time", 0.0),
                        "end_time": speaker_data.get("end_time", 0.0),
                        "stance": speaker_data.get("stance", "neutral"),
                        "reasoning": speaker_data.get("reasoning", ""),
                        "episode_id": episode.video_id
                    }
                
                # Create combined speaker name
                if len(speaker_names) > 1:
                    speaker_name = ", ".join(speaker_names)
                
                logger.info(f"Processing opinion by {speaker_name} in category: {category_name}")
                
                # Determine overall start and end time from all speakers
                start_times = [data.get("start_time", 0.0) for data in speaker_timestamps.values()]
                end_times = [data.get("end_time", 0.0) for data in speaker_timestamps.values()]
                
                overall_start_time = min(start_times) if start_times else 0.0
                overall_end_time = max(end_times) if end_times else 0.0
                
                # Prepare metadata with properly formatted datetime
                metadata = {
                    "episode_published_at": episode.published_at.isoformat() if isinstance(episode.published_at, datetime) else episode.published_at,
                    "extraction_date": datetime.now().isoformat()
                }
                
                # Add multi-speaker flag if applicable
                if len(speaker_timestamps) > 1:
                    metadata["is_multi_speaker"] = True
                    metadata["all_speaker_ids"] = list(speaker_timestamps.keys())
                
                # Track opinion evolution
                evolution_notes = raw_op.get("evolution_notes", "")
                original_opinion_id = None
                evolution_chain = []
                
                # If this opinion evolves from another, set up the evolution chain
                if valid_related_ids:
                    # Find the oldest related opinion that this one evolves from
                    related_opinions = [existing_opinion_map[op_id] for op_id in valid_related_ids]
                    oldest_related = min(related_opinions, key=lambda op: op.date if op.date else datetime.max)
                    
                    # If the oldest related opinion has an original_opinion_id, use that
                    if oldest_related.original_opinion_id:
                        original_opinion_id = oldest_related.original_opinion_id
                        # Get the evolution chain and append to it
                        if original_opinion_id in existing_opinion_map:
                            original_opinion = existing_opinion_map[original_opinion_id]
                            evolution_chain = original_opinion.evolution_chain.copy()
                    else:
                        # Otherwise, use the oldest related opinion as the original
                        original_opinion_id = oldest_related.id
                        evolution_chain = oldest_related.evolution_chain.copy()
                    
                    # Add all related opinions to the chain if not already there
                    for rel_id in valid_related_ids:
                        if rel_id not in evolution_chain:
                            evolution_chain.append(rel_id)
                
                # Create the opinion object
                opinion = Opinion(
                    id=opinion_id,
                    title=raw_op.get("title", "Untitled Opinion"),
                    description=raw_op.get("description", ""),
                    content=raw_op.get("content", ""),
                    speaker_id=speaker_id,
                    speaker_name=speaker_name,
                    episode_id=episode.video_id,
                    episode_title=episode.title,
                    start_time=overall_start_time,
                    end_time=overall_end_time,
                    date=episode_date,
                    keywords=raw_op.get("keywords", []),
                    sentiment=raw_op.get("sentiment"),
                    confidence=raw_op.get("confidence", 0.7),
                    category_id=category_id,
                    related_opinions=valid_related_ids,
                    evolution_notes=evolution_notes,
                    original_opinion_id=original_opinion_id,
                    evolution_chain=evolution_chain,
                    is_contradiction=is_contradiction,
                    contradicts_opinion_id=contradicts_opinion_id,
                    contradiction_notes=contradiction_notes,
                    appeared_in_episodes=[episode.video_id],
                    speaker_timestamps=speaker_timestamps,
                    metadata=metadata
                )
                
                processed_opinions.append(opinion)
                
            except Exception as e:
                logger.error(f"Error processing opinion: {e}")
        
        return processed_opinions
    
    def extract_opinions(
        self, 
        episodes: List[PodcastEpisode], 
        transcripts_dir: str
    ) -> List[PodcastEpisode]:
        """
        Extract opinions from multiple episodes.
        
        Args:
            episodes: List of episodes to process
            transcripts_dir: Directory containing transcript files
            
        Returns:
            List of updated episodes
        """
        updated_episodes = []
        
        # Process episodes in chronological order
        sorted_episodes = sorted(
            episodes, 
            key=lambda ep: ep.published_at if ep.published_at else "",
            reverse=False
        )
        
        # Get all existing opinions for context
        existing_opinions = self.opinion_repository.get_all_opinions()
        
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
            
            logger.info(f"Extracting opinions from episode: {episode.title}")
            
            # Extract opinions for this episode
            opinions = self.extract_opinions_from_transcript(
                episode=episode,
                transcript_path=transcript_path,
                existing_opinions=existing_opinions
            )
            
            if opinions:
                logger.info(f"Extracted {len(opinions)} opinions from {episode.title}")
                
                # Save the opinions
                self.opinion_repository.save_opinions(opinions)
                
                # Update the episode metadata
                if "opinions" not in episode.metadata:
                    episode.metadata["opinions"] = {}
                
                # Add opinion IDs to episode metadata
                for opinion in opinions:
                    episode.metadata["opinions"][opinion.id] = {
                        "title": opinion.title,
                        "speaker_id": opinion.speaker_id,
                        "speaker_name": opinion.speaker_name,
                        "category_id": opinion.category_id,
                        "start_time": opinion.start_time,
                        "end_time": opinion.end_time
                    }
                
                # Add these opinions to our context for subsequent episodes
                existing_opinions.extend(opinions)
            
            updated_episodes.append(episode)
        
        return updated_episodes 