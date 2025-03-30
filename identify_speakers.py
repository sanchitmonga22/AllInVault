#!/usr/bin/env python3
"""
Identify speakers in podcast episode transcripts and update episode metadata.

This script serves as a convenient entry point to the speaker identification CLI.
"""

import sys
from src.cli.identify_speakers_cmd import main

if __name__ == "__main__":
    sys.exit(main()) 