#!/usr/bin/env python3
"""
Process podcast episodes from download to transcription in one step.

This script is a lightweight wrapper around the src/cli/process_podcast_cmd.py implementation.
"""

import sys
from src.cli.process_podcast_cmd import main

if __name__ == "__main__":
    sys.exit(main()) 