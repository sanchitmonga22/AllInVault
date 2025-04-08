"""
Tests for the opinion relationship service.
"""

import unittest
from unittest.mock import MagicMock
from datetime import datetime

from src.services.opinion_extraction.relationship_service import OpinionRelationshipService, RelationshipType

class TestOpinionRelationshipService(unittest.TestCase):
    """Test cases for the OpinionRelationshipService."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create the service
        self.service = OpinionRelationshipService(
            llm_service=None,  # No LLM for basic tests
            relation_batch_size=5,
            similarity_threshold=0.7
        )
        
        # Create test data - opinions with similar content but different episodes
        self.test_opinions = [
            {
                "id": "opinion1",
                "title": "Federal Reserve Rate Cuts",
                "description": "The Fed will cut rates aggressively in 2024",
                "content": "I think the Fed will cut rates quickly",
                "category": "Economics",
                "speakers": [
                    {
                        "speaker_id": "1",
                        "speaker_name": "Speaker One",
                        "stance": "support",
                        "reasoning": "Inflation is coming down",
                        "start_time": 10.5,
                        "end_time": 15.2
                    }
                ],
                "keywords": ["fed", "rates", "economy"],
                "episode_id": "episode1",
                "episode_title": "Episode One",
                "episode_date": datetime(2023, 1, 1)
            },
            {
                "id": "opinion2",
                "title": "Fed Rate Cuts 2024",
                "description": "The Federal Reserve will cut rates aggressively in 2024",
                "content": "The Fed is going to cut rates quickly in 2024",
                "category": "Economics",
                "speakers": [
                    {
                        "speaker_id": "2",
                        "speaker_name": "Speaker Two",
                        "stance": "support",
                        "reasoning": "Inflation is under control",
                        "start_time": 20.5,
                        "end_time": 25.2
                    }
                ],
                "keywords": ["fed", "rates", "inflation"],
                "episode_id": "episode2",
                "episode_title": "Episode Two",
                "episode_date": datetime(2023, 2, 1)
            },
            {
                "id": "opinion3",
                "title": "Technology Trends",
                "description": "AI will transform industries",
                "content": "Artificial intelligence is going to change everything",
                "category": "Technology",
                "speakers": [
                    {
                        "speaker_id": "1",
                        "speaker_name": "Speaker One",
                        "stance": "support",
                        "reasoning": "Based on recent advances",
                        "start_time": 30.5,
                        "end_time": 35.2
                    }
                ],
                "keywords": ["ai", "technology"],
                "episode_id": "episode1",
                "episode_title": "Episode One",
                "episode_date": datetime(2023, 1, 1)
            }
        ]
    
    def test_analyze_relationships_heuristic(self):
        """Test analyzing relationships using the heuristic approach."""
        # Group opinions by category
        categorized_opinions = {
            "Economics": [self.test_opinions[0], self.test_opinions[1]],
            "Technology": [self.test_opinions[2]]
        }
        
        # Call the method
        relationships = self.service.analyze_relationships(categorized_opinions)
        
        # Assertions
        self.assertGreater(len(relationships), 0)
        
        # The first two opinions should be related due to similarity
        found_relationship = False
        for rel in relationships:
            if (rel['source_id'] == 'opinion1' and rel['target_id'] == 'opinion2') or \
               (rel['source_id'] == 'opinion2' and rel['target_id'] == 'opinion1'):
                self.assertIn(rel['relation_type'], [RelationshipType.SAME_OPINION, RelationshipType.RELATED])
                found_relationship = True
        
        self.assertTrue(found_relationship, "Should find relationship between similar opinions")
    
    def test_no_relationship_between_different_categories(self):
        """Test that no relationships are found between opinions in different categories."""
        # Group opinions by category
        categorized_opinions = {
            "Economics": [self.test_opinions[0]],
            "Technology": [self.test_opinions[2]]
        }
        
        # Call the method
        relationships = self.service.analyze_relationships(categorized_opinions)
        
        # Check for cross-category relationships
        cross_category_relationship = False
        for rel in relationships:
            if (rel['source_id'] == 'opinion1' and rel['target_id'] == 'opinion3') or \
               (rel['source_id'] == 'opinion3' and rel['target_id'] == 'opinion1'):
                cross_category_relationship = True
        
        self.assertFalse(cross_category_relationship, 
                         "Should not find relationships between opinions in different categories")
    
    def test_no_relationship_between_opinions_in_same_episode(self):
        """Test that opinions in the same episode are not analyzed."""
        # Create opinions from the same episode
        same_episode_opinions = [
            {
                "id": "opinion4",
                "title": "Stock Market Outlook",
                "description": "The stock market will be volatile",
                "content": "I think the market will be bumpy",
                "category": "Economics",
                "episode_id": "episode3",
                "episode_title": "Episode Three",
                "episode_date": datetime(2023, 3, 1)
            },
            {
                "id": "opinion5",
                "title": "Market Volatility",
                "description": "The market will experience volatility",
                "content": "It's going to be a bumpy ride in the markets",
                "category": "Economics",
                "episode_id": "episode3",
                "episode_title": "Episode Three",
                "episode_date": datetime(2023, 3, 1)
            }
        ]
        
        # Group opinions by category
        categorized_opinions = {
            "Economics": same_episode_opinions
        }
        
        # Use the heuristic method directly to test the check for same episode
        relationships = self.service._analyze_relationships_heuristic(same_episode_opinions)
        
        # Assertions
        self.assertEqual(len(relationships), 0, 
                         "Should not find relationships between opinions in the same episode")
    
    def test_llm_integration(self):
        """Test integration with LLM."""
        # Create a mock LLM service
        mock_llm = MagicMock()
        mock_llm.call_simple.return_value = [
            {
                "source_id": "opinion1",
                "target_id": "opinion2",
                "relation_type": "same_opinion",
                "notes": "These opinions express the same view on Fed rate cuts"
            }
        ]
        
        # Set the mock LLM
        self.service.llm_service = mock_llm
        
        # Group opinions by category
        categorized_opinions = {
            "Economics": [self.test_opinions[0], self.test_opinions[1]]
        }
        
        # Call the method
        relationships = self.service.analyze_relationships(categorized_opinions)
        
        # Assertions
        self.assertEqual(len(relationships), 1)
        self.assertEqual(relationships[0]["relation_type"], RelationshipType.SAME_OPINION)
        self.assertEqual(relationships[0]["source_id"], "opinion1")
        self.assertEqual(relationships[0]["target_id"], "opinion2")
        
        # Verify the LLM was called
        mock_llm.call_simple.assert_called_once()

if __name__ == '__main__':
    unittest.main() 