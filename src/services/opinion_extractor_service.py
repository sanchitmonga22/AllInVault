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
import random
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from pathlib import Path

from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance
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
    
    def _get_most_recent_date(self, opinion: Opinion) -> datetime:
        """
        Get the most recent appearance date for an opinion.
        
        Args:
            opinion: The opinion to get the date for
            
        Returns:
            The most recent appearance date or datetime.min if no appearances
        """
        if not opinion.appearances:
            return datetime.min
        
        # Ensure all dates have timezone information or all don't
        dates = []
        for app in opinion.appearances:
            if app.date:
                # Convert to naive datetime if it has timezone info
                if hasattr(app.date, 'tzinfo') and app.date.tzinfo is not None:
                    dates.append(app.date.replace(tzinfo=None))
                else:
                    dates.append(app.date)
        
        # Return the most recent date
        return max(dates) if dates else datetime.min

    def _filter_relevant_opinions(
        self, 
        existing_opinions: List[Opinion],
        episode: PodcastEpisode
    ) -> List[Opinion]:
        """
        Filter existing opinions to only include the most relevant ones for context.
        
        Args:
            existing_opinions: All existing opinions
            episode: Current episode being processed
            
        Returns:
            List of the most relevant opinions for providing context
        """
        if not existing_opinions:
            return []
        
        # If we have a small number of opinions, use them all
        if len(existing_opinions) <= self.max_context_opinions:
            return existing_opinions
        
        # Extract metadata
        episode_speakers = self._extract_speaker_info(episode)
        episode_speaker_ids = list(episode_speakers.keys())
        
        # Calculate opinion relevance scores
        relevance_scores = []
        
        for i, opinion in enumerate(existing_opinions):
            score = 0
            
            # Prioritize opinions by the same speakers
            for speaker_id in opinion.get_all_speaker_ids():
                if speaker_id in episode_speaker_ids:
                    score += 10
            
            # Prioritize recent opinions
            opinion_date = self._get_most_recent_date(opinion)
            
            # Ensure episode date is naive if opinion_date is naive
            episode_date = episode.published_at
            if hasattr(episode_date, 'tzinfo') and episode_date.tzinfo is not None and (opinion_date == datetime.min or opinion_date.tzinfo is None):
                episode_date = episode_date.replace(tzinfo=None)
            
            # Calculate days between (handle case where opinion_date is datetime.min)
            if opinion_date == datetime.min:
                days_ago = 1000  # Just a large number to indicate old/no date
            else:
                try:
                    days_ago = (episode_date - opinion_date).days
                except TypeError:
                    # If we still have timezone mismatch, convert both to naive
                    episode_date = episode_date.replace(tzinfo=None) if hasattr(episode_date, 'tzinfo') and episode_date.tzinfo is not None else episode_date
                    opinion_date = opinion_date.replace(tzinfo=None) if hasattr(opinion_date, 'tzinfo') and opinion_date.tzinfo is not None else opinion_date
                    days_ago = (episode_date - opinion_date).days
            
            # Higher score for more recent opinions (but avoid negative days)
            days_ago = max(0, days_ago)
            recency_score = max(0, 100 - (days_ago / 10))
            score += recency_score
            
            # Add a small random factor to break ties
            score += random.random()
            
            relevance_scores.append((i, score))
        
        # Sort by relevance score (descending)
        relevance_scores.sort(key=lambda x: x[1], reverse=True)
        
        # Take the top N opinions
        top_indices = [idx for idx, _ in relevance_scores[:self.max_context_opinions]]
        
        # Return the most relevant opinions
        return [existing_opinions[i] for i in top_indices]
    
    def _construct_opinion_extraction_prompt(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict,
        existing_opinions: List[Opinion] = None
    ) -> Dict:
        """
        Construct prompt for opinion extraction.
        
        Args:
            episode_metadata: Episode metadata
            transcript_text: Formatted transcript text
            speakers_info: Information about speakers
            existing_opinions: List of existing opinions for context
            
        Returns:
            Dictionary containing system_prompt and user_prompt
        """
        system_prompt = """
You are an expert opinion analyzer for podcasts. Your task is to extract opinions expressed by speakers in the podcast transcript.

For each opinion, provide:
1. A concise title
2. A detailed description
3. The content (direct quote or paraphrase)
4. The speaker information with timestamps and stance
5. A category the opinion belongs to (choose the most appropriate: Politics, Economics, Technology, Society, Philosophy, Science, Business, Culture, Health, Environment, Media, Education, Finance, Sports, Entertainment, or create a new one if needed)
6. Keywords associated with the opinion
7. Evolution notes (if this opinion builds on or changes a previous one)
8. Identify contradictions (if the speaker contradicts themselves or others)

IMPORTANT: Focus on extracting substantive opinions, not casual remarks or observations. Pay careful attention to the speakers' stances on each opinion. Note when multiple speakers comment on the same opinion and their respective positions.

Output your analysis in the following JSON format:
{
  "opinions": [
    {
      "title": "Short opinion title",
      "description": "Detailed description of the opinion",
      "content": "Direct quote or paraphrase of the opinion",
      "speakers": [
        {
          "speaker_id": "1",
          "speaker_name": "Speaker Name",
          "stance": "support/oppose/neutral",
          "reasoning": "Why they have this stance",
          "start_time": 123.4,
          "end_time": 145.6
        }
      ],
      "category": "Category name",
      "keywords": ["keyword1", "keyword2"],
      "is_contradiction": false,
      "contradicts_opinion_id": null,
      "contradiction_notes": null,
      "evolution_notes": null,
      "related_opinions": []
    }
  ]
}

If there are connections to previous opinions, note them in the "related_opinions" field and explain the evolution in "evolution_notes". Pay special attention to conflicting opinions and mark contradictions appropriately.
"""

        # Format episode info
        episode_info = f"""
EPISODE INFO:
Title: {episode_metadata.get('title', 'Unknown')}
Date: {episode_metadata.get('date', 'Unknown')}
"""

        # Format speakers info
        speakers_section = "SPEAKERS INFO:\n"
        for speaker_id, info in speakers_info.items():
            speakers_section += f"Speaker {speaker_id}: {info.get('name', 'Unknown')}\n"

        # Format existing opinions for context
        context_opinions = ""
        if existing_opinions and len(existing_opinions) > 0:
            context_opinions = f"""
PREVIOUS OPINIONS CONTEXT:
{self._format_opinions_for_context(existing_opinions)}
"""

        # Format the user input section
        user_prompt = f"""
Given the following podcast transcript, identify and extract the key opinions expressed by the speakers.

{episode_info}
{speakers_section}

{context_opinions}

TRANSCRIPT:
{transcript_text}

Extract the key opinions from this transcript using the format described earlier. 
Focus on the most significant, substantive opinions (maximum {self.max_opinions_per_episode}).
When a speaker refers to or builds upon an opinion from a previous episode, note this in the evolution_notes and link them in related_opinions.
"""

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
    
    def _format_opinions_for_context(self, opinions: List[Opinion]) -> str:
        """
        Format existing opinions for inclusion in the context.
        
        Args:
            opinions: List of existing opinions
            
        Returns:
            Formatted opinions text
        """
        formatted_opinions = ""
        
        for i, opinion in enumerate(opinions):
            # Get the most recent appearance
            latest_appearance = opinion.appearances[0] if opinion.appearances else None
            
            speakers_info = ""
            if latest_appearance and latest_appearance.speakers:
                speakers = []
                for speaker in latest_appearance.speakers:
                    stance_text = f"({speaker.stance})" if speaker.stance != "support" else ""
                    speakers.append(f"{speaker.speaker_name} {stance_text}")
                speakers_info = ", ".join(speakers)
            
            formatted_opinions += f"""
Opinion ID: {opinion.id}
Title: {opinion.title}
Category: {opinion.category_id}
Speakers: {speakers_info}
Description: {opinion.description}
"""
            
            # Add evolution notes if present
            if opinion.evolution_notes:
                formatted_opinions += f"Evolution Notes: {opinion.evolution_notes}\n"
                
            # Add contradiction information if present
            if opinion.is_contradiction and opinion.contradicts_opinion_id:
                formatted_opinions += f"Contradicts Opinion: {opinion.contradicts_opinion_id}\n"
                if opinion.contradiction_notes:
                    formatted_opinions += f"Contradiction Notes: {opinion.contradiction_notes}\n"
            
            # Separator between opinions
            if i < len(opinions) - 1:
                formatted_opinions += "----------\n"
        
        return formatted_opinions
    
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
        prompts = self._construct_opinion_extraction_prompt(
            episode_metadata=episode_metadata,
            transcript_text=transcript_text,
            speakers_info=speakers_info,
            existing_opinions=existing_opinions
        )
            
        # Call LLM service
        try:
            response = self.llm_service.extract_opinions_from_transcript(
                system_prompt=prompts["system_prompt"],
                prompt=prompts["user_prompt"],
                episode_metadata=episode_metadata
            )
            
            return response
        except Exception as e:
            logger.error(f"Error calling LLM for opinion extraction: {e}")
            return {}
    
    def _process_llm_results(
        self,
        extracted_opinions: Dict,
        episode: PodcastEpisode,
        existing_opinions: List[Opinion] = None
    ) -> List[Opinion]:
        """
        Process raw LLM extraction results and create Opinion objects.
        
        Args:
            extracted_opinions: Raw extraction results from LLM
            episode: Podcast episode object
            existing_opinions: List of existing opinions for context
            
        Returns:
            List of processed Opinion objects
        """
        processed_opinions = []
        
        # Handle the case when we get a string instead of a dict (sometimes happens with LLM responses)
        if isinstance(extracted_opinions, str):
            try:
                # Try to parse it as JSON
                import json
                extracted_opinions = json.loads(extracted_opinions)
            except json.JSONDecodeError:
                logger.error(f"Could not parse LLM response as JSON: {extracted_opinions[:100]}...")
                return []
        
        if not extracted_opinions or not isinstance(extracted_opinions, dict):
            logger.error("Invalid extraction results format")
            return []
        
        # Get the opinions list from the response
        opinions_data = extracted_opinions.get("opinions", [])
        if not opinions_data or not isinstance(opinions_data, list):
            logger.error("No opinions found in extraction results")
            return []
        
        existing_opinions = existing_opinions or []
        existing_opinion_map = {op.id: op for op in existing_opinions}
        
        # Build a map of existing opinions by title/description for matching
        title_description_map = {}
        for op in existing_opinions:
            key = f"{op.title.lower()}:{op.description.lower()}"
            title_description_map[key] = op
        
        # Map of category names to category objects for quick lookup
        category_map = {}
        for category in self.category_repository.get_all_categories():
            category_map[category.name.lower()] = category
        
        # Normalize episode published_at date to ensure it's a naive datetime
        episode_date = episode.published_at
        if episode_date and hasattr(episode_date, 'tzinfo') and episode_date.tzinfo is not None:
            episode_date = episode_date.replace(tzinfo=None)
        
        # Process each opinion
        for opinion_data in opinions_data:
            try:
                # Skip if not a dict
                if not isinstance(opinion_data, dict):
                    logger.error(f"Invalid opinion data format: {type(opinion_data)}")
                    continue
                
                # Extract basic fields from opinion data
                title = opinion_data.get("title", "").strip()
                description = opinion_data.get("description", "").strip()
                content = opinion_data.get("content", "").strip()
                
                if not title or not description:
                    logger.warning("Skipping opinion with missing title or description")
                    continue
                
                # Get or create category
                category_name = opinion_data.get("category", "Uncategorized").strip()
                category = None
                
                if category_name.lower() in category_map:
                    category = category_map[category_name.lower()]
                else:
                    # Create new category
                    category = self.category_repository.find_or_create_category(category_name)
                    category_map[category_name.lower()] = category
                
                # Get speaker information and stances
                speaker_info = opinion_data.get("speakers", [])
                
                # Handle the case when speakers is a string
                if isinstance(speaker_info, str):
                    logger.error(f"Speaker info is a string, not a list: {speaker_info}")
                    speaker_info = []
                
                if not isinstance(speaker_info, list):
                    speaker_info = [speaker_info]
                
                speakers = []
                
                for speaker_data in speaker_info:
                    # Skip if not a dict
                    if not isinstance(speaker_data, dict):
                        logger.error(f"Invalid speaker data format: {type(speaker_data)}")
                        continue
                    
                    speaker_id = str(speaker_data.get("speaker_id", "unknown"))
                    speaker_name = speaker_data.get("speaker_name", f"Speaker {speaker_id}")
                    
                    # Create SpeakerStance object
                    speaker = SpeakerStance(
                        speaker_id=speaker_id,
                        speaker_name=speaker_name,
                        stance=speaker_data.get("stance", "support"),
                        reasoning=speaker_data.get("reasoning"),
                        start_time=speaker_data.get("start_time"),
                        end_time=speaker_data.get("end_time")
                    )
                    speakers.append(speaker)
                
                # Skip if no valid speakers
                if not speakers:
                    logger.warning(f"Skipping opinion with no valid speakers: {title}")
                    continue
                
                # Create the episode appearance
                appearance = OpinionAppearance(
                    episode_id=episode.video_id,
                    episode_title=episode.title,
                    date=episode_date,  # Use normalized episode date
                    speakers=speakers,
                    content=content
                )
                
                # Try to match with existing opinions
                matched_opinion = self._find_matching_opinion(
                    title, description, category.id, existing_opinions
                )
                
                if matched_opinion:
                    # Update the existing opinion with this new appearance
                    matched_opinion.add_appearance(appearance)
                    
                    # Handle evolution notes
                    evolution_notes = opinion_data.get("evolution_notes")
                    if evolution_notes:
                        if matched_opinion.evolution_notes:
                            matched_opinion.evolution_notes += f"\n\n{evolution_notes}"
                        else:
                            matched_opinion.evolution_notes = evolution_notes
                    
                    # Handle related opinions
                    related_opinions = opinion_data.get("related_opinions", [])
                    if related_opinions and isinstance(related_opinions, list):
                        for related_id in related_opinions:
                            if related_id not in matched_opinion.related_opinions:
                                matched_opinion.related_opinions.append(related_id)
                    
                    # Handle contradictions
                    is_contradiction = opinion_data.get("is_contradiction", False)
                    contradicts_id = opinion_data.get("contradicts_opinion_id")
                    
                    if is_contradiction and contradicts_id:
                        matched_opinion.is_contradiction = True
                        matched_opinion.contradicts_opinion_id = contradicts_id
                        matched_opinion.contradiction_notes = opinion_data.get("contradiction_notes")
                    
                    processed_opinions.append(matched_opinion)
                else:
                    # Create a new opinion
                    new_opinion = Opinion(
                        id=str(uuid.uuid4()),
                        title=title,
                        description=description,
                        category_id=category.id,
                        related_opinions=opinion_data.get("related_opinions", []) if isinstance(opinion_data.get("related_opinions"), list) else [],
                        evolution_notes=opinion_data.get("evolution_notes"),
                        is_contradiction=opinion_data.get("is_contradiction", False),
                        contradicts_opinion_id=opinion_data.get("contradicts_opinion_id"),
                        contradiction_notes=opinion_data.get("contradiction_notes"),
                        keywords=opinion_data.get("keywords", []) if isinstance(opinion_data.get("keywords"), list) else [],
                        confidence=opinion_data.get("confidence", 0.8)
                    )
                    
                    # Add the appearance
                    new_opinion.add_appearance(appearance)
                    
                    processed_opinions.append(new_opinion)
            
            except Exception as e:
                logger.error(f"Error processing opinion data: {e}")
                continue
        
        # Save all processed opinions
        if processed_opinions:
            self.opinion_repository.save_opinions(processed_opinions)
            logger.info(f"Saved {len(processed_opinions)} opinions to repository")
        
        return processed_opinions
    
    def _find_matching_opinion(
        self,
        title: str,
        description: str,
        category_id: str,
        existing_opinions: List[Opinion]
    ) -> Optional[Opinion]:
        """
        Find an existing opinion that matches the provided details.
        
        Args:
            title: Opinion title
            description: Opinion description
            category_id: Category ID
            existing_opinions: List of existing opinions
            
        Returns:
            Matched opinion or None if no match found
        """
        # First try exact match by title
        title_matches = [op for op in existing_opinions if op.title.lower() == title.lower()]
        
        if len(title_matches) == 1:
            return title_matches[0]
        
        # If multiple title matches, narrow down by description similarity
        if len(title_matches) > 1:
            for op in title_matches:
                if self._is_similar_text(op.description.lower(), description.lower()):
                    return op
        
        # Try by description similarity in the same category
        category_matches = [op for op in existing_opinions if op.category_id == category_id]
        for op in category_matches:
            if self._is_similar_text(op.description.lower(), description.lower()):
                return op
        
        # No matches found
        return None
    
    def _is_similar_text(self, text1: str, text2: str, threshold: float = 0.8) -> bool:
        """
        Check if two text strings are similar using simple heuristics.
        
        Args:
            text1: First text string
            text2: Second text string
            threshold: Similarity threshold
            
        Returns:
            True if texts are similar, False otherwise
        """
        # Very simple similarity check for now
        # Could be enhanced with more sophisticated algorithms
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return False
            
        intersection = words1.intersection(words2)
        
        similarity = len(intersection) / max(len(words1), len(words2))
        
        return similarity >= threshold
    
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