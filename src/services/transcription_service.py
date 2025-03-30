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
    
    def __init__(self, api_key: str, language: str = "en-US", model: str = "nova", max_speakers: int = 6):
        """
        Initialize the DeepgramTranscriptionService.
        
        Args:
            api_key: Deepgram API key
            language: Language code for transcription
            model: Deepgram model to use
            max_speakers: Maximum number of potential speakers to account for (default: 6)
        """
        self.deepgram = Deepgram(api_key) if api_key else None
        self.language = language
        self.model = model
        self.max_speakers = max_speakers
    
    def _extract_speaker_metadata(self, transcript_data: Dict) -> List[Dict[str, Any]]:
        """
        Extract speaker metadata from a transcript.
        Attempts to identify the likely hosts based on speaker patterns.
        
        Args:
            transcript_data: Transcript data from Deepgram
            
        Returns:
            List of speaker information dictionaries
        """
        if not transcript_data or 'results' not in transcript_data or 'utterances' not in transcript_data['results']:
            return []
            
        # Count speaker occurrences and speaking time
        speaker_stats = {}
        for utterance in transcript_data['results']['utterances']:
            speaker_id = utterance.get('speaker', None)
            if speaker_id is None:
                continue
                
            duration = utterance.get('end', 0) - utterance.get('start', 0)
            
            if speaker_id not in speaker_stats:
                speaker_stats[speaker_id] = {
                    'count': 0,
                    'total_time': 0,
                    'text': ''
                }
                
            speaker_stats[speaker_id]['count'] += 1
            speaker_stats[speaker_id]['total_time'] += duration
            
            # Collect a sample of text from each speaker (limit to avoid huge samples)
            if len(speaker_stats[speaker_id]['text']) < 1000:
                speaker_stats[speaker_id]['text'] += utterance.get('text', '') + ' '
        
        # Sort speakers by total speaking time
        sorted_speakers = sorted(
            [(speaker_id, stats) for speaker_id, stats in speaker_stats.items()],
            key=lambda x: x[1]['total_time'],
            reverse=True
        )
        
        # Generate speaker metadata
        speakers = []
        for i, (speaker_id, stats) in enumerate(sorted_speakers):
            # Try to identify if this is one of the main hosts
            is_host = False
            host_name = None
            
            # For real transcription, check text for mentions of host names
            text = stats['text'].lower()
            for host_key, host_data in DEFAULT_HOSTS.items():
                if host_key in text or host_data['full_name'].lower() in text:
                    host_name = host_data['full_name']
                    is_host = True
                    break
                if 'alt_name' in host_data and host_data['alt_name'].lower() in text:
                    host_name = host_data['full_name']
                    is_host = True
                    break
            
            # Default naming if no host identified
            if not host_name:
                if i < 4:  # First 4 speakers might be hosts
                    # Use order-based host assignment as a fallback
                    hosts_by_order = ["Chamath", "Jason", "David Sacks", "David Friedberg"]
                    host_name = hosts_by_order[i]
                    is_host = True
                else:
                    # For additional speakers, mark as guests
                    host_name = f"Guest {i-3}"
                    is_host = False
            
            speakers.append({
                'id': speaker_id,
                'name': host_name,
                'is_host': is_host,
                'speaking_time': stats['total_time'],
                'utterance_count': stats['count']
            })
        
        return speakers
    
    def verify_transcript_completeness(self, transcript_data: Dict, episode_duration: Optional[int] = None) -> Dict[str, Any]:
        """
        Verify whether a transcript appears to be complete.
        
        Args:
            transcript_data: The transcript data to verify
            episode_duration: Optional duration in seconds from the episode metadata
            
        Returns:
            Dictionary with verification results:
            {
                "is_complete": bool,
                "coverage_percent": float,
                "reason": str
            }
        """
        result = {
            "is_complete": False,
            "coverage_percent": 0.0,
            "reason": ""
        }
        
        # Check transcript duration vs episode duration
        if "results" in transcript_data and "duration" in transcript_data["results"]:
            transcript_duration = transcript_data["results"]["duration"]
            
            if episode_duration:
                # Convert ISO 8601 duration to seconds if needed
                if isinstance(episode_duration, str):
                    match = re.match(r'PT(\d+)H(\d+)M(\d+)S', episode_duration)
                    if match:
                        hours, minutes, seconds = map(int, match.groups())
                        episode_seconds = hours * 3600 + minutes * 60 + seconds
                    else:
                        # Try simpler format PT(\d+)M(\d+)S
                        match = re.match(r'PT(\d+)M(\d+)S', episode_duration)
                        if match:
                            minutes, seconds = map(int, match.groups())
                            episode_seconds = minutes * 60 + seconds
                        else:
                            # Try even simpler format PT(\d+)S
                            match = re.match(r'PT(\d+)S', episode_duration)
                            if match:
                                episode_seconds = int(match.groups()[0])
                            else:
                                episode_seconds = episode_duration
                else:
                    episode_seconds = episode_duration
                
                # Calculate coverage
                coverage = min(100.0, (transcript_duration / episode_seconds) * 100)
                result["coverage_percent"] = coverage
                
                if coverage < 90:
                    result["reason"] = f"Transcript only covers {coverage:.1f}% of episode duration"
                    return result
            
            # Even without episode_duration, check if transcript is suspiciously short
            if transcript_duration < 300:  # Less than 5 minutes
                result["reason"] = f"Transcript duration ({transcript_duration}s) is suspiciously short"
                return result
        
        # Check number of utterances
        if "results" in transcript_data and "utterances" in transcript_data["results"]:
            utterances = transcript_data["results"]["utterances"]
            if len(utterances) < 10:  # Arbitrary minimum for a real episode
                result["reason"] = f"Too few utterances ({len(utterances)}) for a complete transcript"
                return result
        
        # If no issues found, consider it complete
        result["is_complete"] = True
        return result
    
    def transcribe_audio(self, audio_path: str) -> Dict:
        """
        Transcribe an audio file using Deepgram API.
        
        Args:
            audio_path: Path to the audio file
            
        Returns:
            Dictionary with transcription data
        """
        # Regular operation using Deepgram API
        with open(audio_path, 'rb') as audio:
            source = {'buffer': audio, 'mimetype': 'audio/mp3'}
            options = {
                'punctuate': True, 
                'diarize': True,
                'utterances': True,
                'smart_format': True,
                'model': self.model,
                'language': self.language,
                'diarize_version': 'latest',
                'numerals': True,
                'detect_topics': True,
                'max_speakers': self.max_speakers
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
        # Skip if episode has no audio filename
        if not episode.audio_filename:
            print(f"Episode {episode.title} has no audio file")
            return episode
        
        # Prepare paths
        audio_path = os.path.join(audio_dir, episode.audio_filename)
        transcript_filename = f"{os.path.splitext(episode.audio_filename)[0]}.json"
        transcript_path = os.path.join(transcripts_dir, transcript_filename)
        
        # Create transcripts directory if it doesn't exist
        Path(transcripts_dir).mkdir(parents=True, exist_ok=True)
        
        # Check if transcript already exists
        transcript_data = None
        if os.path.exists(transcript_path):
            print(f"Transcript already exists for {episode.title}")
            with open(transcript_path, 'r') as f:
                transcript_data = json.load(f)
            
            # Verify if the existing transcript is complete
            verification = self.verify_transcript_completeness(transcript_data, episode.duration)
            
            # If not complete, we might want to regenerate it
            if not verification["is_complete"]:
                print(f"WARNING: {episode.title} has an incomplete transcript: {verification['reason']}")
                print(f"Coverage: {verification['coverage_percent']:.1f}%")
                
                # Optionally, add logic here to force regeneration if coverage is too low
                # For now, we'll just warn the user
        
        # Transcribe if we don't have data yet
        if transcript_data is None:
            # Transcribe the audio
            print(f"Transcribing {episode.title}...")
            try:
                transcript_data = self.transcribe_audio(audio_path)
                
                # Extract speaker metadata and add to transcript
                speakers = self._extract_speaker_metadata(transcript_data)
                if speakers:
                    # Add speaker mapping to transcript data
                    if 'metadata' not in transcript_data:
                        transcript_data['metadata'] = {}
                    transcript_data['metadata']['speakers'] = speakers
                
                # Add episode information to transcript metadata
                if 'metadata' not in transcript_data:
                    transcript_data['metadata'] = {}
                
                transcript_data['metadata']['episode_info'] = {
                    'video_id': episode.video_id,
                    'title': episode.title,
                    'duration': episode.duration,
                    'duration_seconds': self._duration_to_seconds(episode.duration),
                    'published_at': episode.published_at.isoformat()
                }
                
                # Save the transcript to file
                with open(transcript_path, 'w') as f:
                    json.dump(transcript_data, f, indent=2)
            except Exception as e:
                print(f"Error transcribing {episode.title}: {e}")
                # Just re-raise the exception - no fallback to demo mode
                raise
        
        # Update the episode with transcript information
        episode.transcript_filename = transcript_filename
        
        # Extract some metadata from the transcript
        if transcript_data and 'results' in transcript_data:
            # Total duration from the transcript
            if 'duration' in transcript_data['results']:
                episode.transcript_duration = transcript_data['results']['duration']
            
            # Number of paragraphs/utterances
            if 'utterances' in transcript_data['results']:
                episode.transcript_utterances = len(transcript_data['results']['utterances'])
            
            # Extract detected speaker count 
            if 'metadata' in transcript_data and 'speakers' in transcript_data['metadata']:
                episode.speaker_count = len(transcript_data['metadata']['speakers'])
            
            # Verify and store transcript completeness
            verification = self.verify_transcript_completeness(transcript_data, episode.duration)
            if 'metadata' not in episode.metadata:
                episode.metadata['transcript'] = {}
            
            episode.metadata['transcript'] = {
                'is_complete': verification['is_complete'],
                'coverage_percent': verification['coverage_percent'],
                'reason': verification['reason']
            }
        
        return episode
    
    def _duration_to_seconds(self, duration_str: str) -> int:
        """
        Convert ISO 8601 duration string to seconds.
        
        Args:
            duration_str: Duration string in ISO 8601 format (e.g., PT1H28M)
            
        Returns:
            Duration in seconds
        """
        if not duration_str:
            return 0
            
        # Try format PT(\d+)H(\d+)M(\d+)S
        match = re.match(r'PT(\d+)H(\d+)M(\d+)S', duration_str)
        if match:
            hours, minutes, seconds = map(int, match.groups())
            return hours * 3600 + minutes * 60 + seconds
        
        # Try format PT(\d+)H(\d+)M
        match = re.match(r'PT(\d+)H(\d+)M', duration_str)
        if match:
            hours, minutes = map(int, match.groups())
            return hours * 3600 + minutes * 60
        
        # Try format PT(\d+)M(\d+)S
        match = re.match(r'PT(\d+)M(\d+)S', duration_str)
        if match:
            minutes, seconds = map(int, match.groups())
            return minutes * 60 + seconds
            
        # Try format PT(\d+)M
        match = re.match(r'PT(\d+)M', duration_str)
        if match:
            minutes = int(match.groups()[0])
            return minutes * 60
            
        # Try format PT(\d+)S
        match = re.match(r'PT(\d+)S', duration_str)
        if match:
            return int(match.groups()[0])
            
        # If all else fails, return 0
        return 0
    
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