#!/usr/bin/env python3
"""
Command-line interface for verifying transcript completeness.
This script checks all existing transcripts against their episode durations
and updates the episode metadata with completeness information.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any
from tqdm import tqdm

from src.models.podcast_episode import PodcastEpisode


def duration_to_seconds(duration_str: str) -> int:
    """
    Convert ISO 8601 duration string to seconds.
    
    Args:
        duration_str: Duration string in ISO 8601 format (e.g., PT1H28M)
        
    Returns:
        Duration in seconds
    """
    if not duration_str:
        return 0
        
    # Try format PT(\d+)H(\d+)M(\d+)S
    match = re.match(r'PT(\d+)H(\d+)M(\d+)S', duration_str)
    if match:
        hours, minutes, seconds = map(int, match.groups())
        return hours * 3600 + minutes * 60 + seconds
    
    # Try format PT(\d+)H(\d+)M
    match = re.match(r'PT(\d+)H(\d+)M', duration_str)
    if match:
        hours, minutes = map(int, match.groups())
        return hours * 3600 + minutes * 60
    
    # Try format PT(\d+)M(\d+)S
    match = re.match(r'PT(\d+)M(\d+)S', duration_str)
    if match:
        minutes, seconds = map(int, match.groups())
        return minutes * 60 + seconds
        
    # Try format PT(\d+)M
    match = re.match(r'PT(\d+)M', duration_str)
    if match:
        minutes = int(match.groups()[0])
        return minutes * 60
        
    # Try format PT(\d+)S
    match = re.match(r'PT(\d+)S', duration_str)
    if match:
        return int(match.groups()[0])
        
    # If all else fails, return 0
    return 0


def verify_transcript_completeness(transcript_data: Dict, episode_duration: Optional[int] = None) -> Dict[str, Any]:
    """
    Verify whether a transcript appears to be complete.
    
    Args:
        transcript_data: The transcript data to verify
        episode_duration: Optional duration in seconds from the episode metadata
        
    Returns:
        Dictionary with verification results:
        {
            "is_complete": bool,
            "coverage_percent": float,
            "reason": str
        }
    """
    result = {
        "is_complete": False,
        "coverage_percent": 0.0,
        "reason": ""
    }
    
    # Check transcript duration vs episode duration
    if "results" in transcript_data and "duration" in transcript_data["results"]:
        transcript_duration = transcript_data["results"]["duration"]
        
        if episode_duration:
            # Calculate coverage
            coverage = min(100.0, (transcript_duration / episode_duration) * 100)
            result["coverage_percent"] = coverage
            
            if coverage < 90:
                result["reason"] = f"Transcript only covers {coverage:.1f}% of episode duration"
                return result
        
        # Even without episode_duration, check if transcript is suspiciously short
        if transcript_duration < 300:  # Less than 5 minutes
            result["reason"] = f"Transcript duration ({transcript_duration}s) is suspiciously short"
            return result
    
    # Check number of utterances
    if "results" in transcript_data and "utterances" in transcript_data["results"]:
        utterances = transcript_data["results"]["utterances"]
        if len(utterances) < 10:  # Arbitrary minimum for a real episode
            result["reason"] = f"Too few utterances ({len(utterances)}) for a complete transcript"
            return result
    
    # If no issues found, consider it complete
    result["is_complete"] = True
    return result


def update_transcript_metadata(transcript_path: str, episode: PodcastEpisode) -> Dict:
    """
    Update transcript metadata with episode information and completeness check.
    
    Args:
        transcript_path: Path to the transcript JSON file
        episode: Associated PodcastEpisode instance
        
    Returns:
        Updated transcript data dictionary
    """
    with open(transcript_path, 'r') as f:
        transcript_data = json.load(f)
    
    # Add episode information to metadata if not present
    if 'metadata' not in transcript_data:
        transcript_data['metadata'] = {}
    
    # Add/update episode info
    episode_seconds = duration_to_seconds(episode.duration)
    transcript_data['metadata']['episode_info'] = {
        'video_id': episode.video_id,
        'title': episode.title,
        'duration': episode.duration,
        'duration_seconds': episode_seconds,
        'published_at': episode.published_at.isoformat()
    }
    
    # Save updated transcript
    with open(transcript_path, 'w') as f:
        json.dump(transcript_data, f, indent=2)
    
    return transcript_data


def verify_and_update_episodes(episodes_json_path: str, transcripts_dir: str) -> None:
    """
    Verify and update completeness information for all episodes with transcripts.
    
    Args:
        episodes_json_path: Path to the episodes JSON file
        transcripts_dir: Directory containing transcript files
    """
    # Load episodes
    with open(episodes_json_path, 'r') as f:
        episodes_data = json.load(f)
    
    episodes = []
    for episode_data in episodes_data.get('episodes', []):
        episodes.append(PodcastEpisode.from_dict(episode_data))
    
    print(f"Loaded {len(episodes)} episodes")
    
    # Track statistics
    stats = {
        "total": 0,
        "has_transcript": 0,
        "complete": 0,
        "incomplete": 0,
        "avg_coverage": 0.0
    }
    
    # Process episodes with transcripts
    episodes_to_update = []
    total_coverage = 0.0
    
    for episode in tqdm(episodes, desc="Verifying transcripts"):
        stats["total"] += 1
        
        if not episode.transcript_filename:
            continue
        
        stats["has_transcript"] += 1
        
        # Get transcript path
        transcript_path = os.path.join(transcripts_dir, episode.transcript_filename)
        
        if not os.path.exists(transcript_path):
            print(f"Warning: Transcript file {episode.transcript_filename} not found for {episode.title}")
            continue
        
        # Update transcript metadata
        transcript_data = update_transcript_metadata(transcript_path, episode)
        
        # Verify transcript completeness
        episode_seconds = duration_to_seconds(episode.duration)
        verification = verify_transcript_completeness(transcript_data, episode_seconds)
        
        # Update episode metadata with verification results
        if 'metadata' not in episode.metadata:
            episode.metadata = {}
        
        episode.metadata['transcript'] = {
            'is_complete': verification['is_complete'],
            'coverage_percent': verification['coverage_percent'],
            'reason': verification['reason']
        }
        
        # Update transcript information
        if 'results' in transcript_data:
            if 'duration' in transcript_data['results']:
                episode.transcript_duration = transcript_data['results']['duration']
            
            if 'utterances' in transcript_data['results']:
                episode.transcript_utterances = len(transcript_data['results']['utterances'])
        
        # Update statistics
        if verification['is_complete']:
            stats["complete"] += 1
        else:
            stats["incomplete"] += 1
            print(f"Incomplete transcript for {episode.title}: {verification['reason']}")
        
        total_coverage += verification['coverage_percent']
        episodes_to_update.append(episode)
    
    # Calculate average coverage
    if stats["has_transcript"] > 0:
        stats["avg_coverage"] = total_coverage / stats["has_transcript"]
    
    # Save updated episodes
    episodes_data['episodes'] = [episode.to_dict() for episode in episodes]
    with open(episodes_json_path, 'w') as f:
        json.dump(episodes_data, f, indent=2)
    
    # Print statistics
    print("\nTranscript Verification Summary:")
    print(f"Total episodes: {stats['total']}")
    print(f"Episodes with transcripts: {stats['has_transcript']}")
    print(f"Complete transcripts: {stats['complete']}")
    print(f"Incomplete transcripts: {stats['incomplete']}")
    print(f"Average coverage: {stats['avg_coverage']:.1f}%")


def main():
    """Main function for verifying transcript completeness."""
    parser = argparse.ArgumentParser(
        description="Verify transcript completeness and update episode metadata"
    )
    parser.add_argument(
        "--episodes",
        default="data/json/episodes.json",
        help="Path to episodes JSON file (default: data/json/episodes.json)"
    )
    parser.add_argument(
        "--transcripts",
        default="data/transcripts",
        help="Directory containing transcript files (default: data/transcripts)"
    )
    args = parser.parse_args()
    
    try:
        verify_and_update_episodes(args.episodes, args.transcripts)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main()) 