"""
Opinion Extraction Package

This package contains services for extracting opinions from podcast transcripts.
"""

from src.services.opinion_extraction.extraction_service import OpinionExtractionService
from src.services.opinion_extraction.checkpoint_service import CheckpointService

__all__ = ['OpinionExtractionService', 'CheckpointService'] 