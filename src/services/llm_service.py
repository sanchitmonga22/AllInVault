"""
LLM Service

This module provides LLM integration for enhanced speaker identification.
"""

import json
import os
import logging
from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Union
import requests

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

    @abstractmethod
    def extract_opinions_from_transcript(self, system_prompt: str, prompt: str, episode_metadata: Dict) -> Dict:
        """
        Extract opinions from transcript using LLM.
        
        Args:
            system_prompt: The system prompt providing instructions
            prompt: The user prompt with transcript content
            episode_metadata: Dictionary with episode metadata for context
            
        Returns:
            Dictionary with extracted opinions
        """
        pass


class OpenAIProvider(LLMProvider):
    """OpenAI implementation of LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o"):
        """
        Initialize OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to environment variable)
            model: Model to use (default: gpt-4o)
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
            
            # Extract more context from metadata
            guest_hint = ""
            for key_phrase in ["with ", "featuring ", "guest ", "welcomes "]:
                if key_phrase in description.lower():
                    parts = description.lower().split(key_phrase)
                    if len(parts) > 1:
                        # Get the part after the key phrase up to the next punctuation
                        potential_guest = parts[1].split(".")[0].split(",")[0].split("!")[0].strip()
                        if potential_guest and len(potential_guest) > 3:
                            guest_hint = f"The description mentions someone after '{key_phrase}': '{potential_guest}'"
                            break
            
            # Extract a better sample with more turns of conversation
            conversation_turns = []
            current_speaker = None
            current_text = ""
            
            for line in transcript_sample.split('\n'):
                if line.startswith("Speaker "):
                    # Save previous speaker's text
                    if current_speaker is not None and current_text:
                        conversation_turns.append(f"{current_speaker}: {current_text}")
                    
                    # Start new speaker
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        current_speaker = parts[0]
                        current_text = parts[1].strip()
                    else:
                        current_speaker = parts[0]
                        current_text = ""
                else:
                    # Continue current speaker's text
                    current_text += " " + line.strip()
            
            # Add the last speaker
            if current_speaker is not None and current_text:
                conversation_turns.append(f"{current_speaker}: {current_text}")
            
            # Join the conversation turns
            formatted_transcript = "\n".join(conversation_turns)
            
            prompt = f"""
            I need to identify all speakers in a podcast episode based on the following information:
            
            TITLE: {title}
            
            DESCRIPTION: {description}
            
            {guest_hint}
            
            TRANSCRIPT (CONVERSATION FORMAT):
            {formatted_transcript}
            
            Known podcast hosts are:
            1. Chamath Palihapitiya
            2. Jason Calacanis
            3. David Sacks
            4. David Friedberg
            
            Their speaking styles:
            - Chamath: Often discusses economics, venture capital, policy issues; direct in his speaking style
            - Jason: Usually moderates, introduces guests, asks questions; energetic speaking style
            - Sacks: Provides political commentary, business strategy; measured and thoughtful speaking style
            - Friedberg: Discusses scientific topics, data-driven perspectives; analytical speaking style
            
            Analyze the transcript to determine:
            1. Which of the known hosts are participating in this episode
            2. Any guest speakers appearing in this episode (from title, description, or transcript)
            3. Map each "Speaker X" to their actual identity
            
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
            
            # Log the prompt being sent to the API
            logger.info(f"Sending prompt to OpenAI:\n{prompt}")
            
            # Try using newer OpenAI API version first
            try:
                # Compatible with openai>=1.0.0
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                
                # Different parameters based on model
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies podcast speakers by analyzing transcripts and metadata."},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"}
                )
                
                content = response.choices[0].message.content
            except (ImportError, AttributeError):
                # Fallback to older OpenAI API version
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that identifies podcast speakers. Return JSON only."},
                        {"role": "user", "content": prompt + "\n\nImportant: Return your response as a valid JSON object only, with no other text."}
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
    
    def extract_opinions_from_transcript(self, system_prompt: str, prompt: str, episode_metadata: Dict) -> Dict:
        """
        Extract opinions from transcript using OpenAI.
        
        Args:
            system_prompt: The system prompt providing instructions
            prompt: The user prompt with transcript content
            episode_metadata: Dictionary with episode metadata for context
            
        Returns:
            Dictionary with extracted opinions data
        """
        try:
            # Log the prompt being sent to the API (truncated for brevity)
            logger.info(f"Sending opinion extraction prompt to OpenAI (first 500 chars):\n{prompt[:500]}...")
            
            # Try using newer OpenAI API version first
            try:
                # Compatible with openai>=1.0.0
                from openai import OpenAI
                client = OpenAI(api_key=self.api_key)
                
                response = client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt}
                    ],
                    response_format={"type": "json_object"},
                    temperature=0.3,  # Lower temperature for more consistent, focused results
                    max_tokens=4000  # Allow for more detailed response
                )
                
                content = response.choices[0].message.content
            except (ImportError, AttributeError):
                # Fallback to older OpenAI API version
                response = openai.ChatCompletion.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": prompt + "\n\nImportant: Return your response as a valid JSON object only, with no other text."}
                    ],
                    temperature=0.3
                )
                content = response.choices[0].message["content"]
            
            # Extract and parse JSON response
            try:
                # First try direct JSON parsing
                try:
                    opinions_data = json.loads(content)
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON portion
                    logger.warning("Failed to parse direct JSON, attempting to extract JSON portion")
                    import re
                    json_pattern = r'({[\s\S]*})'
                    match = re.search(json_pattern, content)
                    if match:
                        json_str = match.group(1)
                        opinions_data = json.loads(json_str)
                    else:
                        logger.error("Could not extract JSON from LLM response")
                        return {"opinions": []}
                
                return opinions_data
            except (AttributeError, IndexError) as e:
                logger.error(f"Error processing OpenAI response: {e}")
                return {"opinions": []}
                
        except Exception as e:
            logger.error(f"Error calling OpenAI API for opinion extraction: {e}")
            return {"opinions": []}


class DeepSeekProvider(LLMProvider):
    """DeepSeek implementation of LLM provider."""
    
    def __init__(self, api_key: Optional[str] = None, model: str = "deepseek-chat"):
        """
        Initialize DeepSeek provider.
        
        Args:
            api_key: DeepSeek API key (defaults to environment variable)
            model: Model to use (default: deepseek-chat for DeepSeek-V3)
        """
        self.api_key = api_key or os.getenv("DEEP_SEEK_API_KEY")
        if not self.api_key:
            raise ValueError("DeepSeek API key is required")
        
        self.model = model  # Default is deepseek-chat which maps to DeepSeek-V3
        self.base_url = "https://api.deepseek.com"
        
        # Initialize OpenAI client with DeepSeek base URL
        try:
            from openai import OpenAI
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        except ImportError:
            logger.error("OpenAI SDK is required. Please install it with 'pip install openai'")
            raise
        
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
            
            # Extract more context from metadata
            guest_hint = ""
            for key_phrase in ["with ", "featuring ", "guest ", "welcomes "]:
                if key_phrase in description.lower():
                    parts = description.lower().split(key_phrase)
                    if len(parts) > 1:
                        # Get the part after the key phrase up to the next punctuation
                        potential_guest = parts[1].split(".")[0].split(",")[0].split("!")[0].strip()
                        if potential_guest and len(potential_guest) > 3:
                            guest_hint = f"The description mentions someone after '{key_phrase}': '{potential_guest}'"
                            break
            
            # Extract a better sample with more turns of conversation
            conversation_turns = []
            current_speaker = None
            current_text = ""
            
            for line in transcript_sample.split('\n'):
                if line.startswith("Speaker "):
                    # Save previous speaker's text
                    if current_speaker is not None and current_text:
                        conversation_turns.append(f"{current_speaker}: {current_text}")
                    
                    # Start new speaker
                    parts = line.split(':', 1)
                    if len(parts) > 1:
                        current_speaker = parts[0]
                        current_text = parts[1].strip()
                    else:
                        current_speaker = parts[0]
                        current_text = ""
                else:
                    # Continue current speaker's text
                    current_text += " " + line.strip()
            
            # Add the last speaker
            if current_speaker is not None and current_text:
                conversation_turns.append(f"{current_speaker}: {current_text}")
            
            # Join the conversation turns
            formatted_transcript = "\n".join(conversation_turns)
            
            prompt = f"""
            I need to identify all speakers in a podcast episode based on the following information:
            
            TITLE: {title}
            
            DESCRIPTION: {description}
            
            {guest_hint}
            
            TRANSCRIPT (CONVERSATION FORMAT):
            {formatted_transcript}
            
            Known podcast hosts are:
            1. Chamath Palihapitiya
            2. Jason Calacanis
            3. David Sacks
            4. David Friedberg
            
            Their speaking styles:
            - Chamath: Often discusses economics, venture capital, policy issues; direct in his speaking style
            - Jason: Usually moderates, introduces guests, asks questions; energetic speaking style
            - Sacks: Provides political commentary, business strategy; measured and thoughtful speaking style
            - Friedberg: Discusses scientific topics, data-driven perspectives; analytical speaking style
            
            Analyze the transcript to determine:
            1. Which of the known hosts are participating in this episode
            2. Any guest speakers appearing in this episode (from title, description, or transcript)
            3. Map each "Speaker X" to their actual identity
            
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
            
            # Log the prompt being sent to the API
            logger.info(f"Sending prompt to DeepSeek:\n{prompt}")
            
            # Call DeepSeek API using OpenAI SDK
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that identifies podcast speakers by analyzing transcripts and metadata."},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                stream=False
            )
            
            # Extract content from response
            content = response.choices[0].message.content
            
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
            except Exception as e:
                logger.error(f"Error processing DeepSeek response: {e}")
                return {"hosts": [], "guests": []}
                
        except Exception as e:
            logger.error(f"Error calling DeepSeek API: {e}")
            return {"hosts": [], "guests": []}

    def extract_opinions_from_transcript(self, system_prompt: str, prompt: str, episode_metadata: Dict) -> Dict:
        """
        Extract opinions from transcript using DeepSeek.
        
        Args:
            system_prompt: The system prompt providing instructions
            prompt: The user prompt with transcript content
            episode_metadata: Dictionary with episode metadata for context
            
        Returns:
            Dictionary with extracted opinions
        """
        try:
            # Log the prompt being sent to the API (truncated for brevity)
            logger.info(f"Sending opinion extraction prompt to DeepSeek (first 500 chars):\n{prompt[:500]}...")
            
            # Call DeepSeek API using OpenAI SDK
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                response_format={"type": "json_object"},
                temperature=0.3,  # Lower temperature for more consistent, focused results
                stream=False
            )
            
            # Extract content from response
            content = response.choices[0].message.content
            
            # Extract and parse JSON response
            try:
                # First try direct JSON parsing
                try:
                    opinions_data = json.loads(content)
                except json.JSONDecodeError:
                    # If direct parsing fails, try to extract JSON portion
                    logger.warning("Failed to parse direct JSON, attempting to extract JSON portion")
                    import re
                    json_pattern = r'({[\s\S]*})'
                    match = re.search(json_pattern, content)
                    if match:
                        json_str = match.group(1)
                        opinions_data = json.loads(json_str)
                    else:
                        logger.error("Could not extract JSON from LLM response")
                        return {"opinions": []}
                
                return opinions_data
            except Exception as e:
                logger.error(f"Error processing DeepSeek response: {e}")
                return {"opinions": []}
                
        except Exception as e:
            logger.error(f"Error calling DeepSeek API for opinion extraction: {e}")
            return {"opinions": []}


