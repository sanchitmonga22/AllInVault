#!/usr/bin/env python3
"""
Transcribe only the full episodes (not YouTube shorts) from the downloaded podcast episodes.

This script is a lightweight wrapper around the src/cli/transcribe_full_episodes_cmd.py implementation.
"""

import sys
from src.cli.transcribe_full_episodes_cmd import main

if __name__ == "__main__":
    sys.exit(main()) 