#!/usr/bin/env python3
"""
Command-line interface for the complete podcast processing pipeline.

This script provides a unified interface to:
1. Download episode metadata
2. Analyze episodes to separate full episodes from shorts
3. Download audio for full episodes
4. Generate transcripts
5. Identify speakers in transcripts
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
        "--skip-speaker-identification", 
        action="store_true",
        help="Skip speaker identification step"
    )
    
    parser.add_argument(
        "--min-duration", 
        type=int,
        default=180,
        help="Minimum duration in seconds for an episode to be considered a full episode (default: 180)"
    )
    
    parser.add_argument(
        "--use-llm", 
        action="store_true",
        help="Use LLM (Large Language Model) for speaker identification (default)"
    )
    
    parser.add_argument(
        "--no-llm", 
        action="store_true",
        help="Disable LLM for speaker identification and use heuristics only"
    )
    
    parser.add_argument(
        "--llm-provider", 
        type=str, 
        choices=["openai", "deepseq"],
        default="openai",
        help="LLM provider to use for speaker identification (default: openai)"
    )
    
    args = parser.parse_args()
    
    try:
        # Resolve conflicting options
        use_llm = not args.no_llm
        
        # Initialize the pipeline service
        pipeline = PodcastPipelineService(
            min_duration_seconds=args.min_duration,
            use_llm_for_speakers=use_llm,
            llm_provider=args.llm_provider
        )
        
        # Run the pipeline
        pipeline.run_pipeline(
            num_episodes=args.num_episodes,
            download_audio=not args.skip_download,
            transcribe=not args.skip_transcription,
            identify_speakers=not args.skip_speaker_identification,
            use_llm_for_speakers=use_llm
        )
        
        return 0
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 