"""
LLM Service

This module provides LLM integration for enhanced speaker identification.
"""

import json
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union

import openai

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    def extract_speakers(self, episode_metadata: Dict, transcript_sample: str) -> Dict:
        """
        Extract potential speakers from episode metadata and transcript using LLM.
        
        Args:
            episode_metadata: Dictionary with episode metadata
            transcript_sample: Sample from the transcript for context
            
        Returns:
            Dictionary with identified potential speakers
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-3.5-turbo"):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to environment variable)
            model: Model to use (default: gpt-3.5-turbo)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OpenAI API key is required")
        
        self.model = model
        # Set OpenAI API key - compatible with both old and new versions
        openai.api_key = self.api_key
        
    def extract_speakers(self, episode_metadata: Dict, transcript_sample: str) -> Dict:
        """
        Extract potential speakers from episode metadata and transcript using OpenAI.
        
        Args:
            episode_metadata: Dictionary with episode metadata
            transcript_sample: Sample from the transcript for context
            
        Returns:
            Dictionary with identified potential speakers
        """
        try:
            # Prepare prompt with episode metadata and transcript sample
            title = episode_metadata.get("title", "")
            description = episode_metadata.get("description", "")
            
            prompt = f"""
            I need to identify all speakers in a podcast episode based on the following information:
            
            TITLE: {title}
            
            DESCRIPTION: {description}
            
            TRANSCRIPT SAMPLE: {transcript_sample}
            
            Known podcast hosts are:
            1. Chamath Palihapitiya
            2. Jason Calacanis
            3. David Sacks
            4. David Friedberg
            
            Please identify:
            1. Which of the known hosts are present in this episode
            2. Any guest speakers that appear in this episode (from title, description, or transcript)
            
            Format your response as a JSON object with the following structure:
            {{
                "hosts": [
                    {{"name": "Full Name", "confidence": 0.9, "mentioned_in": ["title", "description", "transcript"]}}
                ],
                "guests": [
                    {{"name": "Guest Name", "confidence": 0.8, "mentioned_in": ["title", "description"]}}
                ]
            }}
            """
            
            # Try using newer OpenAI API version first
            try:
                # Compatible with openai>=1.0.0
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                
                # Different parameters based on model - only gpt-4-turbo and newer support response_format=json_object
                if "gpt-4-turbo" in self.model or "gpt-4-0125" in self.model:
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that identifies podcast speakers."},
                            {"role": "user", "content": prompt}
                        ],
                        response_format={"type": "json_object"}
                    )
                else:
                    # For older models like gpt-4, don't use response_format
                    response = client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": "You are a helpful assistant that identifies podcast speakers. Return JSON only."},
                            {"role": "user", "content": prompt + "\n\nImportant: Return your response as a valid JSON object only, with no other text."}
                        ]
                    )
                
                content = response.choices[0].message.content
            except (ImportError, AttributeError):
                # Fallback to older OpenAI API version
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies podcast speakers."},
                        {"role": "user", "content": prompt}
                    ]
                )
                content = response.choices[0].message["content"]
            
            # Extract and parse JSON response
            try:
                # First try direct JSON parsing
                try:
                    speakers_data = json.loads(content)
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON portion
                    logger.warning("Failed to parse direct JSON, attempting to extract JSON portion")
                    import re
                    json_pattern = r'({[\s\S]*})'
                    match = re.search(json_pattern, content)
                    if match:
                        json_str = match.group(1)
                        speakers_data = json.loads(json_str)
                    else:
                        logger.error("Could not extract JSON from LLM response")
                        return {"hosts": [], "guests": []}
                
                return speakers_data
            except (AttributeError, IndexError) as e:
                logger.error(f"Error processing OpenAI response: {e}")
                return {"hosts": [], "guests": []}
                
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return {"hosts": [], "guests": []}


class DeepSeekProvider(LLMProvider):
    """DeepSeek implementation of LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-coder"):
        """
        Initialize DeepSeek provider.
        
        Args:
            api_key: DeepSeek API key (defaults to environment variable)
            model: Model to use (default: deepseek-coder)
        """
        self.api_key = api_key or os.getenv("DEEP_SEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key is required")
        
        self.model = model
        # Placeholder for actual DeepSeek client initialization
        # self.client = DeepSeek(api_key=self.api_key)
        
    def extract_speakers(self, episode_metadata: Dict, transcript_sample: str) -> Dict:
        """
        Extract potential speakers from episode metadata and transcript using DeepSeek.
        
        Args:
            episode_metadata: Dictionary with episode metadata
            transcript_sample: Sample from the transcript for context
            
        Returns:
            Dictionary with identified potential speakers
        """
        try:
            # Prepare prompt with episode metadata and transcript sample
            title = episode_metadata.get("title", "")
            description = episode_metadata.get("description", "")
            
            prompt = f"""
            I need to identify all speakers in a podcast episode based on the following information:
            
            TITLE: {title}
            
            DESCRIPTION: {description}
            
            TRANSCRIPT SAMPLE: {transcript_sample}
            
            Known podcast hosts are:
            1. Chamath Palihapitiya
            2. Jason Calacanis
            3. David Sacks
            4. David Friedberg
            
            Please identify which of the known hosts are present in this episode,
            and any guest speakers that appear in this episode (from title, description, or transcript).
            
            Format your response as a JSON object with the following structure:
            {
                "hosts": [
                    {"name": "Full Name", "confidence": 0.9, "mentioned_in": ["title", "description", "transcript"]}
                ],
                "guests": [
                    {"name": "Guest Name", "confidence": 0.8, "mentioned_in": ["title", "description"]}
                ]
            }
            """
            
            # TODO: Implement actual DeepSeq API call
            # For now, return a placeholder response
            logger.warning("DeepSeq integration not fully implemented yet")
            return {"hosts": [], "guests": []}
                
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            return {"hosts": [], "guests": []}


