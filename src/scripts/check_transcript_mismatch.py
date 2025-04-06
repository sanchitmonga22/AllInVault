#!/usr/bin/env python3

import json
import os
from typing import Dict, List, Set
from pathlib import Path

def load_episodes() -> List[Dict]:
    with open('data/json/episodes.json', 'r') as f:
        data = json.load(f)
        return data['episodes']

def get_transcript_files() -> Set[str]:
    transcript_dir = Path('data/transcripts')
    json_files = {f.stem for f in transcript_dir.glob('*.json')}
    txt_files = {f.stem for f in transcript_dir.glob('*.txt')}
    return json_files.intersection(txt_files)  # Only return IDs that have both JSON and TXT

def analyze_mismatches(episodes: List[Dict], transcript_files: Set[str]):
    stats = {
        'episodes_missing_speakers': [],
        'episodes_with_transcript_not_recorded': [],
        'episodes_with_transcript_recorded': []
    }
    
    for episode in episodes:
        if episode.get('metadata', {}).get('type') != 'FULL':
            continue
            
        video_id = episode['video_id']
        has_speakers = 'speakers' in episode.get('metadata', {})
        has_transcript_recorded = bool(episode.get('transcript_filename'))
        has_transcript_file = video_id in transcript_files
        
        if not has_speakers:
            stats['episodes_missing_speakers'].append({
                'video_id': video_id,
                'title': episode['title'],
                'has_transcript_file': has_transcript_file,
                'has_transcript_recorded': has_transcript_recorded
            })
            
        if has_transcript_file and not has_transcript_recorded:
            stats['episodes_with_transcript_not_recorded'].append({
                'video_id': video_id,
                'title': episode['title']
            })
        elif has_transcript_file:
            stats['episodes_with_transcript_recorded'].append({
                'video_id': video_id,
                'title': episode['title']
            })
    
    return stats

def print_analysis(stats: Dict):
    print("\n=== Transcript and Speaker Analysis ===")
    
    print("\nEpisodes Missing Speaker Data:")
    print("-" * 100)
    for ep in stats['episodes_missing_speakers']:
        transcript_status = []
        if ep['has_transcript_file']:
            transcript_status.append("Has transcript file")
        if ep['has_transcript_recorded']:
            transcript_status.append("Recorded in episodes.json")
        status = " & ".join(transcript_status) if transcript_status else "No transcript"
        print(f"- {ep['video_id']}: {ep['title']}")
        print(f"  Status: {status}")
    
    if stats['episodes_with_transcript_not_recorded']:
        print("\nEpisodes with Transcript Files but Not Recorded in episodes.json:")
        print("-" * 100)
        for ep in stats['episodes_with_transcript_not_recorded']:
            print(f"- {ep['video_id']}: {ep['title']}")
    
    print(f"\nSummary:")
    print(f"- Total episodes missing speakers: {len(stats['episodes_missing_speakers'])}")
    print(f"- Episodes with unrecorded transcripts: {len(stats['episodes_with_transcript_not_recorded'])}")
    print(f"- Episodes with recorded transcripts: {len(stats['episodes_with_transcript_recorded'])}")

def main():
    print("Loading episodes...")
    episodes = load_episodes()
    
    print("Checking transcript files...")
    transcript_files = get_transcript_files()
    
    print("Analyzing mismatches...")
    stats = analyze_mismatches(episodes, transcript_files)
    print_analysis(stats)

if __name__ == "__main__":
    main() 