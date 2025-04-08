#!/usr/bin/env python3
"""
Command-line interface for the flexible podcast processing pipeline.

This script provides a unified interface to:
1. Execute specific pipeline stages
2. Process all episodes or specific episodes
3. Control stage dependencies
4. Configure stage-specific parameters
5. Display and verify transcripts
"""

import argparse
import json
import os
import sys
from typing import List, Optional, Dict, Any

from src.services.pipeline_orchestrator import (
    PipelineOrchestrator, 
    PipelineStage,
    StageResult
)
from src.utils.config import load_config, AppConfig
from src.repositories.episode_repository import JsonFileRepository

def parse_episode_ids(ids_str: Optional[str]) -> Optional[List[str]]:
    """
    Parse comma-separated episode IDs into a list.
    
    Args:
        ids_str: Comma-separated list of episode IDs
        
    Returns:
        List of episode IDs or None if not provided
    """
    if not ids_str:
        return None
    return [vid.strip() for vid in ids_str.split(',') if vid.strip()]

def display_transcript(episode_id: str, format_type: str = "text", 
                      show_speakers: bool = True, show_timestamps: bool = False) -> int:
    """
    Display a transcript in the specified format.
    
    Args:
        episode_id: Video ID of the episode to display
        format_type: Display format ('text', 'json')
        show_speakers: Whether to show speaker information
        show_timestamps: Whether to show timestamps
        
    Returns:
        0 on success, 1 on failure
    """
    try:
        config = load_config()
        repository = JsonFileRepository(str(config.episodes_db_path))
        
        # Get episode from repository
        episode = repository.get_episode(episode_id)
        if not episode:
            print(f"Error: Episode {episode_id} not found", file=sys.stderr)
            return 1
        
        # Check if transcript exists
        if not episode.transcript_filename:
            print(f"Error: No transcript available for episode {episode_id}", file=sys.stderr)
            return 1
        
        # Determine path to transcript files
        transcript_json_path = os.path.join(str(config.transcripts_dir), f"{episode_id}.json")
        transcript_txt_path = os.path.join(str(config.transcripts_dir), f"{episode_id}.txt")
        
        # Display transcript based on format
        if format_type == "json":
            # Display JSON format
            if not os.path.exists(transcript_json_path):
                print(f"Error: Transcript JSON file not found: {transcript_json_path}", file=sys.stderr)
                return 1
                
            with open(transcript_json_path, 'r') as f:
                transcript_data = json.load(f)
                
            print(json.dumps(transcript_data, indent=2))
            return 0
            
        else:  # text format
            # Display text format
            if not os.path.exists(transcript_txt_path):
                print(f"Error: Transcript text file not found: {transcript_txt_path}", file=sys.stderr)
                return 1
                
            with open(transcript_txt_path, 'r') as f:
                transcript_text = f.read()
                
            # Process the text based on options
            if not show_speakers:
                # Remove speaker labels (e.g., "[Speaker 1]: ")
                import re
                transcript_text = re.sub(r'\[Speaker \d+\]: ', '', transcript_text)
                
            if not show_timestamps and '[' in transcript_text and ']' in transcript_text:
                # Remove timestamps (e.g., "[00:01:23]")
                import re
                transcript_text = re.sub(r'\[\d{2}:\d{2}:\d{2}\] ', '', transcript_text)
                
            print(transcript_text)
            return 0
            
    except Exception as e:
        print(f"Error displaying transcript: {e}", file=sys.stderr)
        return 1

