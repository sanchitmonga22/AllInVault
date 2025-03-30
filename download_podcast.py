#!/usr/bin/env python3
"""
All In Podcast Downloader

This script downloads all episodes of the All In podcast as audio files
and stores their metadata in a local JSON database.
"""

import argparse
import os
import sys
from typing import List, Optional

from src.models.podcast_episode import PodcastEpisode
from src.repositories.episode_repository import JsonFileRepository
from src.services.downloader_service import PytubeDownloader
from src.services.youtube_service import YouTubeService
from src.utils.config import load_config


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(description="Download All In podcast episodes")
    parser.add_argument(
        "-l", "--limit", 
        type=int, 
        help="Limit the number of episodes to download"
    )
    parser.add_argument(
        "-i", "--info-only", 
        action="store_true", 
        help="Only fetch metadata without downloading audio"
    )
    parser.add_argument(
        "-f", "--format", 
        default="mp3", 
        help="Audio format (default: mp3)"
    )
    parser.add_argument(
        "-q", "--quality", 
        default="192", 
        help="Audio quality in kbps (default: 192)"
    )
    return parser.parse_args()


def main():
    """Main function to download podcast episodes."""
    args = parse_args()
    
    try:
        # Load configuration
        config = load_config()
        
        # Override config with command line arguments if provided
        if args.format:
            config.audio_format = args.format
        if args.quality:
            config.audio_quality = args.quality
        
        # Initialize services and repository
        youtube_service = YouTubeService(config.youtube_api_key)
        downloader = PytubeDownloader(format=config.audio_format, quality=config.audio_quality)
        repository = JsonFileRepository(str(config.episodes_db_path))
        
        print(f"Fetching episodes for channel ID: {config.all_in_channel_id}")
        
        # Get episodes from YouTube
        episodes = youtube_service.get_all_episodes(
            config.all_in_channel_id,
            max_results=args.limit
        )
        
        print(f"Found {len(episodes)} episodes")
        
        # Save episodes metadata to repository
        repository.save_episodes(episodes)
        print(f"Saved episode metadata to {config.episodes_db_path}")
        
        # Download audio if not info-only mode
        if not args.info_only:
            print("Downloading episode audio...")
            updated_episodes = downloader.download_episodes(episodes, str(config.audio_dir))
            
            # Update repository with audio filenames
            repository.save_episodes(updated_episodes)
            print(f"Updated metadata with audio filenames")
        
        print("Done!")
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 