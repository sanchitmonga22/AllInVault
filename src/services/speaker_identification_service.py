"""
Speaker Identification Service

This module provides functionality for identifying and mapping anonymous speakers 
from transcripts to actual speaker names, using an LLM.
"""

import json
import os
import logging
from typing import Dict, List, Optional
from pathlib import Path

from src.models.podcast_episode import PodcastEpisode
from src.services.llm_service import LLMService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpeakerIdentificationService:
    """Service for identifying speakers in podcast transcripts using LLM."""
    
    def __init__(self, 
                 use_llm: bool = True,
                 llm_provider: str = "deepseek",
                 llm_api_key: Optional[str] = None,
                 llm_model: Optional[str] = None):
        """
        Initialize the speaker identification service.
        
        Args:
            use_llm: Whether to use LLM for speaker identification
            llm_provider: LLM provider ('openai' or 'deepseek')
            llm_api_key: API key for the LLM provider
            llm_model: Model name for the LLM provider
        """
        # LLM integration
        self.use_llm = use_llm
        self.llm_service = None
        
        if use_llm:
            try:
                self.llm_service = LLMService(
                    provider=llm_provider,
                    api_key=llm_api_key,
                    model=llm_model
                )
                logger.info(f"LLM integration enabled with provider: {llm_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                logger.warning("Speaker identification will not work without LLM integration")
                self.use_llm = False
    
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
    
    def extract_speakers_from_transcript(self, transcript_data: Dict) -> Dict[int, Dict]:
        """
        Extract unique speaker IDs from transcript data.
        
        Args:
            transcript_data: Transcript data dictionary
            
        Returns:
            Dictionary mapping speaker IDs to speaker info dictionaries
        """
        speakers = {}
        
        if not transcript_data or 'results' not in transcript_data:
            return speakers
        
        # Extract from utterances if available
        if 'utterances' in transcript_data['results']:
            for utterance in transcript_data['results']['utterances']:
                if 'speaker' in utterance:
                    speaker_id = int(utterance['speaker'])
                    if speaker_id not in speakers:
                        speakers[speaker_id] = {
                            "id": speaker_id,
                            "speaker_tag": f"Speaker {speaker_id}",
                            "name": None,
                            "utterance_count": 0,
                            "samples": [],
                            "confidence": 0.0
                        }
                    
                    speakers[speaker_id]["utterance_count"] += 1
                    
                    # Store sample utterances for later analysis
                    if len(speakers[speaker_id]["samples"]) < 10 and 'transcript' in utterance:
                        speakers[speaker_id]["samples"].append(utterance['transcript'])
        
        return speakers
    
    def identify_speakers(self, transcript_path: str, episode: Optional[PodcastEpisode] = None) -> Dict[int, Dict]:
        """
        Identify speakers in a transcript using LLM.
        
        Args:
            transcript_path: Path to the transcript JSON file
            episode: Optional episode metadata to help with identification
            
        Returns:
            Dictionary mapping speaker IDs to speaker info
        """
        # Load transcript data
        transcript_data = self.load_transcript(transcript_path)
        if not transcript_data:
            return {}
        
        # Extract speakers
        speakers = self.extract_speakers_from_transcript(transcript_data)
        
        # LLM-based identification
        if self.use_llm and self.llm_service and episode:
            # Extract a representative sample from the transcript
            transcript_sample = self._get_transcript_sample(transcript_data, max_length=4000)
            logger.info(f"Using transcript sample for LLM identification")
            
            # Use LLM to identify potential speakers
            llm_speakers = self.llm_service.extract_speakers_from_episode(
                episode, transcript_sample
            )
            
            logger.info(f"LLM identified speakers: {llm_speakers}")
            
            # Process hosts from LLM results
            if "hosts" in llm_speakers:
                # Create a mapping of host names to confidence scores
                host_confidence = {}
                for host in llm_speakers["hosts"]:
                    name = host.get("name")
                    confidence = host.get("confidence", 0.8)  # Default to 0.8 if not provided
                    if name:
                        host_confidence[name] = confidence
                
                # Find speakers with the most utterances to assign to hosts
                speaker_utterance_counts = [(id, info["utterance_count"]) 
                                           for id, info in speakers.items()]
                speaker_utterance_counts.sort(key=lambda x: x[1], reverse=True)
                
                # Assign hosts to the speakers with most utterances
                for host_name, confidence in host_confidence.items():
                    if not speaker_utterance_counts:
                        break
                    
                    speaker_id, _ = speaker_utterance_counts.pop(0)
                    speakers[speaker_id]["name"] = host_name
                    speakers[speaker_id]["confidence"] = confidence
                    speakers[speaker_id]["identified_by_llm"] = True
            
            # Process guests from LLM results
            if "guests" in llm_speakers and llm_speakers["guests"]:
                # Create a set of potential guest names
                guest_names = {guest.get("name"): guest.get("confidence", 0.7)
                             for guest in llm_speakers["guests"] if guest.get("name")}
                
                # Find remaining speakers for guests
                remaining_speakers = [id for id, info in speakers.items() 
                                     if info["name"] is None]
                
                # Assign guests to remaining speakers
                for i, speaker_id in enumerate(remaining_speakers):
                    if i < len(guest_names):
                        guest_name = list(guest_names.keys())[i]
                        confidence = guest_names[guest_name]
                        speakers[speaker_id]["name"] = guest_name
                        speakers[speaker_id]["confidence"] = confidence
                        speakers[speaker_id]["is_guest"] = True
                        speakers[speaker_id]["identified_by_llm"] = True
        
        # Mark any remaining speakers as unknown
        for speaker_id, info in speakers.items():
            if info["name"] is None:
                info["name"] = f"Unknown Speaker {speaker_id}"
                info["confidence"] = 0.1
                info["is_unknown"] = True
        
        return speakers
    
    def process_episode(self, episode: PodcastEpisode, transcripts_dir: str) -> PodcastEpisode:
        """
        Process an episode to identify speakers and update metadata.
        
        Args:
            episode: PodcastEpisode to process
            transcripts_dir: Directory containing transcript files
            
        Returns:
            Updated PodcastEpisode with speaker information
        """
        if not episode.transcript_filename:
            logger.warning(f"Episode {episode.title} has no transcript")
            return episode
        
        transcript_path = os.path.join(transcripts_dir, episode.transcript_filename)
        if not os.path.exists(transcript_path):
            logger.warning(f"Transcript file {transcript_path} not found")
            return episode
        
        # Identify speakers using the episode metadata for context
        speakers = self.identify_speakers(transcript_path, episode)
        
        # Update episode metadata with speaker information
        if speakers:
            episode.speaker_count = len(speakers)
            
            # Create speaker metadata
            speaker_metadata = {}
            for speaker_id, speaker_info in speakers.items():
                speaker_metadata[str(speaker_id)] = {
                    "name": speaker_info["name"],
                    "utterance_count": speaker_info["utterance_count"],
                    "confidence": speaker_info.get("confidence", 0),
                    "is_guest": speaker_info.get("is_guest", False),
                    "is_unknown": speaker_info.get("is_unknown", False),
                    "identified_by_llm": speaker_info.get("identified_by_llm", False)
                }
            
            # Update episode metadata
            if "speakers" not in episode.metadata:
                episode.metadata["speakers"] = speaker_metadata
            else:
                episode.metadata["speakers"].update(speaker_metadata)
        
        return episode
    
    def process_episodes(self, episodes: List[PodcastEpisode], transcripts_dir: str) -> List[PodcastEpisode]:
        """
        Process multiple episodes to identify speakers.
        
        Args:
            episodes: List of PodcastEpisode instances to process
            transcripts_dir: Directory containing transcript files
            
        Returns:
            List of updated PodcastEpisode instances with speaker information
        """
        updated_episodes = []
        
        for episode in episodes:
            updated_episode = self.process_episode(episode, transcripts_dir)
            updated_episodes.append(updated_episode)
        
        return updated_episodes
    
    def _get_transcript_sample(self, transcript_data: Dict, max_length: int = 4000) -> str:
        """
        Extract a representative sample from the transcript for LLM analysis.
        
        Args:
            transcript_data: The transcript data
            max_length: Maximum length of sample in characters
            
        Returns:
            A string containing a sample of utterances
        """
        sample_utterances = []
        total_length = 0
        
        # Extract from utterances if available
        if 'results' in transcript_data and 'utterances' in transcript_data['results']:
            utterances = transcript_data['results']['utterances']
            
            # Sample from beginning, middle, and end of the transcript for better context
            sample_points = [
                (0, min(20, len(utterances))),                      # Beginning (first 20 utterances)
                (len(utterances)//2, min(20, len(utterances)//2)),  # Middle (20 utterances from middle)
                (max(0, len(utterances)-20), min(20, len(utterances)))  # End (last 20 utterances)
            ]
            
            for start_idx, count in sample_points:
                # Skip if we already have enough text
                if total_length >= max_length:
                    break
                    
                # Get a section header
                if start_idx == 0:
                    sample_utterances.append("--- BEGINNING OF TRANSCRIPT ---")
                elif start_idx == len(utterances)//2:
                    sample_utterances.append("--- MIDDLE OF TRANSCRIPT ---")
                else:
                    sample_utterances.append("--- END OF TRANSCRIPT ---")
                
                # Extract utterances from this section
                section_length = 0
                end_idx = min(start_idx + count, len(utterances))
                
                for i in range(start_idx, end_idx):
                    if 'speaker' in utterances[i] and 'transcript' in utterances[i]:
                        utterance_text = f"Speaker {utterances[i]['speaker']}: {utterances[i]['transcript']}"
                        sample_utterances.append(utterance_text)
                        section_length += len(utterance_text)
                        total_length += len(utterance_text)
                        
                        # If this section is getting too long, move to next section
                        if section_length > max_length / 3:
                            break
        
        # If we have no utterances, try to extract from plain transcript
        if not sample_utterances and 'results' in transcript_data and 'transcript' in transcript_data['results']:
            # Split into lines and take samples from beginning, middle, and end
            transcript_lines = transcript_data['results']['transcript'].split('\n')
            
            if len(transcript_lines) > 30:
                # Beginning
                sample_utterances.append("--- BEGINNING OF TRANSCRIPT ---")
                sample_utterances.extend(transcript_lines[:10])
                
                # Middle
                middle_start = len(transcript_lines) // 2 - 5
                sample_utterances.append("--- MIDDLE OF TRANSCRIPT ---")
                sample_utterances.extend(transcript_lines[middle_start:middle_start+10])
                
                # End
                sample_utterances.append("--- END OF TRANSCRIPT ---")
                sample_utterances.extend(transcript_lines[-10:])
            else:
                # Just take all lines if there aren't many
                sample_utterances.extend(transcript_lines)
        
        return "\n".join(sample_utterances) 