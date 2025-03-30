#!/usr/bin/env python3
"""
All In Podcast Downloader

This script is a lightweight wrapper around the src/cli/download_podcast_cmd.py implementation.
"""

import sys
from src.cli.download_podcast_cmd import main

if __name__ == "__main__":
    sys.exit(main()) 