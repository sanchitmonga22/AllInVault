#!/usr/bin/env python3
"""
Service for batch transcription of podcast episodes.
"""

import os
import sys
import subprocess
from typing import List, Optional
from src.services.episode_analyzer import EpisodeAnalyzerService

class BatchTranscriberService:
    """Service for batch transcription of podcast episodes."""
    
    def __init__(self, transcription_script_path: str = "transcribe_audio.py", 
                 display_script_path: str = "display_transcript.py",
                 min_duration: int = 60):
        """
        Initialize the batch transcriber service.
        
        Args:
            transcription_script_path: Path to the transcription script
            display_script_path: Path to the display script for readable output
            min_duration: Minimum duration in seconds for an episode to be transcribed
        """
        self.transcription_script_path = transcription_script_path
        self.display_script_path = display_script_path
        self.min_duration = min_duration
        self.analyzer = EpisodeAnalyzerService()
    
    def transcribe_episodes(self, episode_ids: List[str], output_dir: str = "data/transcripts") -> None:
        """
        Transcribe the specified episodes.
        
        Args:
            episode_ids: List of episode IDs to transcribe
            output_dir: Directory to store the transcripts
        """
        os.makedirs(output_dir, exist_ok=True)
        
        print(f"\nStarting transcription of {len(episode_ids)} episodes...")
        print("="*80)
        
        for i, episode_id in enumerate(episode_ids):
            print(f"\nTranscribing episode {i+1}/{len(episode_ids)}: {episode_id}")
            print("-"*80)
            
            # Prepare the transcription command
            cmd = f"python {self.transcription_script_path} --episode {episode_id} --min-duration {self.min_duration}"
            
            # Run the transcription command
            process = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            
            # Stream output
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    print(output.strip())
            
            # Check for errors
            if process.returncode != 0:
                stderr = process.stderr.read()
                print(f"Error: {stderr}", file=sys.stderr)
                continue
        
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
        os.makedirs(output_dir, exist_ok=True)
        
        print("\nGenerating readable transcripts...")
        
        for episode_id in episode_ids:
            transcript_path = f"{input_dir}/{episode_id}.json"
            text_path = f"{output_dir}/{episode_id}.txt"
            
            if os.path.exists(transcript_path):
                # Generate readable text transcript
                cmd = f"python {self.display_script_path} {transcript_path} -o {text_path}"
                subprocess.run(cmd, shell=True)
                print(f"Transcript saved to {text_path}")
            else:
                print(f"Warning: JSON transcript not found for episode {episode_id}")
    
    def transcribe_full_episodes(self, episodes_json_path: str = "data/json/episodes.json", 
                               limit: int = 10) -> None:
        """
        Transcribe only full episodes (not shorts) from the downloaded episodes.
        
        Args:
            episodes_json_path: Path to the episodes JSON file
            limit: Maximum number of episodes to analyze and transcribe
        """
        # Get list of full episode IDs from analysis
        full_episode_ids = self.analyzer.get_full_episode_ids(episodes_json_path, limit)
        
        # Transcribe full episodes
        self.transcribe_episodes(full_episode_ids)
        
        # Generate readable transcripts
        self.generate_readable_transcripts(full_episode_ids)
        
        print("\nTranscription process complete! Transcripts are available in the data/transcripts directory.")

# Command-line interface
def main():
    """Run batch transcription as a standalone script."""
    batch_transcriber = BatchTranscriberService()
    batch_transcriber.transcribe_full_episodes()

if __name__ == "__main__":
    main() 