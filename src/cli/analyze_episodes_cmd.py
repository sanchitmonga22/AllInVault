#!/usr/bin/env python3
"""
Command-line interface for analyzing podcast episodes.
"""

import sys
import argparse
from src.services.episode_analyzer import EpisodeAnalyzerService

def main():
    """Run episode analysis as a command-line script."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Analyze podcast episodes to identify shorts vs full episodes')
    parser.add_argument('--limit', type=int, default=10,
                        help='Maximum number of episodes to analyze (default: 10)')
    parser.add_argument('--min-duration', type=int, default=180,
                        help='Minimum duration in seconds for an episode to be considered a full episode (default: 180)')
    parser.add_argument('--json-path', type=str, default='data/json/episodes.json',
                        help='Path to the episodes JSON file (default: data/json/episodes.json)')
    
    args = parser.parse_args()
    
    # Initialize analyzer and run analysis
    analyzer = EpisodeAnalyzerService(min_duration=args.min_duration)
    full_episodes, shorts = analyzer.analyze_episodes(
        episodes_json_path=args.json_path, 
        limit=args.limit
    )
    analyzer.print_analysis(full_episodes, shorts)
    
    # Print full episode IDs only if being used programmatically
    if not sys.stdout.isatty():
        # Return full episode IDs for further processing
        print([ep['video_id'] for ep in full_episodes])

if __name__ == "__main__":
    main() 