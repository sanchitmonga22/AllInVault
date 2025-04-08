"""
Speaker Tracking Service

This module provides functionality for tracking speakers' stances on opinions
and detecting contradictions in their positions.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from collections import defaultdict

from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance
from src.models.opinions.previous_stance import PreviousStance
from src.models.opinions.speaker_journey import SpeakerJourney, SpeakerJourneyNode
from src.repositories.opinion_repository import OpinionRepository
from src.services.opinion_extraction.base_service import BaseOpinionService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SpeakerTrackingService(BaseOpinionService):
    """Service for tracking speaker stances and detecting contradictions."""
    
    def __init__(self, 
                 opinion_repository: Optional[OpinionRepository] = None):
        """
        Initialize the speaker tracking service.
        
        Args:
            opinion_repository: Repository for opinion storage
        """
        super().__init__(llm_service=None)
        self.opinion_repository = opinion_repository
    
    def track_speaker_stances(
        self,
        opinions: List[Opinion]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Track stances of all speakers across all opinions.
        
        Args:
            opinions: List of opinion objects
            
        Returns:
            Dictionary mapping speaker IDs to their opinion stances:
            {
                speaker_id: {
                    opinion_id: [
                        {
                            date: datetime,
                            stance: str,
                            reasoning: str,
                            episode_id: str
                        },
                        ...
                    ]
                }
            }
        """
        logger.info(f"Tracking speaker stances across {len(opinions)} opinions")
        
        # Initialize speaker stance tracking
        speaker_stances = defaultdict(lambda: defaultdict(list))
        
        # Process each opinion to collect all speaker stances
        for opinion in opinions:
            for appearance in opinion.appearances:
                for stance in appearance.speakers:
                    # Record this stance
                    stance_record = {
                        'date': appearance.date,
                        'stance': stance.stance,
                        'reasoning': stance.reasoning,
                        'episode_id': appearance.episode_id,
                        'episode_title': appearance.episode_title
                    }
                    
                    speaker_stances[stance.speaker_id][opinion.id].append(stance_record)
        
        # Sort stance records by date for each speaker and opinion
        for speaker_id, opinions_map in speaker_stances.items():
            for opinion_id, stances in opinions_map.items():
                opinions_map[opinion_id] = sorted(stances, key=lambda x: x['date'])
        
        return dict(speaker_stances)
    
    def detect_stance_changes(
        self,
        speaker_stances: Dict[str, Dict[str, List[Dict[str, Any]]]]
    ) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Detect changes in speakers' stances over time.
        
        Args:
            speaker_stances: Dictionary mapping speaker IDs to their opinion stances
            
        Returns:
            Dictionary mapping speaker IDs to their opinion stance changes:
            {
                speaker_id: {
                    opinion_id: [
                        {
                            from_stance: str,
                            to_stance: str,
                            from_date: datetime,
                            to_date: datetime,
                            from_episode: str,
                            to_episode: str,
                            change_magnitude: str  # minor, moderate, major, reversal
                        },
                        ...
                    ]
                }
            }
        """
        logger.info("Detecting stance changes for all speakers")
        
        stance_changes = defaultdict(lambda: defaultdict(list))
        
        # Process each speaker
        for speaker_id, opinions_map in speaker_stances.items():
            # For each opinion this speaker has discussed
            for opinion_id, stances in opinions_map.items():
                # Need at least 2 stances to detect a change
                if len(stances) < 2:
                    continue
                    
                # Check for changes between consecutive stances
                for i in range(1, len(stances)):
                    prev_stance = stances[i-1]
                    curr_stance = stances[i]
                    
                    # If stance actually changed
                    if prev_stance['stance'] != curr_stance['stance']:
                        # Determine change magnitude
                        change_magnitude = self._calculate_stance_change_magnitude(
                            prev_stance['stance'],
                            curr_stance['stance']
                        )
                        
                        # Record the change
                        change_record = {
                            'from_stance': prev_stance['stance'],
                            'to_stance': curr_stance['stance'],
                            'from_date': prev_stance['date'],
                            'to_date': curr_stance['date'],
                            'from_episode': prev_stance['episode_id'],
                            'to_episode': curr_stance['episode_id'],
                            'from_episode_title': prev_stance['episode_title'],
                            'to_episode_title': curr_stance['episode_title'],
                            'from_reasoning': prev_stance['reasoning'],
                            'to_reasoning': curr_stance['reasoning'],
                            'change_magnitude': change_magnitude
                        }
                        
                        stance_changes[speaker_id][opinion_id].append(change_record)
        
        return dict(stance_changes)
    
    def _calculate_stance_change_magnitude(
        self,
        from_stance: str,
        to_stance: str
    ) -> str:
        """
        Calculate the magnitude of a stance change.
        
        Args:
            from_stance: Original stance
            to_stance: New stance
            
        Returns:
            String describing change magnitude: minor, moderate, major, reversal
        """
        # Define stance values for magnitude calculation
        stance_values = {
            'support': 1.0,
            'neutral': 0.0,
            'oppose': -1.0,
            'unclear': 0.0
        }
        
        # Calculate the magnitude of change
        if from_stance not in stance_values or to_stance not in stance_values:
            return "unclear"
            
        from_value = stance_values[from_stance]
        to_value = stance_values[to_stance]
        
        difference = abs(from_value - to_value)
        
        if difference == 0:
            return "none"
        elif difference <= 0.5:
            return "minor"
        elif difference <= 1.0:
            return "moderate"
        elif difference <= 1.5:
            return "major"
        else:
            return "reversal"
    
    def detect_contradictions(
        self,
        speaker_stances: Dict[str, Dict[str, List[Dict[str, Any]]]]
    ) -> List[Dict[str, Any]]:
        """
        Detect contradictions in speakers' positions on different opinions.
        
        Args:
            speaker_stances: Dictionary mapping speaker IDs to their opinion stances
            
        Returns:
            List of contradiction records:
            [
                {
                    'speaker_id': str,
                    'speaker_name': str,
                    'opinion_a_id': str,
                    'opinion_b_id': str,
                    'stance_a': str,
                    'stance_b': str,
                    'date_a': datetime,
                    'date_b': datetime,
                    'episode_a': str,
                    'episode_b': str,
                    'contradiction_type': str,  # explicit, implicit, shift
                    'description': str
                },
                ...
            ]
        """
        logger.info("Detecting contradictions in speaker positions")
        
        contradictions = []
        
        # Process each speaker
        for speaker_id, opinions_map in speaker_stances.items():
            # Skip speakers with only one opinion
            if len(opinions_map) < 2:
                continue
                
            # Get the latest stance for each opinion
            latest_stances = {}
            for opinion_id, stances in opinions_map.items():
                if stances:
                    latest_stances[opinion_id] = stances[-1]
            
            # Compare pairs of opinions
            opinion_ids = list(latest_stances.keys())
            for i in range(len(opinion_ids)):
                for j in range(i+1, len(opinion_ids)):
                    opinion_a_id = opinion_ids[i]
                    opinion_b_id = opinion_ids[j]
                    
                    stance_a = latest_stances[opinion_a_id]
                    stance_b = latest_stances[opinion_b_id]
                    
                    # Check for explicit contradictions (support vs oppose)
                    if ((stance_a['stance'] == 'support' and stance_b['stance'] == 'oppose') or
                        (stance_a['stance'] == 'oppose' and stance_b['stance'] == 'support')):
                        
                        # Create contradiction record
                        contradiction = {
                            'speaker_id': speaker_id,
                            'opinion_a_id': opinion_a_id,
                            'opinion_b_id': opinion_b_id,
                            'stance_a': stance_a['stance'],
                            'stance_b': stance_b['stance'],
                            'date_a': stance_a['date'],
                            'date_b': stance_b['date'],
                            'episode_a': stance_a['episode_id'],
                            'episode_b': stance_b['episode_id'],
                            'episode_a_title': stance_a['episode_title'],
                            'episode_b_title': stance_b['episode_title'],
                            'contradiction_type': 'explicit',
                            'description': f"Speaker holds opposing stances on related opinions"
                        }
                        
                        contradictions.append(contradiction)
            
            # Check for self-contradictions (flip-flopping on the same opinion)
            for opinion_id, stances in opinions_map.items():
                if len(stances) < 2:
                    continue
                    
                # Look for support -> oppose or oppose -> support transitions
                current_stance = None
                for stance_record in stances:
                    # Skip unclear or neutral stances
                    if stance_record['stance'] in ['unclear', 'neutral']:
                        continue
                        
                    if current_stance is None:
                        current_stance = stance_record
                        continue
                    
                    # Check for a reversal
                    if ((current_stance['stance'] == 'support' and stance_record['stance'] == 'oppose') or
                        (current_stance['stance'] == 'oppose' and stance_record['stance'] == 'support')):
                        
                        # Create contradiction record
                        contradiction = {
                            'speaker_id': speaker_id,
                            'opinion_a_id': opinion_id,
                            'opinion_b_id': opinion_id,  # Same opinion
                            'stance_a': current_stance['stance'],
                            'stance_b': stance_record['stance'],
                            'date_a': current_stance['date'],
                            'date_b': stance_record['date'],
                            'episode_a': current_stance['episode_id'],
                            'episode_b': stance_record['episode_id'],
                            'episode_a_title': current_stance['episode_title'],
                            'episode_b_title': stance_record['episode_title'],
                            'contradiction_type': 'reversal',
                            'description': f"Speaker reversed position on the same opinion"
                        }
                        
                        contradictions.append(contradiction)
                    
                    # Update current stance
                    current_stance = stance_record
        
        return contradictions
    
    def generate_previous_stances(
        self,
        opinions: List[Opinion]
    ) -> Dict[str, List[PreviousStance]]:
        """
        Generate PreviousStance objects for each opinion where stances have changed.
        
        Args:
            opinions: List of opinion objects
            
        Returns:
            Dictionary mapping opinion IDs to lists of PreviousStance objects
        """
        logger.info(f"Generating previous stance records for {len(opinions)} opinions")
        
        # Track speaker stances for each opinion
        speaker_stances = self.track_speaker_stances(opinions)
        
        # Detect stance changes
        stance_changes = self.detect_stance_changes(speaker_stances)
        
        # Create previous stance objects
        previous_stances = defaultdict(list)
        
        # For each speaker
        for speaker_id, opinions_map in stance_changes.items():
            # For each opinion with changes
            for opinion_id, changes in opinions_map.items():
                # For each change
                for change in changes:
                    previous_stance = PreviousStance(
                        speaker_stance_id=f"{speaker_id}_{opinion_id}_{change['from_episode']}",
                        episode_id=change['from_episode'],
                        episode_date=change['from_date'],
                        stance=change['from_stance'],
                        change_reasoning=f"Changed to {change['to_stance']} in episode {change['to_episode_title']}"
                    )
                    
                    previous_stances[opinion_id].append(previous_stance)
        
        return dict(previous_stances)
    
    def analyze_speaker_consistency(
        self,
        speaker_stances: Dict[str, Dict[str, List[Dict[str, Any]]]],
        contradictions: List[Dict[str, Any]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Analyze each speaker's consistency in their opinions.
        
        Args:
            speaker_stances: Dictionary mapping speaker IDs to their opinion stances
            contradictions: List of contradiction records
            
        Returns:
            Dictionary mapping speaker IDs to consistency metrics:
            {
                speaker_id: {
                    'opinion_count': int,
                    'stance_change_count': int,
                    'contradiction_count': int,
                    'consistency_score': float,  # 0.0 to 1.0
                    'flip_flop_count': int,
                    'major_reversal_count': int
                }
            }
        """
        logger.info("Analyzing speaker consistency")
        
        # Detect stance changes
        stance_changes = self.detect_stance_changes(speaker_stances)
        
        # Calculate consistency metrics for each speaker
        consistency_metrics = {}
        
        # Group contradictions by speaker
        speaker_contradictions = defaultdict(list)
        for contradiction in contradictions:
            speaker_contradictions[contradiction['speaker_id']].append(contradiction)
        
        # Process each speaker
        for speaker_id, opinions_map in speaker_stances.items():
            # Count opinions
            opinion_count = len(opinions_map)
            
            # Count stance changes
            stance_change_count = sum(len(changes) for changes in stance_changes.get(speaker_id, {}).values())
            
            # Count contradictions
            contradiction_count = len(speaker_contradictions.get(speaker_id, []))
            
            # Count major reversals and flip-flops
            flip_flop_count = 0
            major_reversal_count = 0
            
            for opinion_id, changes in stance_changes.get(speaker_id, {}).items():
                for change in changes:
                    if change['change_magnitude'] in ['major', 'reversal']:
                        major_reversal_count += 1
                    
                    # A flip-flop is when someone goes back to a previous stance
                    if change['to_stance'] == 'support' and change['from_stance'] == 'oppose':
                        for prev_change in changes:
                            if prev_change['to_stance'] == 'oppose' and prev_change['from_stance'] == 'support':
                                flip_flop_count += 1
                                break
            
            # Calculate consistency score (higher is more consistent)
            if opinion_count == 0:
                consistency_score = 0.0
            else:
                # Base score starts at 1.0 (perfect consistency)
                consistency_score = 1.0
                
                # Reduce for each type of inconsistency
                consistency_score -= (stance_change_count / (opinion_count * 2.0)) * 0.3  # Minor changes
                consistency_score -= (contradiction_count / (opinion_count * 2.0)) * 0.4  # Contradictions
                consistency_score -= (flip_flop_count / (opinion_count * 1.0)) * 0.5  # Flip-flops
                consistency_score -= (major_reversal_count / (opinion_count * 1.0)) * 0.6  # Major reversals
                
                # Ensure score is between 0 and 1
                consistency_score = max(0.0, min(1.0, consistency_score))
            
            # Create consistency metrics record
            consistency_metrics[speaker_id] = {
                'opinion_count': opinion_count,
                'stance_change_count': stance_change_count,
                'contradiction_count': contradiction_count,
                'consistency_score': consistency_score,
                'flip_flop_count': flip_flop_count,
                'major_reversal_count': major_reversal_count
            }
        
        return consistency_metrics
    
    def analyze_speaker_behavior(
        self,
        opinions: List[Opinion]
    ) -> Dict[str, Any]:
        """
        Perform comprehensive analysis of speaker behavior across opinions.
        
        Args:
            opinions: List of opinion objects
            
        Returns:
            Dictionary with analysis results
        """
        logger.info(f"Analyzing speaker behavior across {len(opinions)} opinions")
        
        # Track speaker stances
        speaker_stances = self.track_speaker_stances(opinions)
        
        # Detect contradictions
        contradictions = self.detect_contradictions(speaker_stances)
        
        # Generate previous stances
        previous_stances = self.generate_previous_stances(opinions)
        
        # Analyze speaker consistency
        consistency_metrics = self.analyze_speaker_consistency(speaker_stances, contradictions)
        
        return {
            'speaker_stances': speaker_stances,
            'contradictions': contradictions,
            'previous_stances': previous_stances,
            'consistency_metrics': consistency_metrics
        } 