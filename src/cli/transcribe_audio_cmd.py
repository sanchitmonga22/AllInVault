#!/usr/bin/env python3
"""
Command-line interface for transcribing All In podcast episodes.
"""

import argparse
import sys
import re
from datetime import timedelta

from src.repositories.episode_repository import JsonFileRepository
from src.services.transcription_service import DeepgramTranscriptionService
from src.utils.config import load_config

def parse_duration(duration_str: str) -> int:
    """
    Parse a duration string in ISO 8601 format (e.g., PT1H30M15S) to seconds.
    
    Args:
        duration_str: Duration string in ISO 8601 format
        
    Returns:
        Total seconds as an integer
    """
    if not duration_str:
        return 0
        
    # For formats like 'PT1H30M15S'
    hours = re.search(r'(\d+)H', duration_str)
    minutes = re.search(r'(\d+)M', duration_str)
    seconds = re.search(r'(\d+)S', duration_str)
    
    total_seconds = 0
    if hours:
        total_seconds += int(hours.group(1)) * 3600
    if minutes:
        total_seconds += int(minutes.group(1)) * 60
    if seconds:
        total_seconds += int(seconds.group(1))
        
    return total_seconds

def main():
    """Main function to transcribe podcast episodes."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Transcribe All In podcast episodes")
    parser.add_argument(
        "-l", "--limit", 
        type=int, 
        help="Limit the number of episodes to transcribe"
    )
    parser.add_argument(
        "-e", "--episode", 
        type=str, 
        help="Transcribe only a specific episode by video ID"
    )
    parser.add_argument(
        "--language", 
        default=None, 
        help="Language code for transcription (default from config)"
    )
    parser.add_argument(
        "--model", 
        default=None, 
        help="Deepgram model to use (default from config)"
    )
    parser.add_argument(
        "--demo", 
        action="store_true", 
        help="Use demo mode to generate sample transcripts without real audio"
    )
    parser.add_argument(
        "--min-duration",
        type=int,
        default=180,
        help="Minimum duration in seconds to consider an episode for transcription (default: 180s)"
    )
    args = parser.parse_args()
    
    try:
        # Load configuration
        config = load_config()
        
        # Check if Deepgram API key is available if not in demo mode
        if not args.demo and not config.deepgram_api_key:
            print("Error: DEEPGRAM_API_KEY not found in environment variables", file=sys.stderr)
            print("Use --demo flag to run in demo mode without an API key")
            return 1
        
        # Override config with command line arguments if provided
        language = args.language or config.deepgram_language
        model = args.model or config.deepgram_model
        
        # Initialize services and repository
        transcription_service = DeepgramTranscriptionService(
            api_key=config.deepgram_api_key if not args.demo else None,
            language=language,
            model=model,
            demo_mode=args.demo
        )
        repository = JsonFileRepository(str(config.episodes_db_path))
        
        # Get episodes from repository
        all_episodes = repository.get_all_episodes()
        print(f"Found {len(all_episodes)} episodes in the repository")
        
        # Filter episodes that have audio files
        episodes_with_audio = [ep for ep in all_episodes if ep.audio_filename]
        print(f"{len(episodes_with_audio)} episodes have audio files")
        
        # Filter out YouTube Shorts based on duration
        min_duration_seconds = args.min_duration
        episodes_with_sufficient_duration = []
        
        for episode in episodes_with_audio:
            if not episode.duration:
                print(f"Warning: Episode {episode.title} has no duration metadata, skipping")
                continue
                
            duration_seconds = parse_duration(episode.duration)
            
            if duration_seconds < min_duration_seconds:
                print(f"Skipping {episode.title} (duration: {str(timedelta(seconds=duration_seconds))}) - likely a YouTube Short")
                continue
                
            episodes_with_sufficient_duration.append(episode)
        
        print(f"{len(episodes_with_sufficient_duration)} episodes have sufficient duration (≥ {str(timedelta(seconds=min_duration_seconds))})")
        
        # Filter episodes by video ID if specified
        if args.episode:
            episode_obj = repository.get_episode(args.episode)
            if not episode_obj:
                print(f"No episode found with video ID: {args.episode}")
                return 1
                
            if not episode_obj.audio_filename:
                print(f"Episode {episode_obj.title} has no audio file")
                return 1
                
            if episode_obj.duration:
                duration_seconds = parse_duration(episode_obj.duration)
                if duration_seconds < min_duration_seconds:
                    print(f"Warning: Episode {episode_obj.title} is only {str(timedelta(seconds=duration_seconds))} long (likely a YouTube Short)")
                    if input("Transcribe anyway? (y/n): ").lower() != 'y':
                        return 0
                        
            episodes_to_transcribe = [episode_obj]
            print(f"Transcribing 1 specific episode: {episodes_to_transcribe[0].title}")
        else:
            episodes_to_transcribe = episodes_with_sufficient_duration
            
        # Apply limit if specified
        if args.limit and args.limit > 0:
            episodes_to_transcribe = episodes_to_transcribe[:args.limit]
            print(f"Limiting to {args.limit} episodes")
        
        print(f"Ready to transcribe {len(episodes_to_transcribe)} episodes")
        
        # Indicate if running in demo mode
        if args.demo:
            print("Running in DEMO MODE: Will generate sample transcripts without real audio processing")
        
        # Transcribe episodes
        updated_episodes = transcription_service.transcribe_episodes(
            episodes_to_transcribe, 
            str(config.audio_dir), 
            str(config.transcripts_dir)
        )
        
        # Update repository with transcription information
        repository.save_episodes(updated_episodes)
        print(f"Updated episode metadata with transcription information")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 