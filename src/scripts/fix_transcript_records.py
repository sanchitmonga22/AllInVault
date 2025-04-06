#!/usr/bin/env python3

import json
import os
from pathlib import Path
from typing import Dict, List, Set

def load_episodes() -> List[Dict]:
    with open('data/json/episodes.json', 'r') as f:
        return json.load(f)

def get_transcript_files() -> Set[str]:
    transcript_dir = Path('data/transcripts')
    json_files = {f.stem for f in transcript_dir.glob('*.json')}
    txt_files = {f.stem for f in transcript_dir.glob('*.txt')}
    return json_files.intersection(txt_files)  # Only return IDs that have both JSON and TXT

def update_transcript_records(data: Dict, transcript_files: Set[str]) -> int:
    updated_count = 0
    
    for episode in data['episodes']:
        if episode.get('metadata', {}).get('type') != 'FULL':
            continue
            
        video_id = episode['video_id']
        if video_id in transcript_files and not episode.get('transcript_filename'):
            # Update the transcript filename
            episode['transcript_filename'] = f"{video_id}.json"
            updated_count += 1
    
    return updated_count

def main():
    print("Loading episodes.json...")
    data = load_episodes()
    
    print("Getting transcript files...")
    transcript_files = get_transcript_files()
    
    print("Updating transcript records...")
    updated_count = update_transcript_records(data, transcript_files)
    
    if updated_count > 0:
        print(f"Updated {updated_count} episodes. Saving changes...")
        with open('data/json/episodes.json', 'w') as f:
            json.dump(data, f, indent=2)
        print("Done!")
    else:
        print("No updates needed.")

if __name__ == "__main__":
    main() 