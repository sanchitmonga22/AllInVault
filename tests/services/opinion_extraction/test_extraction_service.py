"""
Tests for the opinion extraction service.
"""

import unittest
import os
from unittest.mock import MagicMock, patch
from datetime import datetime

from src.models.podcast_episode import PodcastEpisode
from src.services.opinion_extraction.extraction_service import OpinionExtractionService
from src.services.llm_service import LLMService

class TestOpinionExtractionService(unittest.TestCase):
    """Test cases for the OpinionExtractionService."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock LLM service for testing
        self.mock_llm_service = MagicMock(spec=LLMService)
        
        # Create the service with the mock LLM
        self.service = OpinionExtractionService(use_llm=True)
        self.service.llm_service = self.mock_llm_service
        
        # Mock the component services as well
        self.service.raw_extraction_service.llm_service = self.mock_llm_service
        self.service.categorization_service.llm_service = self.mock_llm_service
        self.service.relationship_service.llm_service = self.mock_llm_service
        
        # Create test data
        self.test_episode = PodcastEpisode(
            video_id="test_episode_1",
            title="Test Episode",
            description="A test episode",
            published_at=datetime.now(),
            transcript_filename="test_transcript.txt",
            metadata={"speakers": {"1": {"name": "Speaker One", "is_guest": False}}}
        )
    
    @patch('os.path.exists')
    def test_extract_opinions_from_transcript(self, mock_exists):
        """Test extracting opinions from a transcript with mocked LLM responses."""
        # Setup mocks
        mock_exists.return_value = True
        
        # Mock the raw extraction service
        self.service.raw_extraction_service.extract_raw_opinions = MagicMock(return_value=[
            {
                "id": "opinion1",
                "title": "Test Opinion",
                "description": "This is a test opinion",
                "content": "I think this is important",
                "category": "Test Category",
                "speakers": [
                    {
                        "speaker_id": "1",
                        "speaker_name": "Speaker One",
                        "stance": "support",
                        "reasoning": "Strong belief",
                        "start_time": 10.5,
                        "end_time": 15.2
                    }
                ],
                "keywords": ["test", "opinion"],
                "episode_id": "test_episode_1",
                "episode_title": "Test Episode",
                "episode_date": datetime.now()
            }
        ])
        
        # Mock the categorization service
        self.service.categorization_service.categorize_opinions = MagicMock(return_value={
            "Test Category": [
                {
                    "id": "opinion1",
                    "title": "Test Opinion",
                    "description": "This is a test opinion",
                    "content": "I think this is important",
                    "category": "Test Category",
                    "speakers": [
                        {
                            "speaker_id": "1",
                            "speaker_name": "Speaker One",
                            "stance": "support",
                            "reasoning": "Strong belief",
                            "start_time": 10.5,
                            "end_time": 15.2
                        }
                    ],
                    "keywords": ["test", "opinion"],
                    "episode_id": "test_episode_1",
                    "episode_title": "Test Episode",
                    "episode_date": datetime.now()
                }
            ]
        })
        
        # Mock the relationship service
        self.service.relationship_service.analyze_relationships = MagicMock(return_value=[])
        
        # Mock the opinion repository
        self.service.opinion_repository.get_all_opinions = MagicMock(return_value=[])
        
        # Mock the merger service
        mock_opinion = MagicMock()
        mock_opinion.appearances = [MagicMock(episode_id="test_episode_1")]
        
        self.service.merger_service.process_relationships = MagicMock(return_value=[
            {
                "id": "opinion1",
                "title": "Test Opinion",
                "description": "This is a test opinion",
                "category": "Test Category"
            }
        ])
        
        self.service.merger_service.create_opinion_objects = MagicMock(return_value=[mock_opinion])
        self.service.merger_service.save_opinions = MagicMock(return_value=True)
        
        # Call the method
        result = self.service.extract_opinions_from_transcript(
            episode=self.test_episode,
            transcript_path="test_transcript.txt"
        )
        
        # Assertions
        self.assertEqual(len(result), 1)
        
        # Verify the calls to the component services
        self.service.raw_extraction_service.extract_raw_opinions.assert_called_once()
        self.service.categorization_service.categorize_opinions.assert_called_once()
        self.service.relationship_service.analyze_relationships.assert_called_once()
        self.service.merger_service.process_relationships.assert_called_once()
        self.service.merger_service.create_opinion_objects.assert_called_once()
        self.service.merger_service.save_opinions.assert_called_once()
    
    def test_extract_opinions_without_llm(self):
        """Test extracting opinions when LLM is not available."""
        # Set LLM to None to simulate unavailability
        self.service.use_llm = False
        self.service.llm_service = None
        
        # Call the method
        result = self.service.extract_opinions_from_transcript(
            episode=self.test_episode,
            transcript_path="test_transcript.txt"
        )
        
        # Should return empty list when LLM is not available
        self.assertEqual(len(result), 0)

if __name__ == '__main__':
    unittest.main() 