#!/usr/bin/env python3
"""
Service for batch transcription of podcast episodes.
"""

import os
import json
from typing import List
from pathlib import Path
from src.services.transcription_service import DeepgramTranscriptionService
from src.models.podcast_episode import PodcastEpisode
from src.repositories.episode_repository import JsonFileRepository

class BatchTranscriberService:
    """Service for batch transcription of podcast episodes."""
    
    def __init__(self, api_key: str = None):
        """
        Initialize the batch transcriber service.
        
        Args:
            api_key: Deepgram API key (optional, will use env var if not provided)
        """
        # Use environment variable if no API key provided
        if not api_key:
            api_key = os.getenv('DEEPGRAM_API_KEY')
            
        self.transcription_service = DeepgramTranscriptionService(api_key)
        self.repository = JsonFileRepository('data/json/episodes.json')
    
    def transcribe_episodes(self, episode_ids: List[str], audio_dir: str = "data/audio", transcripts_dir: str = "data/transcripts") -> None:
        """
        Transcribe the specified episodes.
        
        Args:
            episode_ids: List of episode IDs to transcribe
            audio_dir: Directory containing audio files
            transcripts_dir: Directory to store the transcripts
        """
        # Create output directory if it doesn't exist
        Path(transcripts_dir).mkdir(parents=True, exist_ok=True)
        
        print(f"\nStarting transcription of {len(episode_ids)} episodes...")
        print("="*80)
        
        episodes_to_transcribe = []
        for episode_id in episode_ids:
            episode = self.repository.get_episode(episode_id)
            if episode and episode.audio_filename:
                episodes_to_transcribe.append(episode)
            else:
                print(f"Skipping episode {episode_id} - no audio file found")
        
        # Transcribe episodes using our transcription service
        updated_episodes = self.transcription_service.transcribe_episodes(
            episodes_to_transcribe,
            audio_dir,
            transcripts_dir
        )
        
        # Update episodes in repository
        for episode in updated_episodes:
            self.repository.update_episode(episode)
        
        print("\nTranscription complete!")
        print("="*80)
    
    def generate_readable_transcripts(self, episode_ids: List[str], 
                                   input_dir: str = "data/transcripts",
                                   output_dir: str = "data/transcripts") -> None:
        """
        Generate readable text transcripts from JSON transcripts.
        
        Args:
            episode_ids: List of episode IDs to process
            input_dir: Directory containing JSON transcripts
            output_dir: Directory to store readable transcripts
        """
        Path(output_dir).mkdir(parents=True, exist_ok=True)
        
        print("\nGenerating readable transcripts...")
        
        for episode_id in episode_ids:
            json_path = os.path.join(input_dir, f"{episode_id}.json")
            text_path = os.path.join(output_dir, f"{episode_id}.txt")
            
            if not os.path.exists(json_path):
                print(f"Warning: JSON transcript not found for episode {episode_id}")
                continue
                
            try:
                # Read JSON transcript
                with open(json_path, 'r') as f:
                    transcript = json.load(f)
                
                # Generate readable text
                with open(text_path, 'w') as f:
                    if ('results' in transcript and 
                        'channels' in transcript['results'] and 
                        transcript['results']['channels'] and
                        'alternatives' in transcript['results']['channels'][0] and
                        transcript['results']['channels'][0]['alternatives']):
                        
                        # Get the transcript data
                        transcript_data = transcript['results']['channels'][0]['alternatives'][0]
                        
                        # Get speaker mapping if available
                        speaker_map = {}
                        if 'metadata' in transcript and 'speakers' in transcript['metadata']:
                            for speaker in transcript['metadata']['speakers']:
                                speaker_map[speaker.get('id')] = speaker.get('name', f"Speaker {speaker.get('id')}")
                        
                        # Write each word with its speaker
                        current_speaker = None
                        current_text = []
                        current_start = None
                        
                        for word in transcript_data.get('words', []):
                            speaker = word.get('speaker', None)
                            
                            # If speaker changes or this is the first word, write the previous segment
                            if speaker != current_speaker and current_text:
                                speaker_name = speaker_map.get(current_speaker, f"Speaker {current_speaker}")
                                f.write(f"[{current_start:.1f}] {speaker_name}: {' '.join(current_text)}\n")
                                current_text = []
                            
                            # Start new segment if needed
                            if current_text == []:
                                current_start = word.get('start', 0)
                                current_speaker = speaker
                            
                            # Add word to current segment
                            current_text.append(word.get('punctuated_word', word.get('word', '')))
                        
                        # Write final segment if any
                        if current_text:
                            speaker_name = speaker_map.get(current_speaker, f"Speaker {current_speaker}")
                            f.write(f"[{current_start:.1f}] {speaker_name}: {' '.join(current_text)}\n")
                    else:
                        f.write("No transcript data found\n")
                        
                print(f"Generated readable transcript: {text_path}")
                
            except Exception as e:
                print(f"Error processing transcript for episode {episode_id}: {e}")
                continue

# Command-line interface
def main():
    """Run batch transcription as a standalone script."""
    batch_transcriber = BatchTranscriberService()
    batch_transcriber.transcribe_episodes()

if __name__ == "__main__":
    main() 