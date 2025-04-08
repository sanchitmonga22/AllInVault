"""
Base Opinion Extraction Service

This module provides base functionality for opinion extraction services.
"""

import logging
import os
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime

from src.models.podcast_episode import PodcastEpisode
from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance
from src.services.llm_service import LLMService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BaseOpinionService:
    """Base service class for opinion extraction components."""
    
    def __init__(self, 
                 llm_service: Optional[LLMService] = None):
        """
        Initialize the base opinion service.
        
        Args:
            llm_service: LLM service for text processing
        """
        self.llm_service = llm_service
    
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
            
            import re
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