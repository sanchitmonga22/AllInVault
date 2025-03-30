#!/usr/bin/env python3
"""
Transcript Verification Script

This script verifies and updates all episodes to ensure YouTube metadata and transcript information
are properly integrated.
"""

import os
import json
import argparse
from pathlib import Path
from typing import Dict, List, Tuple

from src.models.podcast_episode import PodcastEpisode
from src.repositories.episode_repository import JsonFileRepository
from src.services.episode_analyzer import EpisodeAnalyzerService

def verify_episodes(episodes_json_path: str, transcripts_dir: str) -> Tuple[int, int, int]:
    """
    Verify and update all episodes to ensure YouTube metadata and transcript information are properly integrated.
    
    Args:
        episodes_json_path: Path to the episodes JSON file
        transcripts_dir: Directory containing transcript files
        
    Returns:
        Tuple of (total_episodes, updated_episodes, missing_transcripts)
    """
    # Initialize repository and analyzer
    repository = JsonFileRepository(episodes_json_path)
    analyzer = EpisodeAnalyzerService()
    
    # Get all episodes
    episodes = repository.get_all_episodes()
    print(f"Found {len(episodes)} episodes in repository")
    
    updated_count = 0
    missing_transcripts = 0
    
    for episode in episodes:
        needs_update = False
        
        # Ensure metadata exists
        if not episode.metadata:
            episode.metadata = {}
            needs_update = True
        
        # Parse duration if not already done
        if episode.duration and 'duration_seconds' not in episode.metadata:
            duration_seconds = analyzer.parse_duration(episode.duration)
            if duration_seconds:
                episode.metadata['duration_seconds'] = duration_seconds
                needs_update = True
                print(f"Added duration_seconds to episode {episode.video_id}")
        
        # Check for transcript file
        transcript_path = os.path.join(transcripts_dir, f"{episode.video_id}.json")
        if episode.transcript_filename and os.path.exists(transcript_path):
            # Load transcript data
            try:
                with open(transcript_path, 'r') as f:
                    transcript_data = json.load(f)
                
                # Update transcript metadata
                if 'results' in transcript_data:
                    # Update transcript duration if needed
                    if 'duration' in transcript_data['results'] and (
                        not episode.transcript_duration or 
                        abs(episode.transcript_duration - transcript_data['results']['duration']) > 1
                    ):
                        episode.transcript_duration = transcript_data['results']['duration']
                        needs_update = True
                        print(f"Updated transcript duration for episode {episode.video_id}")
                    
                    # Update utterance count if needed
                    if 'utterances' in transcript_data['results']:
                        utterance_count = len(transcript_data['results']['utterances'])
                        if not episode.transcript_utterances or episode.transcript_utterances != utterance_count:
                            episode.transcript_utterances = utterance_count
                            needs_update = True
                            print(f"Updated utterance count for episode {episode.video_id}")
                
                # Add episode metadata to transcript if needed
                if not 'episode_metadata' in transcript_data:
                    transcript_data['episode_metadata'] = {
                        'video_id': episode.video_id,
                        'title': episode.title,
                        'published_at': episode.published_at.isoformat(),
                        'duration': episode.duration,
                        'duration_seconds': episode.metadata.get('duration_seconds'),
                        'transcript_duration': episode.transcript_duration
                    }
                    # Save updated transcript
                    with open(transcript_path, 'w') as f:
                        json.dump(transcript_data, f, indent=2)
                    print(f"Added episode metadata to transcript {episode.video_id}")
                
                # Calculate coverage if we have both durations
                if episode.transcript_duration and episode.metadata.get('duration_seconds'):
                    coverage = min(100.0, (episode.transcript_duration / episode.metadata['duration_seconds']) * 100)
                    episode.metadata['transcript_coverage'] = round(coverage, 2)
                    needs_update = True
                    print(f"Episode {episode.video_id}: Coverage {episode.metadata['transcript_coverage']}%")
                
                # Update episode type if not set
                if 'type' not in episode.metadata and episode.metadata.get('duration_seconds'):
                    if episode.metadata['duration_seconds'] >= 300:  # 5 minutes
                        episode.metadata['type'] = 'FULL'
                    else:
                        episode.metadata['type'] = 'SHORT'
                    needs_update = True
                    print(f"Set episode type to {episode.metadata['type']} for {episode.video_id}")
            except Exception as e:
                print(f"Error processing transcript for {episode.video_id}: {e}")
        else:
            # Transcript file doesn't exist
            if episode.transcript_filename:
                print(f"Warning: Transcript file missing for episode {episode.video_id}")
            missing_transcripts += 1
        
        # Update episode in repository if needed
        if needs_update:
            repository.update_episode(episode)
            updated_count += 1
    
    return len(episodes), updated_count, missing_transcripts