def verify_transcripts(stats_only: bool = False, update_files: bool = True) -> int:
    """
    Verify transcript metadata and display statistics.
    
    Args:
        stats_only: Whether to only display statistics without updating
        update_files: Whether to update episode metadata files
        
    Returns:
        0 on success, 1 on failure
    """
    try:
        config = load_config()
        repository = JsonFileRepository(str(config.episodes_db_path))
        
        # Get all episodes
        all_episodes = repository.get_all_episodes()
        
        # Statistics
        stats = {
            "total_episodes": len(all_episodes),
            "with_audio": 0,
            "with_transcript": 0,
            "with_speakers": 0,
            "full_episodes": 0,
            "shorts": 0,
            "missing_audio": [],
            "missing_transcript": [],
            "missing_speakers": []
        }
        
        # Verify each episode
        for episode in all_episodes:
            # Check episode type
            if episode.metadata and episode.metadata.get("type") == "FULL":
                stats["full_episodes"] += 1
            elif episode.metadata and episode.metadata.get("type") == "SHORT":
                stats["shorts"] += 1
            
            # Check audio
            if episode.audio_filename:
                stats["with_audio"] += 1
                audio_path = os.path.join(str(config.audio_dir), episode.audio_filename)
                if not os.path.exists(audio_path):
                    print(f"Warning: Audio file not found: {audio_path}")
                    episode.audio_filename = None
                    if update_files:
                        repository.update_episode(episode)
            else:
                stats["missing_audio"].append(episode.video_id)
            
            # Check transcript
            if episode.transcript_filename:
                stats["with_transcript"] += 1
                transcript_path = os.path.join(str(config.transcripts_dir), episode.transcript_filename)
                if not os.path.exists(transcript_path):
                    print(f"Warning: Transcript file not found: {transcript_path}")
                    episode.transcript_filename = None
                    if update_files:
                        repository.update_episode(episode)
            else:
                stats["missing_transcript"].append(episode.video_id)
            
            # Check speakers
            if episode.metadata and episode.metadata.get("speakers"):
                stats["with_speakers"] += 1
            else:
                stats["missing_speakers"].append(episode.video_id)
        
        # Display statistics
        print("\nTranscript Verification Statistics:")
        print(f"Total Episodes: {stats['total_episodes']}")
        print(f"Full Episodes: {stats['full_episodes']}")
        print(f"Shorts: {stats['shorts']}")
        print(f"With Audio: {stats['with_audio']} ({stats['with_audio']/stats['total_episodes']*100:.1f}%)")
        print(f"With Transcript: {stats['with_transcript']} ({stats['with_transcript']/stats['total_episodes']*100:.1f}%)")
        print(f"With Speaker Identification: {stats['with_speakers']} ({stats['with_speakers']/stats['total_episodes']*100:.1f}%)")
        
        # Show missing items if not stats_only
        if not stats_only:
            if stats["missing_audio"]:
                print(f"\nEpisodes missing audio ({len(stats['missing_audio'])}):")
                for video_id in stats["missing_audio"][:10]:  # Limit to 10 for brevity
                    episode = repository.get_episode(video_id)
                    print(f"  - {video_id}: {episode.title}")
                if len(stats["missing_audio"]) > 10:
                    print(f"  ... and {len(stats['missing_audio']) - 10} more")
            
            if stats["missing_transcript"]:
                print(f"\nEpisodes missing transcript ({len(stats['missing_transcript'])}):")
                for video_id in stats["missing_transcript"][:10]:  # Limit to 10 for brevity
                    episode = repository.get_episode(video_id)
                    print(f"  - {video_id}: {episode.title}")
                if len(stats["missing_transcript"]) > 10:
                    print(f"  ... and {len(stats['missing_transcript']) - 10} more")
            
            if stats["missing_speakers"]:
                print(f"\nEpisodes missing speaker identification ({len(stats['missing_speakers'])}):")
                for video_id in stats["missing_speakers"][:10]:  # Limit to 10 for brevity
                    episode = repository.get_episode(video_id)
                    print(f"  - {video_id}: {episode.title}")
                if len(stats["missing_speakers"]) > 10:
                    print(f"  ... and {len(stats['missing_speakers']) - 10} more")
        
        return 0
        
    except Exception as e:
        print(f"Error verifying transcripts: {e}", file=sys.stderr)
        return 1

