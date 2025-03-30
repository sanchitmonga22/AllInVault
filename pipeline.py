#!/usr/bin/env python3
"""
Main entry point for the AllInVault podcast processing system.

This is the single unified command-line interface for:
1. Processing the podcast pipeline with flexible stage selection
2. Displaying transcripts with various formatting options
3. Verifying transcript metadata and statistics

Examples:
    # Run the complete pipeline for most recent 5 episodes
    python pipeline.py

    # Run only specific stages for the 10 most recent episodes
    python pipeline.py pipeline --stages fetch_metadata,download_audio --num-episodes 10

    # Process specific episodes by video ID
    python pipeline.py pipeline --episodes "Wr12BFko-Xo,8UzQ5uf_vik"

    # Display a transcript
    python pipeline.py display --episode VIDEO_ID

    # Verify transcript metadata and display statistics
    python pipeline.py verify

Run with --help for a complete list of options.
"""

from src.cli.pipeline_cmd import main

if __name__ == "__main__":
    exit(main()) 