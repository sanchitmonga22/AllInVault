#!/usr/bin/env python3
"""
All In Podcast Transcription

This script is a lightweight wrapper around the src/cli/transcribe_audio_cmd.py implementation.
"""

import sys
from src.cli.transcribe_audio_cmd import main

if __name__ == "__main__":
    sys.exit(main()) 