def main():
    """Execute the podcast processing pipeline with flexible stage selection."""
    parser = argparse.ArgumentParser(
        description="Process podcast episodes with flexible stage selection"
    )
    
    # Subparsers for different operation modes
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")
    
    # Pipeline command
    pipeline_parser = subparsers.add_parser("pipeline", help="Execute the pipeline or specific stages")
    
    # Pipeline stage selection
    stage_group = pipeline_parser.add_argument_group("Pipeline Stage Selection")
    stage_group.add_argument(
        "--stages", 
        type=str,
        help=('Comma-separated list of stages to execute. Available stages: '
              'FETCH_METADATA, ANALYZE_EPISODES, DOWNLOAD_AUDIO, CONVERT_AUDIO, '
              'TRANSCRIBE_AUDIO, IDENTIFY_SPEAKERS, EXTRACT_OPINIONS')
    )
    
    stage_group.add_argument(
        "--start-stage", 
        type=str,
        choices=["fetch_metadata", "analyze_episodes", "download_audio", "convert_audio", "transcribe_audio", "identify_speakers"],
        help="First stage to execute in the pipeline"
    )
    
    stage_group.add_argument(
        "--end-stage", 
        type=str,
        choices=["fetch_metadata", "analyze_episodes", "download_audio", "convert_audio", "transcribe_audio", "identify_speakers"],
        help="Last stage to execute in the pipeline"
    )
    
    stage_group.add_argument(
        "--skip-dependencies", 
        action="store_true",
        help="Skip automatic execution of stage dependencies"
    )
    
    # Episode selection
    episode_group = pipeline_parser.add_argument_group("Episode Selection")
    episode_group.add_argument(
        "--episodes", 
        type=str,
        help="Comma-separated list of episode video IDs to process"
    )
    
    episode_group.add_argument(
        "-n", "--num-episodes", 
        type=int, 
        default=5,
        help="Number of recent episodes to process (used only when --episodes is not provided)"
    )
    
    # Stage-specific parameters
    fetch_group = pipeline_parser.add_argument_group("Fetch Metadata Stage")
    fetch_group.add_argument(
        "--limit", 
        type=int,
        help="Maximum number of episodes to fetch metadata for"
    )
    
    analyze_group = pipeline_parser.add_argument_group("Analyze Episodes Stage")
    analyze_group.add_argument(
        "--min-duration", 
        type=int,
        default=180,
        help="Minimum duration in seconds for an episode to be considered full (default: 180)"
    )
    
    download_group = pipeline_parser.add_argument_group("Download Audio Stage")
    download_group.add_argument(
        "--webm-dir", 
        type=str,
        help="Directory for storing downloaded WebM files"
    )
    
    download_group.add_argument(
        "--all-episodes", 
        action="store_true",
        help="Include all episodes for audio download, not just full episodes"
    )
    
    convert_group = pipeline_parser.add_argument_group("Convert Audio Stage")
    convert_group.add_argument(
        "--audio-dir", 
        type=str,
        help="Directory for storing converted audio files"
    )
    
    convert_group.add_argument(
        "--audio-format", 
        type=str,
        help="Audio format to convert to (e.g., mp3, m4a)"
    )
    
    convert_group.add_argument(
        "--audio-quality", 
        type=str,
        help="Audio quality for conversion (e.g., 192)"
    )
    
    convert_group.add_argument(
        "--max-workers", 
        type=int,
        help="Maximum number of parallel conversion processes"
    )
    
    transcribe_group = pipeline_parser.add_argument_group("Transcribe Audio Stage")
    transcribe_group.add_argument(
        "--transcripts-dir", 
        type=str,
        help="Directory for storing transcriptions"
    )
    
    transcribe_group.add_argument(
        "--model", 
        type=str,
        default="nova-3",
        help="Deepgram model to use for transcription (default: nova-3)"
    )
    
    transcribe_group.add_argument(
        "--no-diarize", 
        action="store_true",
        help="Disable speaker diarization during transcription"
    )
    
    transcribe_group.add_argument(
        "--no-smart-format", 
        action="store_true",
        help="Disable smart formatting in transcripts"
    )
    
    transcribe_group.add_argument(
        "--detect-language", 
        action="store_true",
        help="Enable language detection during transcription"
    )
    
    speaker_group = pipeline_parser.add_argument_group("Identify Speakers Stage")
    speaker_group.add_argument(
        "--no-llm", 
        action="store_true",
        help="Disable LLM for speaker identification and use heuristics only"
    )
    
    speaker_group.add_argument(
        "--llm-provider", 
        type=str, 
        choices=["openai", "deepseq"],
        default="openai",
        help="LLM provider to use for speaker identification (default: openai)"
    )
    
    speaker_group.add_argument(
        "--force-reidentify", 
        action="store_true",
        help="Force re-identification of speakers even if already identified"
    )
    
    # Opinion extraction stage parameters
    opinion_group = pipeline_parser.add_argument_group("Extract Opinions Stage")
    opinion_group.add_argument(
        "--max-opinions-per-episode", 
        type=int, 
        default=15,
        help="Maximum number of opinions to extract per episode (default: 15)"
    )
    
    opinion_group.add_argument(
        "--max-context-opinions", 
        type=int, 
        default=20,
        help="Maximum number of context opinions to include (default: 20)"
    )
    
    opinion_group.add_argument(
        "--checkpoint-path", 
        type=str,
        help="Path to store checkpoint data (default: data/checkpoints/extraction_checkpoint.json)"
    )
    
    opinion_group.add_argument(
        "--raw-opinions-path", 
        type=str,
        help="Path to store raw opinions data (default: data/checkpoints/raw_opinions.json)"
    )
    
    opinion_group.add_argument(
        "--no-resume", 
        action="store_true",
        help="Don't resume from previous checkpoint, start fresh"
    )
    
    opinion_group.add_argument(
        "--no-checkpoints", 
        action="store_true",
        help="Don't save checkpoints during extraction"
    )
    
    opinion_group.add_argument(
        "--reset-checkpoint", 
        action="store_true",
        help="Reset checkpoint data before starting extraction"
    )
    
    # Display command
    display_parser = subparsers.add_parser("display", help="Display a transcript")
    display_parser.add_argument(
        "--episode", 
        type=str, 
        required=True,
        help="Video ID of the episode to display"
    )
    display_parser.add_argument(
        "--format", 
        type=str, 
        choices=["text", "json"],
        default="text",
        help="Display format (default: text)"
    )
    display_parser.add_argument(
        "--no-speakers", 
        action="store_true",
        help="Hide speaker information"
    )
    display_parser.add_argument(
        "--show-timestamps", 
        action="store_true",
        help="Show timestamps"
    )
    
    # Verify command
    verify_parser = subparsers.add_parser("verify", help="Verify transcript metadata and statistics")
    verify_parser.add_argument(
        "--stats-only", 
        action="store_true",
        help="Only display statistics without details of missing items"
    )
    verify_parser.add_argument(
        "--no-update", 
        action="store_true",
        help="Don't update episode metadata files"
    )
    
    args = parser.parse_args()
    
    # Default to pipeline if no command is specified
    if not args.command:
        args.command = "pipeline"
    
    try:
        if args.command == "display":
            return display_transcript(
                args.episode,
                args.format,
                not args.no_speakers,
                args.show_timestamps
            )
            
        elif args.command == "verify":
            return verify_transcripts(
                args.stats_only,
                not args.no_update
            )
            
        else:  # pipeline command (default)
            # Initialize the pipeline orchestrator
            orchestrator = PipelineOrchestrator()
            
            # Parse episode IDs
            episode_ids = parse_episode_ids(args.episodes)
            
            # Determine which stages to execute
            if args.stages:
                selected_stages = [s.strip().upper() for s in args.stages.split(',') if s.strip()]
                stage_enum_map = {s.name: s for s in PipelineStage}
                stages_to_execute = [stage_enum_map[s] for s in selected_stages if s in stage_enum_map]
                
                if not stages_to_execute:
                    print("Error: No valid stages specified", file=sys.stderr)
                    return 1
                    
                # Execute individual stages
                kwargs = build_stage_kwargs(args)
                results = {}
                
                for stage in stages_to_execute:
                    result = orchestrator.execute_stage(
                        stage, 
                        episode_ids, 
                        check_dependencies=not args.skip_dependencies,
                        **kwargs
                    )
                    results[stage] = result
                    
                    if not result.success:
                        print(f"Error executing {stage.name}: {result.message}", file=sys.stderr)
                        return 1
            else:
                # Determine start and end stages for pipeline execution
                start_stage = None
                if args.start_stage:
                    start_stage = getattr(PipelineStage, args.start_stage.upper())
                    
                end_stage = None
                if args.end_stage:
                    end_stage = getattr(PipelineStage, args.end_stage.upper())
                
                # Build kwargs for stage-specific parameters
                kwargs = build_stage_kwargs(args)
                
                # Execute pipeline
                results = orchestrator.execute_pipeline(
                    start_stage=start_stage,
                    end_stage=end_stage,
                    episode_ids=episode_ids,
                    **kwargs
                )
            
            # Print summary of results
            print("\nPipeline Execution Summary:")
            for stage, result in results.items():
                status = "Success" if result.success else "Failed"
                print(f"{stage.name}: {status} - {result.message}")
            
            # Check if all stages were successful
            if all(result.success for result in results.values()):
                return 0
            else:
                return 1
        
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1