class LLMService:
    """Service for LLM integration in the AllInVault platform."""
    
    def __init__(self, provider: str = "deepseek", api_key: Optional[str] = None, model: Optional[str] = None):
        """
        Initialize the LLM service.
        
        Args:
            provider: LLM provider ('openai' or 'deepseek', default now 'deepseek')
            api_key: API key for the provider
            model: Model name (provider-specific)
        """
        self.provider_name = provider.lower()
        
        if self.provider_name == "openai":
            model = model or "gpt-4o"
            self.provider = OpenAIProvider(api_key=api_key, model=model)
        elif self.provider_name == "deepseek":
            model = model or "deepseek-chat"  # DeepSeek-V3 is accessed via 'deepseek-chat'
            self.provider = DeepSeekProvider(api_key=api_key, model=model)
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    def extract_speakers_from_episode(self, episode: Any, transcript_sample: str) -> Dict:
        """
        Extract potential speakers from an episode using its metadata and transcript.
        
        Args:
            episode: Episode object or dictionary with metadata
            transcript_sample: Sample from the transcript for context
            
        Returns:
            Dictionary with identified potential speakers
        """
        # Convert episode to dictionary if needed
        episode_metadata = {}
        if hasattr(episode, 'to_dict'):
            episode_metadata = episode.to_dict()
        elif hasattr(episode, '__dict__'):
            episode_metadata = episode.__dict__
        else:
            episode_metadata = {
                "title": getattr(episode, "title", ""),
                "description": getattr(episode, "description", ""),
                "published_at": getattr(episode, "published_at", ""),
                "tags": getattr(episode, "tags", []),
                "video_id": getattr(episode, "video_id", "")
            }
        
        return self.provider.extract_speakers(episode_metadata, transcript_sample)
    
    def extract_opinions_from_transcript(self, system_prompt: str, prompt: str, episode_metadata: Dict) -> Dict:
        """
        Extract opinions from transcript using LLM.
        
        Args:
            system_prompt: The system prompt providing instructions
            prompt: The user prompt with transcript content
            episode_metadata: Dictionary with episode metadata for context
            
        Returns:
            Dictionary with extracted opinions
        """
        return self.provider.extract_opinions_from_transcript(system_prompt, prompt, episode_metadata)
    
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
    
    def call_simple(self, system_prompt: str, prompt: str) -> Any:
        """
        Make a simple call to the LLM with system and user prompts.
        
        Args:
            system_prompt: System prompt providing instructions
            prompt: User prompt with content
            
        Returns:
            LLM response data
        """
        try:
            # For now, we'll reuse the opinion extraction method but with a simpler structure
            # This assumes the LLM providers already have similar processing logic
            dummy_metadata = {"title": "Simple Call", "description": "Direct LLM call"}
            response = self.provider.extract_opinions_from_transcript(
                system_prompt=system_prompt,
                prompt=prompt,
                episode_metadata=dummy_metadata
            )
            return response
        except Exception as e:
            logger.error(f"Error in simple LLM call: {e}")
            return {} 