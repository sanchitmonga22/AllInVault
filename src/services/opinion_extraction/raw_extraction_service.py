"""
Raw Opinion Extraction Service

This module provides functionality for extracting initial opinions from podcast transcripts
without considering prior opinions from other episodes.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime

from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance
from src.services.llm_service import LLMService
from src.services.opinion_extraction.base_service import BaseOpinionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RawOpinionExtractionService(BaseOpinionService):
    """Service for extracting raw opinions from podcast transcripts using LLM."""
    
    def __init__(self, 
                 llm_service: Optional[LLMService] = None,
                 max_opinions_per_episode: int = 15):
        """
        Initialize the raw opinion extraction service.
        
        Args:
            llm_service: LLM service for extraction
            max_opinions_per_episode: Maximum number of opinions to extract per episode
        """
        super().__init__(llm_service)
        self.max_opinions_per_episode = max_opinions_per_episode
    
    def extract_raw_opinions(self, episode: PodcastEpisode, transcript_path: str) -> List[Dict]:
        """
        Extract raw opinions from a transcript without considering previous opinions.
        
        Args:
            episode: The podcast episode metadata
            transcript_path: Path to the transcript TXT file
            
        Returns:
            List of extracted raw opinion dictionaries
        """
        if not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
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
        
        # Extract speaker information
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
            raw_opinions = self._call_llm_for_raw_extraction(
                episode_metadata=episode_metadata,
                transcript_text=transcript_text,
                speakers_info=speakers_info
            )
            
            # Process and enhance raw opinions with episode and timestamp information
            processed_raw_opinions = self._process_raw_extraction_results(
                raw_opinions=raw_opinions,
                episode=episode
            )
            
            return processed_raw_opinions
            
        except Exception as e:
            logger.error(f"Error extracting raw opinions with LLM: {e}")
            return []
            
    def _construct_raw_extraction_prompt(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict
    ) -> Dict:
        """
        Construct prompt for raw opinion extraction.
        
        Args:
            episode_metadata: Episode metadata
            transcript_text: Formatted transcript text
            speakers_info: Information about speakers
            
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

Focus on extracting substantive opinions, not casual remarks or observations. Pay careful attention to the speakers' stances on each opinion. Note when multiple speakers comment on the same opinion and their respective positions.

IMPORTANT: For each speaker discussing an opinion, include:
- Speaker ID
- Speaker name
- Start time (timestamp)
- End time (approximate)
- Stance (support/oppose/neutral)
- Reasoning for their stance

Output your analysis in the following JSON format:
{
  "opinions": [
    {
      "id": "generated-unique-id",
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
      "episode_id": "episode-id-from-metadata"
    }
  ]
}

Extract the most significant opinions (maximum {self.max_opinions_per_episode}) from the transcript.
"""

        # Format episode info
        episode_info = f"""
EPISODE INFO:
Title: {episode_metadata.get('title', 'Unknown')}
ID: {episode_metadata.get('id', 'Unknown')}
Date: {episode_metadata.get('date', 'Unknown')}
Description: {episode_metadata.get('description', 'Unknown')}
"""

        # Format speakers info
        speakers_section = "SPEAKERS INFO:\n"
        for speaker_id, info in speakers_info.items():
            speakers_section += f"Speaker {speaker_id}: {info.get('name', 'Unknown')} ({info.get('role', 'Unknown')})\n"

        # Format the user input section
        user_prompt = f"""
Given the following podcast transcript, identify and extract the key opinions expressed by the speakers.

{episode_info}
{speakers_section}

TRANSCRIPT:
{transcript_text}

Extract the key opinions from this transcript using the format described earlier. 
Focus on the most significant, substantive opinions (maximum {self.max_opinions_per_episode}).
Make sure to include proper metadata for each speaker (ID, name, timestamps, stance, reasoning).
"""

        return {
            "system_prompt": system_prompt,
            "user_prompt": user_prompt
        }
    
    def _call_llm_for_raw_extraction(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict
    ) -> Dict:
        """
        Call LLM to extract raw opinions from transcript.
        
        Args:
            episode_metadata: Metadata about the episode
            transcript_text: Formatted transcript text
            speakers_info: Information about speakers in the episode
            
        Returns:
            Dictionary with extracted raw opinions
        """
        if not self.llm_service:
            return {}
            
        # Construct prompt for opinion extraction
        prompts = self._construct_raw_extraction_prompt(
            episode_metadata=episode_metadata,
            transcript_text=transcript_text,
            speakers_info=speakers_info
        )
            
        # Call LLM service
        try:
            # Assuming LLMService has a method for raw extraction
            response = self.llm_service.extract_opinions_from_transcript(
                system_prompt=prompts["system_prompt"],
                prompt=prompts["user_prompt"],
                episode_metadata=episode_metadata
            )
            
            return response
        except Exception as e:
            logger.error(f"Error calling LLM for raw opinion extraction: {e}")
            return {}
    
    def _process_raw_extraction_results(
        self,
        raw_opinions: Dict,
        episode: PodcastEpisode
    ) -> List[Dict]:
        """
        Process raw LLM extraction results to add episode metadata and normalize format.
        
        Args:
            raw_opinions: Raw extraction results from LLM
            episode: Podcast episode object
            
        Returns:
            List of processed raw opinion dictionaries
        """
        processed_opinions = []
        
        # Handle the case when we get a string instead of a dict (sometimes happens with LLM responses)
        if isinstance(raw_opinions, str):
            try:
                # Try to parse it as JSON
                import json
                raw_opinions = json.loads(raw_opinions)
            except json.JSONDecodeError:
                logger.error(f"Could not parse LLM response as JSON: {raw_opinions[:100]}...")
                return []
        
        if not raw_opinions or not isinstance(raw_opinions, dict):
            logger.error("Invalid extraction results format")
            return []
        
        # Get the opinions list from the response
        opinions_data = raw_opinions.get("opinions", [])
        if not opinions_data or not isinstance(opinions_data, list):
            logger.error("No opinions found in extraction results")
            return []
        
        # Normalize episode published_at date
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
                
                # Generate ID if not provided
                opinion_id = opinion_data.get("id", str(uuid.uuid4()))
                
                # Get speaker information
                speaker_info = opinion_data.get("speakers", [])
                
                # Handle the case when speakers is a string or not a list
                if not isinstance(speaker_info, list):
                    logger.error(f"Speaker info is not a list: {type(speaker_info)}")
                    speaker_info = []
                
                # Ensure we have at least one valid speaker
                if not speaker_info:
                    logger.warning(f"Skipping opinion with no speakers: {title}")
                    continue
                
                # Create the processed opinion with episode metadata
                processed_opinion = {
                    "id": opinion_id,
                    "title": title,
                    "description": description,
                    "content": content,
                    "speakers": speaker_info,
                    "category": opinion_data.get("category", "Uncategorized").strip(),
                    "keywords": opinion_data.get("keywords", []) if isinstance(opinion_data.get("keywords"), list) else [],
                    "episode_id": episode.video_id,
                    "episode_title": episode.title,
                    "episode_date": episode_date,
                    "confidence": opinion_data.get("confidence", 0.8)
                }
                
                processed_opinions.append(processed_opinion)
            
            except Exception as e:
                logger.error(f"Error processing raw opinion data: {e}")
                continue
        
        logger.info(f"Processed {len(processed_opinions)} raw opinions from {episode.title}")
        return processed_opinions 