def build_stage_kwargs(args):
    """
    Build keyword arguments for stage execution based on command-line arguments.
    
    Args:
        args: Parsed command-line arguments
        
    Returns:
        Dictionary of keyword arguments for stage execution
    """
    kwargs = {}
    
    # Fetch metadata stage
    if args.limit:
        kwargs['limit'] = args.limit
    else:
        kwargs['limit'] = args.num_episodes
    
    # Analyze episodes stage
    kwargs['min_duration'] = args.min_duration
    
    # Download audio stage
    if args.webm_dir:
        kwargs['output_dir'] = args.webm_dir
    kwargs['full_episodes_only'] = not args.all_episodes
    
    # Convert audio stage
    if args.audio_dir:
        kwargs['mp3_dir'] = args.audio_dir
    if args.webm_dir:
        kwargs['webm_dir'] = args.webm_dir
    if args.audio_format:
        kwargs['audio_format'] = args.audio_format
    if args.audio_quality:
        kwargs['audio_quality'] = args.audio_quality
    if args.max_workers:
        kwargs['max_workers'] = args.max_workers
    
    # Transcribe audio stage
    if args.transcripts_dir:
        kwargs['transcripts_dir'] = args.transcripts_dir
    if args.audio_dir:
        kwargs['audio_dir'] = args.audio_dir
    kwargs['model'] = args.model
    kwargs['diarize'] = not args.no_diarize
    kwargs['smart_format'] = not args.no_smart_format
    kwargs['detect_language'] = args.detect_language
    
    # Identify speakers stage
    kwargs['use_llm'] = not args.no_llm
    kwargs['llm_provider'] = args.llm_provider
    kwargs['force_reidentify'] = args.force_reidentify
    if args.transcripts_dir:
        kwargs['transcripts_dir'] = args.transcripts_dir
    
    # Extract opinions stage
    if hasattr(args, 'max_opinions_per_episode'):
        kwargs['max_opinions_per_episode'] = args.max_opinions_per_episode
    if hasattr(args, 'max_context_opinions'):
        kwargs['max_context_opinions'] = args.max_context_opinions
    if hasattr(args, 'checkpoint_path'):
        kwargs['checkpoint_path'] = args.checkpoint_path
    if hasattr(args, 'raw_opinions_path'):
        kwargs['raw_opinions_path'] = args.raw_opinions_path
    if hasattr(args, 'no_resume'):
        kwargs['resume_from_checkpoint'] = not args.no_resume
    if hasattr(args, 'no_checkpoints'):
        kwargs['save_checkpoints'] = not args.no_checkpoints
    if hasattr(args, 'reset_checkpoint'):
        kwargs['reset_checkpoint'] = args.reset_checkpoint
    
    return kwargs

if __name__ == "__main__":
    sys.exit(main()) 