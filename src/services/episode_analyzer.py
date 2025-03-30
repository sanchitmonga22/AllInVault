#!/usr/bin/env python3
"""
Service for analyzing podcast episodes to identify shorts vs full episodes.
"""

import json
import re
import os
from pathlib import Path
from datetime import timedelta
from typing import List, Dict, Tuple

class EpisodeAnalyzerService:
    """Service for analyzing podcast episodes."""

    def __init__(self, min_duration: int = 180):
        """
        Initialize the episode analyzer service.
        
        Args:
            min_duration: Minimum duration in seconds for an episode to be considered a full episode
                          (default: 180 seconds = 3 minutes, the maximum length of a YouTube Short)
        """
        self.min_duration = min_duration
    
    def parse_duration(self, duration_str: str) -> int:
        """
        Parse ISO 8601 duration string to seconds.
        
        Args:
            duration_str: ISO 8601 duration string (e.g., "PT1H30M45S")
            
        Returns:
            Total seconds as an integer
        """
        if not duration_str:
            return 0
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
    
    def analyze_episodes(self, episodes_json_path: str = 'data/json/episodes.json', limit: int = 10) -> Tuple[List[Dict], List[Dict]]:
        """
        Analyze episodes to separate full episodes from shorts.
        
        Args:
            episodes_json_path: Path to the episodes JSON file
            limit: Maximum number of episodes to analyze (0 = no limit)
            
        Returns:
            Tuple of (full_episodes, shorts) where each is a list of episode dictionaries
        """
        # Load episodes
        with open(episodes_json_path, 'r') as f:
            data = json.load(f)
        
        episodes_to_analyze = data['episodes'][:limit] if limit > 0 else data['episodes']
        
        full_episodes = []
        shorts = []
        
        for episode in episodes_to_analyze:
            duration_seconds = self.parse_duration(episode['duration'])
            # Add duration_seconds to the episode dict for easier reference
            episode['duration_seconds'] = duration_seconds
            episode_type = 'FULL' if duration_seconds >= self.min_duration else 'SHORT'
            # Add type to the episode dict for easier reference
            episode['type'] = episode_type
            
            if episode_type == 'FULL':
                full_episodes.append(episode)
            else:
                shorts.append(episode)
        
        return full_episodes, shorts
    
    def print_analysis(self, full_episodes: List[Dict], shorts: List[Dict], show_details: bool = True) -> None:
        """
        Print analysis of full episodes and shorts.
        
        Args:
            full_episodes: List of full episode dictionaries
            shorts: List of short episode dictionaries
            show_details: Whether to print detailed information for each episode
        """
        if show_details:
            print('='*80)
            print('EPISODE ANALYSIS')
            print('='*80)
            print(f"{'ID':<15} {'DURATION':<12} {'TYPE':<10} {'TITLE':<40}")
            print('-'*80)
            
            # Print all episodes
            for episode in full_episodes + shorts:
                duration_seconds = episode.get('duration_seconds') or self.parse_duration(episode['duration'])
                duration_str = str(timedelta(seconds=duration_seconds))
                episode_type = episode.get('type') or ('FULL' if duration_seconds >= self.min_duration else 'SHORT')
                print(f"{episode['video_id']:<15} {duration_str:<12} {episode_type:<10} {episode['title'][:40]}")
        
        # Print summary
        print('-'*80)
        print(f'Full episodes: {len(full_episodes)}')
        print(f'Shorts: {len(shorts)}')
        print('='*80)
        
        if show_details:
            print('\nFULL EPISODES:')
            for i, episode in enumerate(full_episodes):
                print(f"{i+1}. {episode['video_id']} - {episode['title']}")
    
    def get_full_episode_ids(self, episodes_json_path: str = 'data/json/episodes.json', limit: int = 10) -> List[str]:
        """
        Get IDs of full episodes.
        
        Args:
            episodes_json_path: Path to the episodes JSON file
            limit: Maximum number of episodes to analyze (0 = no limit)
            
        Returns:
            List of video IDs for full episodes
        """
        full_episodes, _ = self.analyze_episodes(episodes_json_path, limit)
        return [ep['video_id'] for ep in full_episodes]

# Command-line interface
def main():
    """Run episode analysis as a standalone script."""
    analyzer = EpisodeAnalyzerService()
    full_episodes, shorts = analyzer.analyze_episodes()
    analyzer.print_analysis(full_episodes, shorts)
    
    # Return full episode IDs for further processing
    return [ep['video_id'] for ep in full_episodes]

if __name__ == "__main__":
    main() 