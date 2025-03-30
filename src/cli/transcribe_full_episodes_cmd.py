#!/usr/bin/env python3
"""
Command-line interface for transcribing full podcast episodes (not YouTube shorts).
"""

import argparse
from src.services.batch_transcriber import BatchTranscriberService

def main():
    """Run batch transcription as a command-line script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Transcribe full podcast episodes (skipping shorts)')
    parser.add_argument('--limit', type=int, default=10,
                        help='Maximum number of episodes to analyze (default: 10)')
    parser.add_argument('--min-duration', type=int, default=180,
                        help='Minimum duration in seconds for an episode to be transcribed (default: 180)')
    parser.add_argument('--json-path', type=str, default='data/json/episodes.json',
                        help='Path to the episodes JSON file (default: data/json/episodes.json)')
    
    args = parser.parse_args()
    
    # Initialize the batch transcriber service
    batch_transcriber = BatchTranscriberService(
        min_duration=args.min_duration
    )
    
    # Transcribe full episodes
    batch_transcriber.transcribe_full_episodes(
        episodes_json_path=args.json_path,
        limit=args.limit
    )

if __name__ == "__main__":
    main() 