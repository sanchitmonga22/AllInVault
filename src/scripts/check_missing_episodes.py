#!/usr/bin/env python3

import json
from typing import Dict, List
from collections import defaultdict

def load_episodes() -> List[Dict]:
    with open('data/json/episodes.json', 'r') as f:
        data = json.load(f)
        return data['episodes']

def analyze_missing_data(episodes: List[Dict]) -> Dict:
    stats = {
        'total_full_episodes': 0,
        'missing_both': [],
        'missing_speakers': [],
        'missing_transcript': [],
        'fully_processed': [],
        'summary': defaultdict(int)
    }
    
    for episode in episodes:
        # Only analyze FULL episodes
        if episode.get('metadata', {}).get('type') != 'FULL':
            continue
            
        stats['total_full_episodes'] += 1
        video_id = episode['video_id']
        title = episode['title']
        duration = episode.get('metadata', {}).get('duration_seconds', 0)
        
        has_speakers = 'speakers' in episode.get('metadata', {})
        has_transcript = bool(episode.get('transcript_filename'))
        
        episode_info = {
            'video_id': video_id,
            'title': title,
            'duration_minutes': round(duration / 60, 1) if duration else 0,
            'published_at': episode.get('published_at', 'Unknown')
        }
        
        if not has_speakers and not has_transcript:
            stats['missing_both'].append(episode_info)
            stats['summary']['missing_both'] += 1
        elif not has_speakers:
            stats['missing_speakers'].append(episode_info)
            stats['summary']['missing_speakers'] += 1
        elif not has_transcript:
            stats['missing_transcript'].append(episode_info)
            stats['summary']['missing_transcript'] += 1
        else:
            stats['fully_processed'].append(episode_info)
            stats['summary']['fully_processed'] += 1
    
    return stats

def print_missing_report(stats: Dict) -> None:
    print("\n=== Missing Data Analysis for FULL Episodes ===")
    print(f"\nTotal FULL Episodes: {stats['total_full_episodes']}")
    print(f"Fully Processed: {stats['summary']['fully_processed']}")
    print(f"Missing Both (Speakers & Transcript): {stats['summary']['missing_both']}")
    print(f"Missing Only Speakers: {stats['summary']['missing_speakers']}")
    print(f"Missing Only Transcript: {stats['summary']['missing_transcript']}")
    
    def print_episode_list(title: str, episodes: List[Dict]) -> None:
        if not episodes:
            return
        print(f"\n{title} ({len(episodes)}):")
        print("-" * 100)
        print(f"{'Video ID':<15} {'Published':<25} {'Duration':<10} Title")
        print("-" * 100)
        for ep in sorted(episodes, key=lambda x: x['published_at'], reverse=True):
            print(f"{ep['video_id']:<15} {ep['published_at'][:10]:<25} {ep['duration_minutes']:>3}min    {ep['title']}")
    
    print_episode_list("\nEpisodes Missing Both Speakers & Transcript", stats['missing_both'])
    print_episode_list("\nEpisodes Missing Only Speakers", stats['missing_speakers'])
    print_episode_list("\nEpisodes Missing Only Transcript", stats['missing_transcript'])

def main():
    episodes = load_episodes()
    stats = analyze_missing_data(episodes)
    print_missing_report(stats)

if __name__ == "__main__":
    main() 