class LLMService:
    """Service for LLM integration in the AllInVault platform."""
    
    def __init__(self, provider: str = "openai", api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the LLM service.
        
        Args:
            provider: LLM provider ('openai' or 'deepseek')
            api_key: API key for the provider
            model: Model name (provider-specific)
        """
        self.provider_name = provider.lower()
        
        if self.provider_name == "openai":
            model = model or "gpt-3.5-turbo"
            self.provider = OpenAIProvider(api_key=api_key, model=model)
        elif self.provider_name == "deepseek":
            model = model or "deepseek-coder"
            self.provider = DeepSeekProvider(api_key=api_key, model=model)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def extract_speakers_from_episode(self, episode: Any, transcript_sample: Optional[str] = None) -> Dict:
        """
        Extract speakers from an episode using LLM.
        
        Args:
            episode: PodcastEpisode instance
            transcript_sample: Optional transcript sample (if not provided, will try to extract from file)
            
        Returns:
            Dictionary with identified speakers
        """
        # Convert episode to dict for metadata extraction
        episode_metadata = episode.to_dict() if hasattr(episode, "to_dict") else episode
        
        # Get transcript sample if not provided
        if not transcript_sample and episode.transcript_filename:
            try:
                transcript_sample = self._get_transcript_sample(episode.transcript_filename)
            except Exception as e:
                logger.warning(f"Could not extract transcript sample: {e}")
                transcript_sample = ""
        
        # Call provider to extract speakers
        speakers_data = self.provider.extract_speakers(episode_metadata, transcript_sample or "")
        
        return speakers_data
    
    def _get_transcript_sample(self, transcript_path: str, sample_size: int = 10) -> str:
        """
        Get a sample from a transcript file.
        
        Args:
            transcript_path: Path to transcript file
            sample_size: Number of utterances to sample
            
        Returns:
            Sample text from the transcript
        """
        try:
            with open(transcript_path, 'r') as f:
                transcript_data = json.load(f)
            
            if 'results' in transcript_data and 'utterances' in transcript_data['results']:
                utterances = transcript_data['results']['utterances'][:sample_size]
                sample_text = "\n".join([f"Speaker {u.get('speaker', '?')}: {u.get('transcript', '')}" 
                                         for u in utterances])
                return sample_text
            return ""
        except Exception as e:
            logger.error(f"Error reading transcript sample: {e}")
            return "" 