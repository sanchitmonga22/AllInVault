#!/usr/bin/env python3
"""
Command-line interface for displaying All In podcast transcripts.
"""

import argparse
import json
import os
import sys
from datetime import timedelta

def format_time(seconds):
    """Format time in seconds to HH:MM:SS format."""
    return str(timedelta(seconds=seconds)).split('.')[0]

def get_speaker_map(transcript):
    """
    Extract speaker mapping from transcript metadata or use default mapping.
    
    Args:
        transcript: Transcript data dictionary
        
    Returns:
        Dictionary mapping speaker IDs to names
    """
    # Default speaker map for the 4 main hosts
    default_map = {
        0: "Chamath",
        1: "Jason",
        2: "Sacks",
        3: "Friedberg"
    }
    
    # Check if we have custom speaker metadata
    if ("metadata" in transcript and 
        "speakers" in transcript["metadata"] and 
        transcript["metadata"]["speakers"]):
        
        speaker_map = {}
        for speaker in transcript["metadata"]["speakers"]:
            speaker_map[speaker.get("id")] = speaker.get("name", f"Speaker {speaker.get('id')}")
        return speaker_map
    
    return default_map

def display_transcript(transcript_path, output=None):
    """
    Display a transcript in a readable format.
    
    Args:
        transcript_path: Path to the transcript JSON file
        output: Optional file path to save the formatted transcript
    """
    # Load the transcript
    with open(transcript_path, 'r') as f:
        transcript = json.load(f)
    
    # Get speaker mapping from transcript metadata
    speaker_map = get_speaker_map(transcript)
    
    # Prepare the formatted output
    formatted_lines = []
    
    # Add header
    formatted_lines.append("-" * 80)
    title = f"Transcript: {os.path.basename(transcript_path)}"
    formatted_lines.append(title.center(80))
    formatted_lines.append("-" * 80)
    
    # Get transcript duration
    transcript_duration = None
    if "results" in transcript and "duration" in transcript["results"]:
        transcript_duration = transcript["results"]["duration"]
        formatted_lines.append(f"Transcript Duration: {format_time(transcript_duration)}")
    
    # Calculate completeness percentage
    episode_duration_seconds = None
    coverage_pct = None
    
    # Check if episode info is in metadata
    if "metadata" in transcript and "episode_info" in transcript["metadata"]:
        episode_info = transcript["metadata"]["episode_info"]
        if "duration_seconds" in episode_info and episode_info["duration_seconds"]:
            episode_duration_seconds = episode_info["duration_seconds"]
            formatted_lines.append(f"Episode Duration: {format_time(episode_duration_seconds)}")
            
            if transcript_duration and episode_duration_seconds > 0:
                coverage_pct = min(100.0, (transcript_duration / episode_duration_seconds) * 100)
                formatted_lines.append(f"Transcript Coverage: {coverage_pct:.1f}%")
                
                if coverage_pct < 90:
                    formatted_lines.append("⚠️  WARNING: TRANSCRIPT IS INCOMPLETE ⚠️".center(80))
    
    # Add metadata about speakers if available
    if "metadata" in transcript and "speakers" in transcript["metadata"]:
        formatted_lines.append("Speakers detected:")
        for speaker in transcript["metadata"]["speakers"]:
            name = speaker.get("name", f"Speaker {speaker.get('id')}")
            role = "Host" if speaker.get("is_host", False) else "Guest"
            speaking_time = timedelta(seconds=speaker.get("speaking_time", 0))
            formatted_lines.append(f"  - {name} ({role}): {speaking_time} total speaking time")
    
    # Add divider
    formatted_lines.append("-" * 80)
    formatted_lines.append("")
    
    # Process utterances if available
    if "results" in transcript and "utterances" in transcript["results"]:
        utterances = transcript["results"]["utterances"]
        
        # Add utterance count info
        formatted_lines.append(f"Total utterances: {len(utterances)}")
        
        # Add a warning for very few utterances
        if len(utterances) < 10:
            formatted_lines.append("⚠️  WARNING: VERY FEW UTTERANCES DETECTED - TRANSCRIPT MAY BE INCOMPLETE ⚠️".center(80))
        
        # Add divider before utterances
        formatted_lines.append("-" * 80)
        formatted_lines.append("")
        
        for utterance in utterances:
            start_time = format_time(utterance.get("start", 0))
            end_time = format_time(utterance.get("end", 0))
            speaker_id = utterance.get("speaker", None)
            speaker_name = speaker_map.get(speaker_id, f"Speaker {speaker_id}") if speaker_id is not None else "Unknown Speaker"
            text = utterance.get("text", "")
            
            # Format: [00:01:30 - 00:02:15] Speaker: Text content...
            time_range = f"[{start_time} - {end_time}]"
            formatted_lines.append(f"{time_range} {speaker_name}: {text}")
            formatted_lines.append("")  # Empty line for readability
    
    # Add footer for incomplete transcripts
    if coverage_pct and coverage_pct < 90:
        formatted_lines.append("-" * 80)
        formatted_lines.append(f"NOTE: This transcript only covers {coverage_pct:.1f}% of the full episode.".center(80))
        formatted_lines.append("-" * 80)
    
    # Join the lines
    formatted_text = "\n".join(formatted_lines)
    
    # Output to file or stdout
    if output:
        with open(output, 'w') as f:
            f.write(formatted_text)
        print(f"Transcript saved to {output}")
    else:
        print(formatted_text)

def main():
    """Main function to display a transcript."""
    parser = argparse.ArgumentParser(description="Display podcast transcript in a readable format")
    parser.add_argument(
        "transcript", 
        help="Path to the transcript JSON file"
    )
    parser.add_argument(
        "-o", "--output", 
        help="Output file to save the formatted transcript"
    )
    args = parser.parse_args()
    
    try:
        display_transcript(args.transcript, args.output)
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

if __name__ == "__main__":
    sys.exit(main()) 