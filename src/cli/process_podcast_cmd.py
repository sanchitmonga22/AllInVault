#!/usr/bin/env python3
"""
Command-line interface for the complete podcast processing pipeline.

This script provides a unified interface to:
1. Download episode metadata
2. Analyze episodes to separate full episodes from shorts
3. Download audio for full episodes
4. Generate transcripts
"""

import argparse
import sys
from src.services.podcast_pipeline import PodcastPipelineService

def main():
    """Execute the podcast processing pipeline."""
    parser = argparse.ArgumentParser(
        description="Process podcast episodes from download to transcription in one step"
    )
    
    parser.add_argument(
        "-n", "--num-episodes", 
        type=int, 
        default=5,
        help="Number of episodes to process (default: 5)"
    )
    
    parser.add_argument(
        "--skip-download", 
        action="store_true",
        help="Skip audio download and use existing files"
    )
    
    parser.add_argument(
        "--skip-transcription", 
        action="store_true",
        help="Skip transcription step"
    )
    
    parser.add_argument(
        "--min-duration", 
        type=int,
        default=180,
        help="Minimum duration in seconds for an episode to be considered a full episode (default: 180)"
    )
    
    parser.add_argument(
        "--demo", 
        action="store_true",
        help="Use demo mode for transcription (without real audio processing)"
    )
    
    args = parser.parse_args()
    
    try:
        # Initialize the pipeline service
        pipeline = PodcastPipelineService(
            min_duration_seconds=args.min_duration,
            use_demo_mode=args.demo
        )
        
        # Run the pipeline
        pipeline.run_pipeline(
            num_episodes=args.num_episodes,
            download_audio=not args.skip_download,
            transcribe=not args.skip_transcription
        )
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 