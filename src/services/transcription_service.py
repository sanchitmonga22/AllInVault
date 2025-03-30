"""
Transcription Service

This module provides interfaces and implementations for audio transcription services.
"""

import os
import json
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import datetime
import re

from deepgram import Deepgram
from tqdm import tqdm

from src.models.podcast_episode import PodcastEpisode


# Default mapping of the 4 main hosts of All In Podcast
DEFAULT_HOSTS = {
    "chamath": {"id": 0, "full_name": "Chamath Palihapitiya"},
    "jason": {"id": 1, "full_name": "Jason Calacanis"},
    "david": {"id": 2, "full_name": "David Sacks", "alt_name": "Sacks"},
    "friedberg": {"id": 3, "full_name": "David Friedberg"}
}


class TranscriptionServiceInterface(ABC):
    """Interface for transcription services."""
    
    @abstractmethod
    def transcribe_audio(self, audio_path: str) -> Dict:
        """
        Transcribe an audio file and return the transcript data.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary with transcription data
        """
        pass
    
    @abstractmethod
    def transcribe_episode(self, episode: PodcastEpisode, audio_dir: str, transcripts_dir: str) -> PodcastEpisode:
        """
        Transcribe an episode's audio file and update the episode with transcript data.
        
        Args:
            episode: PodcastEpisode instance to transcribe
            audio_dir: Directory containing audio files
            transcripts_dir: Directory to save transcript files
            
        Returns:
            Updated PodcastEpisode with transcript information
        """
        pass
    
    @abstractmethod
    def transcribe_episodes(self, episodes: List[PodcastEpisode], audio_dir: str, transcripts_dir: str) -> List[PodcastEpisode]:
        """
        Transcribe multiple episodes and update them with transcript data.
        
        Args:
            episodes: List of PodcastEpisode instances to transcribe
            audio_dir: Directory containing audio files
            transcripts_dir: Directory to save transcript files
            
        Returns:
            List of updated PodcastEpisode instances with transcript information
        """
        pass


class DeepgramTranscriptionService(TranscriptionServiceInterface):
    """Transcription service using Deepgram API."""
    
    def __init__(self, api_key: str):
        """
        Initialize the DeepgramTranscriptionService.
        
        Args:
            api_key: Deepgram API key
        """
        self.deepgram = Deepgram(api_key) if api_key else None
    
    def transcribe_audio(self, audio_path: str) -> Dict:
        """
        Transcribe an audio file using Deepgram API.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary with transcription data
        """
        with open(audio_path, 'rb') as audio:
            source = {'buffer': audio, 'mimetype': 'audio/mp3'}
            options = {
                'model': 'nova-3',
                'smart_format': True,
                'diarize': True,
                'punctuate': True,
                'utterances': True,
                'language': 'en-US'
            }
            
            # Call the Deepgram API
            response = self.deepgram.transcription.sync_prerecorded(source, options)
            return response
    
    def transcribe_episode(self, episode: PodcastEpisode, audio_dir: str, transcripts_dir: str) -> PodcastEpisode:
        """
        Transcribe a podcast episode and save the transcript.
        
        Args:
            episode: PodcastEpisode to transcribe
            audio_dir: Directory containing audio files
            transcripts_dir: Directory to save transcript files
            
        Returns:
            Updated PodcastEpisode with transcript information
        """
        if not episode.audio_filename:
            print(f"Episode {episode.title} has no audio file")
            return episode
        
        audio_path = os.path.join(audio_dir, episode.audio_filename)
        transcript_filename = f"{os.path.splitext(episode.audio_filename)[0]}.json"
        transcript_path = os.path.join(transcripts_dir, transcript_filename)
        
        # Create transcripts directory if it doesn't exist
        Path(transcripts_dir).mkdir(parents=True, exist_ok=True)
        
        try:
            # Transcribe the audio
            print(f"Transcribing {episode.title}...")
            transcript_data = self.transcribe_audio(audio_path)
            
            # Save the transcript to file
            with open(transcript_path, 'w') as f:
                json.dump(transcript_data, f, indent=2)
            
            # Update episode with transcript information
            episode.transcript_filename = transcript_filename
            if transcript_data and 'results' in transcript_data:
                if 'duration' in transcript_data['results']:
                    episode.transcript_duration = transcript_data['results']['duration']
                if 'utterances' in transcript_data['results']:
                    episode.transcript_utterances = len(transcript_data['results']['utterances'])
                
        except Exception as e:
            print(f"Error transcribing {episode.title}: {e}")
            raise
        
        return episode
    
    def transcribe_episodes(self, episodes: List[PodcastEpisode], audio_dir: str, transcripts_dir: str) -> List[PodcastEpisode]:
        """
        Transcribe multiple episodes and update them with transcript data.
        
        Args:
            episodes: List of PodcastEpisode instances to transcribe
            audio_dir: Directory containing audio files
            transcripts_dir: Directory to save transcript files
            
        Returns:
            List of updated PodcastEpisode instances with transcript information
        """
        updated_episodes = []
        
        for episode in tqdm(episodes, desc="Transcribing episodes"):
            updated_episode = self.transcribe_episode(episode, audio_dir, transcripts_dir)
            updated_episodes.append(updated_episode)
        
        return updated_episodes 