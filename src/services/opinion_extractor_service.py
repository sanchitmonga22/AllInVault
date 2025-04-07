"""
Opinion Extractor Service

This module provides functionality for extracting opinions from podcast transcripts
and tracking them over time using an LLM.
"""

import json
import os
import uuid
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from pathlib import Path

from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion
from src.services.llm_service import LLMService
from src.repositories.opinion_repository import OpinionRepository

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
                 opinions_file_path: str = "data/json/opinions.json"):
        """
        Initialize the opinion extraction service.
        
        Args:
            use_llm: Whether to use LLM for opinion extraction
            llm_provider: LLM provider ('openai' or other supported providers)
            llm_api_key: API key for the LLM provider
            llm_model: Model name for the LLM provider
            opinions_file_path: Path to store opinions
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
        
        # Initialize opinion repository
        self.opinion_repository = OpinionRepository(opinions_file_path)
    
    def load_transcript(self, transcript_path: str) -> Dict:
        """
        Load transcript data from file.
        
        Args:
            transcript_path: Path to the transcript JSON file
            
        Returns:
            Dictionary with transcript data
        """
        try:
            with open(transcript_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading transcript: {e}")
            return {}
    
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
            transcript_path: Path to the transcript JSON file
            existing_opinions: List of existing opinions to consider for tracking
            
        Returns:
            List of extracted opinions
        """
        if not self.use_llm or not self.llm_service:
            logger.warning("LLM is required for opinion extraction but not available")
            return []
        
        # Load transcript data
        transcript_data = self.load_transcript(transcript_path)
        if not transcript_data or 'results' not in transcript_data:
            logger.warning(f"No valid transcript data found for {episode.title}")
            return []
        
        # Format the transcript for LLM processing
        transcript_text = self._format_transcript_for_llm(transcript_data)
        if not transcript_text:
            logger.warning(f"Failed to format transcript for {episode.title}")
            return []
        
        # Get existing opinions for context (for tracking over time)
        existing_opinions_data = []
        if existing_opinions:
            for op in existing_opinions:
                existing_opinions_data.append({
                    "id": op.id,
                    "title": op.title,
                    "speaker_name": op.speaker_name,
                    "content": op.content,
                    "category": op.category
                })
        
        # Prepare episode metadata for the LLM
        episode_metadata = {
            "id": episode.video_id,
            "title": episode.title,
            "date": episode.published_at,
            "description": episode.description
        }
        
        # Extract speaker information if available
        speakers_info = {}
        if episode.metadata and "speakers" in episode.metadata:
            for speaker_id, speaker_data in episode.metadata["speakers"].items():
                speakers_info[speaker_id] = {
                    "name": speaker_data.get("name", f"Speaker {speaker_id}"),
                    "is_guest": speaker_data.get("is_guest", False),
                    "is_unknown": speaker_data.get("is_unknown", False)
                }
        
        # Call LLM to extract opinions
        try:
            extracted_opinions = self._call_llm_for_opinion_extraction(
                episode_metadata=episode_metadata,
                transcript_text=transcript_text,
                speakers_info=speakers_info,
                existing_opinions=existing_opinions_data
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
            return []
    
    def _format_transcript_for_llm(self, transcript_data: Dict) -> str:
        """
        Format transcript data into a text format suitable for LLM processing.
        
        Args:
            transcript_data: The raw transcript data
            
        Returns:
            Formatted transcript text
        """
        formatted_text = []
        
        if 'results' in transcript_data and 'utterances' in transcript_data['results']:
            for utterance in transcript_data['results']['utterances']:
                if 'speaker' in utterance and 'transcript' in utterance:
                    speaker_id = utterance['speaker']
                    text = utterance['transcript']
                    time = utterance.get('start', 0)
                    formatted_text.append(f"[{time:.2f}] Speaker {speaker_id}: {text}")
        
        return "\n".join(formatted_text)
    
    def _call_llm_for_opinion_extraction(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict,
        existing_opinions: List[Dict] = None
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
            # The LLM service doesn't have extract_opinions method yet, so we'll need to add it
            # or use a generic call method. Here's using a placeholder:
            response = self.llm_service.extract_opinions_from_transcript(
                prompt=prompt,
                episode_metadata=episode_metadata
            )
            
            return response
        except Exception as e:
            logger.error(f"Error calling LLM for opinion extraction: {e}")
            return {}
    
    def _construct_opinion_extraction_prompt(
        self,
        episode_metadata: Dict,
        transcript_text: str,
        speakers_info: Dict,
        existing_opinions: List[Dict] = None
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
        speakers_text = ""
        for speaker_id, speaker_info in speakers_info.items():
            role = "Guest" if speaker_info.get("is_guest") else "Host"
            if speaker_info.get("is_unknown"):
                role = "Unknown"
            speakers_text += f"Speaker {speaker_id}: {speaker_info.get('name', f'Speaker {speaker_id}')} ({role})\n"
        
        # Format existing opinions for context
        existing_opinions_text = ""
        if existing_opinions:
            existing_opinions_text = "PREVIOUSLY IDENTIFIED OPINIONS:\n\n"
            for i, op in enumerate(existing_opinions, 1):
                existing_opinions_text += f"{i}. ID: {op['id']}\n"
                existing_opinions_text += f"   Title: {op['title']}\n"
                existing_opinions_text += f"   Speaker: {op['speaker_name']}\n"
                existing_opinions_text += f"   Category: {op['category']}\n"
                existing_opinions_text += f"   Content: {op['content']}\n\n"
        
        # Create the full prompt
        prompt = f"""
        # OPINION EXTRACTION TASK

        Your task is to extract, categorize and track the opinions expressed by speakers in this podcast transcript.

        ## EPISODE INFORMATION:
        ID: {episode_id}
        Title: {episode_title}
        Date: {episode_date}

        ## SPEAKERS:
        {speakers_text}

        {existing_opinions_text}

        ## INSTRUCTIONS:
        1. Identify strong opinions expressed by speakers in the transcript
        2. For each opinion:
           - Create a concise title
           - Write a detailed description
           - Note the speaker ID and timestamps
           - Categorize the opinion (politics, economics, technology, science, philosophy, etc.)
           - Extract keywords related to the opinion
           - Assess the sentiment (positive, negative, neutral)
           - If it relates to any previously identified opinions, note the relationship
           - Track how opinions evolve or change during the conversation

        ## IMPORTANT NOTES:
        - Focus on substantive opinions, not casual remarks
        - Look for areas where speakers express strong views or make predictions
        - Pay special attention to recurring themes or topics
        - Capture diverse opinions across different domains (not just politics/economics)
        - For unknown speakers, label them as specified in the transcript
        - If opinions relate to previously identified ones, explain how they connect or evolve

        ## TRANSCRIPT:
        {transcript_text}

        ## OUTPUT FORMAT:
        Provide your response as a JSON object with the following structure:
        ```json
        {
          "opinions": [
            {
              "title": "Short descriptive title",
              "description": "Detailed description of the opinion",
              "content": "Direct quote or close paraphrase of the opinion",
              "speaker_id": "ID of the speaker (as shown in transcript)",
              "start_time": float value of start time,
              "end_time": float value of end time,
              "category": "Category of the opinion",
              "keywords": ["keyword1", "keyword2", ...],
              "sentiment": float value between -1 (negative) and 1 (positive),
              "confidence": float value between 0 and 1,
              "related_opinion_ids": ["id1", "id2", ...] (IDs of related opinions from previous list),
              "evolution_notes": "Notes on how this opinion relates to or evolves from previous opinions"
            }
          ]
        }
        ```
        
        Remember to be comprehensive but focus on meaningful opinions rather than trivial comments.
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
        
        # Create a mapping of existing opinion IDs to opinion objects
        existing_opinion_map = {}
        if existing_opinions:
            for op in existing_opinions:
                existing_opinion_map[op.id] = op
        
        # Get the raw opinions list
        raw_opinions = extracted_opinions.get("opinions", [])
        
        for raw_op in raw_opinions:
            try:
                # Generate a unique ID for this opinion
                opinion_id = str(uuid.uuid4())
                
                # Get the episode date
                if episode.published_at:
                    try:
                        episode_date = datetime.fromisoformat(episode.published_at.replace('Z', '+00:00'))
                    except (ValueError, TypeError):
                        episode_date = datetime.now()
                else:
                    episode_date = datetime.now()
                
                # Prepare related opinions
                related_opinion_ids = raw_op.get("related_opinion_ids", [])
                # Filter to only include valid existing opinion IDs
                valid_related_ids = [op_id for op_id in related_opinion_ids if op_id in existing_opinion_map]
                
                # Extract speaker name from ID
                speaker_id = raw_op.get("speaker_id", "0")
                speaker_name = "Unknown Speaker"
                
                if episode.metadata and "speakers" in episode.metadata:
                    speaker_info = episode.metadata["speakers"].get(speaker_id)
                    if speaker_info:
                        speaker_name = speaker_info.get("name", f"Speaker {speaker_id}")
                
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
                    start_time=raw_op.get("start_time", 0.0),
                    end_time=raw_op.get("end_time", 0.0),
                    date=episode_date,
                    keywords=raw_op.get("keywords", []),
                    sentiment=raw_op.get("sentiment"),
                    confidence=raw_op.get("confidence", 0.7),
                    category=raw_op.get("category"),
                    related_opinions=valid_related_ids,
                    evolution_notes=raw_op.get("evolution_notes"),
                    metadata={
                        "episode_published_at": episode.published_at,
                        "extraction_date": datetime.now().isoformat()
                    }
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
                        "category": opinion.category,
                        "start_time": opinion.start_time,
                        "end_time": opinion.end_time
                    }
                
                # Add these opinions to our context for subsequent episodes
                existing_opinions.extend(opinions)
            
            updated_episodes.append(episode)
        
        return updated_episodes 