def generate_stats(episodes_json_path: str) -> Dict:
    """
    Generate statistics about episodes and transcripts.
    
    Args:
        episodes_json_path: Path to the episodes JSON file
        
    Returns:
        Dictionary with statistics
    """
    repository = JsonFileRepository(episodes_json_path)
    episodes = repository.get_all_episodes()
    
    stats = {
        'total_episodes': len(episodes),
        'episodes_with_audio': 0,
        'episodes_with_transcripts': 0,
        'full_episodes': 0,
        'short_episodes': 0,
        'average_coverage': 0,
        'complete_transcripts': 0
    }
    
    coverage_values = []
    
    for episode in episodes:
        if episode.audio_filename:
            stats['episodes_with_audio'] += 1
        
        if episode.transcript_filename:
            stats['episodes_with_transcripts'] += 1
            
            # Get coverage
            if episode.metadata and 'transcript_coverage' in episode.metadata:
                coverage = episode.metadata['transcript_coverage']
                coverage_values.append(coverage)
                
                if coverage >= 90:
                    stats['complete_transcripts'] += 1
        
        # Count episode types
        if episode.metadata and 'type' in episode.metadata:
            if episode.metadata['type'] == 'FULL':
                stats['full_episodes'] += 1
            elif episode.metadata['type'] == 'SHORT':
                stats['short_episodes'] += 1
    
    # Calculate average coverage
    if coverage_values:
        stats['average_coverage'] = sum(coverage_values) / len(coverage_values)
    
    return stats

def print_stats(stats: Dict) -> None:
    """Print statistics in a formatted way."""
    print("\n" + "="*50)
    print("Episode Statistics")
    print("="*50)
    print(f"Total episodes: {stats['total_episodes']}")
    print(f"Episodes with audio: {stats['episodes_with_audio']}")
    print(f"Episodes with transcripts: {stats['episodes_with_transcripts']}")
    print(f"Full episodes: {stats['full_episodes']}")
    print(f"Short episodes: {stats['short_episodes']}")
    print(f"Average transcript coverage: {stats['average_coverage']:.2f}%")
    print(f"Complete transcripts (>=90%): {stats['complete_transcripts']}")
    print("="*50)

def main():
    parser = argparse.ArgumentParser(description="Verify and update transcript metadata")
    parser.add_argument("--episodes", default="data/json/episodes.json", help="Path to episodes JSON file")
    parser.add_argument("--transcripts", default="data/transcripts", help="Path to transcripts directory")
    parser.add_argument("--stats-only", action="store_true", help="Only show statistics, don't update episodes")
    
    args = parser.parse_args()
    
    if not args.stats_only:
        print(f"Verifying episodes in {args.episodes}")
        total, updated, missing = verify_episodes(args.episodes, args.transcripts)
        print(f"\nVerification complete: {total} episodes, {updated} updated, {missing} missing transcripts")
    
    # Generate and print statistics
    stats = generate_stats(args.episodes)
    print_stats(stats)

if __name__ == "__main__":
    main() 