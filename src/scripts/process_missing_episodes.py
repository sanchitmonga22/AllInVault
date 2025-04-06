#!/usr/bin/env python3

import json
import subprocess
import time
from typing import Dict, List
import shlex

def load_episodes() -> List[Dict]:
    with open('data/json/episodes.json', 'r') as f:
        data = json.load(f)
        return data['episodes']

def get_missing_speaker_episodes(episodes: List[Dict]) -> List[Dict]:
    return [
        episode for episode in episodes
        if episode.get('metadata', {}).get('type') == 'FULL'
        and 'speakers' not in episode.get('metadata', {})
        and episode.get('transcript_filename')  # Only include episodes with transcripts
    ]

def process_episodes(episodes):
    """Process episodes one at a time."""
    for episode in episodes:
        print(f"Processing episode {episode['video_id']}: {episode['title']}")
        
        # Run speaker identification script for this episode
        cmd = f"PYTHONPATH=. python src/speaker_identification_script.py {shlex.quote(episode['video_id'])} --batch-size 1"
        print(f"Running command: {cmd}")
        
        try:
            subprocess.run(cmd, shell=True, check=True)
            print(f"Successfully processed episode {episode['video_id']}")
            time.sleep(10)  # Add delay between episodes
        except subprocess.CalledProcessError as e:
            print(f"Error processing episode {episode['video_id']}: {e}")
            break  # Stop processing on error

def main():
    # Load episodes from episodes.json
    with open("data/json/episodes.json", "r") as f:
        data = json.load(f)
        episodes = data["episodes"]

    # Filter episodes that need speaker identification
    episodes_to_process = [
        episode for episode in episodes
        if episode.get("metadata", {}).get("type") == "FULL" and  # Only process full episodes
        not episode.get("speaker_count")  # No speaker identification yet
    ]

    print(f"Found {len(episodes_to_process)} episodes that need speaker identification:")
    for episode in episodes_to_process:
        print(f"{episode['video_id']}: {episode['title']}")

    if episodes_to_process:
        print("\nStarting processing...")
        process_episodes(episodes_to_process)
    else:
        print("No episodes need speaker identification.")

if __name__ == "__main__":
    main() 