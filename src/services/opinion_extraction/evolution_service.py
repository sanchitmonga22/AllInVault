"""
Evolution Detection Service

This module provides functionality for detecting and tracking opinion evolution
and building evolution chains and speaker journeys.
"""

import logging
import uuid
from typing import Dict, List, Optional, Any, Set, Tuple
from datetime import datetime
from collections import defaultdict

from src.models.opinions.opinion import Opinion, OpinionAppearance, SpeakerStance
from src.models.opinions.evolution import EvolutionChain, EvolutionNode, EvolutionPattern
from src.models.opinions.speaker_journey import SpeakerJourney, SpeakerJourneyNode
from src.models.opinions.relationship import Relationship, RelationshipEvidence
from src.repositories.opinion_repository import OpinionRepository
from src.services.opinion_extraction.base_service import BaseOpinionService
from src.services.opinion_extraction.relationship_service import RelationshipType

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class EvolutionDetectionService(BaseOpinionService):
    """Service for detecting opinion evolution and building evolution chains."""
    
    def __init__(self, 
                 opinion_repository: Optional[OpinionRepository] = None):
        """
        Initialize the evolution detection service.
        
        Args:
            opinion_repository: Repository for opinion storage
        """
        super().__init__(llm_service=None)
        self.opinion_repository = opinion_repository
    
    def build_evolution_chains(
        self,
        opinions: List[Opinion],
        relationships: List[Relationship]
    ) -> List[EvolutionChain]:
        """
        Build evolution chains from opinions and their relationships.
        
        Args:
            opinions: List of opinion objects
            relationships: List of relationship objects
            
        Returns:
            List of evolution chains
        """
        logger.info(f"Building evolution chains from {len(opinions)} opinions and {len(relationships)} relationships")
        
        # Create a map of opinion IDs to their objects
        opinion_map = {op.id: op for op in opinions}
        
        # Filter out only evolution relationships
        evolution_relationships = [
            rel for rel in relationships 
            if rel.relationship_type == RelationshipType.EVOLUTION
        ]
        
        if not evolution_relationships:
            logger.info("No evolution relationships found")
            return []
        
        # Build a directed graph of evolution relationships
        evolution_graph = defaultdict(list)
        for rel in evolution_relationships:
            # Evolution is directional: source evolves to target
            evolution_graph[rel.opinion_a_id].append({
                'target_id': rel.opinion_b_id,
                'relationship': rel
            })
        
        # Identify root opinions (those that aren't targets of any evolution)
        all_opinion_ids = set(opinion_map.keys())
        all_target_ids = {rel.opinion_b_id for rel in evolution_relationships}
        root_opinion_ids = all_opinion_ids - all_target_ids
        
        # If there are no clear roots, use opinions with no outgoing evolution relationships
        if not root_opinion_ids:
            root_opinion_ids = {op.id for op in opinions if op.id not in evolution_graph}
        
        # If still no roots, use the oldest opinions as roots
        if not root_opinion_ids:
            # Sort opinions by their earliest appearance date
            sorted_opinions = sorted(
                opinions,
                key=lambda op: min(app.date for app in op.appearances) if op.appearances else datetime.max
            )
            # Take the oldest 10% as potential roots
            potential_roots = sorted_opinions[:max(1, len(sorted_opinions) // 10)]
            root_opinion_ids = {op.id for op in potential_roots}
        
        # Build chains starting from each root
        chains = []
        visited = set()  # Track visited opinions to avoid cycles
        
        for root_id in root_opinion_ids:
            if root_id not in opinion_map:
                continue
                
            # Skip if this opinion has already been included in a chain
            if root_id in visited:
                continue
                
            root_opinion = opinion_map[root_id]
            chain = self._build_chain_from_root(
                root_opinion=root_opinion,
                opinion_map=opinion_map,
                evolution_graph=evolution_graph,
                visited=visited
            )
            
            if chain:
                chains.append(chain)
        
        logger.info(f"Built {len(chains)} evolution chains")
        return chains
    
    def _build_chain_from_root(
        self,
        root_opinion: Opinion,
        opinion_map: Dict[str, Opinion],
        evolution_graph: Dict[str, List[Dict]],
        visited: Set[str]
    ) -> Optional[EvolutionChain]:
        """
        Build an evolution chain starting from a root opinion.
        
        Args:
            root_opinion: The root opinion for this chain
            opinion_map: Map of opinion IDs to opinion objects
            evolution_graph: Graph of evolution relationships
            visited: Set of visited opinion IDs
            
        Returns:
            An evolution chain object or None if chain couldn't be built
        """
        # Create root node
        root_node = self._create_evolution_node(
            opinion=root_opinion,
            evolution_type="initial",
            description=f"Initial statement of opinion: {root_opinion.title}"
        )
        
        # Create chain
        chain = EvolutionChain(
            root_node_id=root_node.id,
            title=f"Evolution of: {root_opinion.title}",
            description=f"Evolution chain tracking the development of the opinion: {root_opinion.description}",
            category_id=root_opinion.category_id
        )
        
        # Add root node to chain
        chain.add_node(root_node)
        visited.add(root_opinion.id)
        
        # Process the chain through BFS traversal
        queue = [(root_opinion.id, root_node.id)]
        while queue:
            opinion_id, parent_node_id = queue.pop(0)
            
            # Get evolutions from this opinion
            for evolution in evolution_graph.get(opinion_id, []):
                target_id = evolution['target_id']
                relationship = evolution['relationship']
                
                # Skip if target doesn't exist or was already visited
                if target_id not in opinion_map or target_id in visited:
                    continue
                
                target_opinion = opinion_map[target_id]
                
                # Determine evolution type
                evolution_type = self._determine_evolution_type(
                    source_opinion=opinion_map[opinion_id],
                    target_opinion=target_opinion
                )
                
                # Create description
                description = relationship.description or self._generate_evolution_description(
                    source_opinion=opinion_map[opinion_id],
                    target_opinion=target_opinion,
                    evolution_type=evolution_type
                )
                
                # Create node
                node = self._create_evolution_node(
                    opinion=target_opinion,
                    evolution_type=evolution_type,
                    description=description,
                    previous_node_id=parent_node_id
                )
                
                # Add to chain
                chain.add_node(node)
                visited.add(target_id)
                
                # Continue traversal
                queue.append((target_id, node.id))
        
        # Only return the chain if it has more than just the root node
        if len(chain.nodes) > 1:
            return chain
        
        return None
    
    def _create_evolution_node(
        self,
        opinion: Opinion,
        evolution_type: str,
        description: str,
        previous_node_id: Optional[str] = None
    ) -> EvolutionNode:
        """
        Create an evolution node from an opinion.
        
        Args:
            opinion: The opinion for this node
            evolution_type: Type of evolution
            description: Description of the evolution
            previous_node_id: ID of the previous node
            
        Returns:
            Evolution node object
        """
        # Get the earliest appearance date for this opinion
        if opinion.appearances:
            episode = sorted(opinion.appearances, key=lambda app: app.date)[0]
            date = episode.date
            episode_id = episode.episode_id
        else:
            date = datetime.now()
            episode_id = "unknown"
        
        return EvolutionNode(
            opinion_id=opinion.id,
            episode_id=episode_id,
            date=date,
            evolution_type=evolution_type,
            description=description,
            previous_node_id=previous_node_id,
            metadata={'opinion_title': opinion.title}
        )
    
    def _determine_evolution_type(
        self,
        source_opinion: Opinion,
        target_opinion: Opinion
    ) -> str:
        """
        Determine the type of evolution between two opinions.
        
        Args:
            source_opinion: The source opinion
            target_opinion: The target opinion
            
        Returns:
            Evolution type as string
        """
        # TODO: Implement more sophisticated evolution type detection
        # This could use NLP or the LLM to detect the nature of the evolution
        
        # Basic heuristic approach for now
        source_description = source_opinion.description.lower()
        target_description = target_opinion.description.lower()
        
        # Check for significant length change
        length_ratio = len(target_description) / max(1, len(source_description))
        
        if length_ratio > 1.5:
            return "expansion"
        elif length_ratio < 0.75:
            return "contraction"
        
        # Look for specific terms indicating refinement
        refinement_terms = [
            "however", "but", "although", "nevertheless", "despite", "actually",
            "clarify", "adjust", "refine", "revise", "correct", "modify", "update"
        ]
        
        for term in refinement_terms:
            if term in target_description and term not in source_description:
                return "refinement"
        
        # Look for terms indicating pivot
        pivot_terms = [
            "instead", "rather", "changed", "shift", "pivot", "reverse", "opposite",
            "no longer", "changed my mind", "now believe", "previously thought"
        ]
        
        for term in pivot_terms:
            if term in target_description:
                return "pivot"
        
        # Default evolution type
        return "development"
    
    def _generate_evolution_description(
        self,
        source_opinion: Opinion,
        target_opinion: Opinion,
        evolution_type: str
    ) -> str:
        """
        Generate a description of the evolution between two opinions.
        
        Args:
            source_opinion: The source opinion
            target_opinion: The target opinion
            evolution_type: Type of evolution
            
        Returns:
            Description of the evolution
        """
        if evolution_type == "expansion":
            return f"Expanded on original opinion with additional details or examples"
        elif evolution_type == "contraction":
            return f"Condensed or focused the opinion on key aspects"
        elif evolution_type == "refinement":
            return f"Refined the opinion with more nuanced perspective"
        elif evolution_type == "pivot":
            return f"Significantly changed position from the original opinion"
        else:
            return f"Developed the opinion further over time"
    
    def build_speaker_journeys(
        self,
        opinions: List[Opinion],
        evolution_chains: List[EvolutionChain]
    ) -> List[SpeakerJourney]:
        """
        Build speaker journeys tracking how speakers' stances evolve across opinions.
        
        Args:
            opinions: List of opinion objects
            evolution_chains: List of evolution chain objects
            
        Returns:
            List of speaker journeys
        """
        logger.info(f"Building speaker journeys from {len(opinions)} opinions and {len(evolution_chains)} evolution chains")
        
        # Create a map of opinion IDs to their objects
        opinion_map = {op.id: op for op in opinions}
        
        # Collect all speakers across all opinions
        all_speakers = defaultdict(set)  # speaker_id -> set of opinion_ids
        speaker_names = {}  # speaker_id -> speaker_name
        
        for opinion in opinions:
            for appearance in opinion.appearances:
                for speaker in appearance.speakers:
                    all_speakers[speaker.speaker_id].add(opinion.id)
                    speaker_names[speaker.speaker_id] = speaker.speaker_name
        
        # Build a journey for each speaker
        journeys = []
        for speaker_id, opinion_ids in all_speakers.items():
            speaker_name = speaker_names.get(speaker_id, f"Speaker {speaker_id}")
            
            journey = SpeakerJourney(
                speaker_id=speaker_id,
                speaker_name=speaker_name
            )
            
            # Process each chain to find the speaker's involvement
            for chain in evolution_chains:
                chain_nodes = chain.get_ordered_nodes()
                previous_node = None
                previous_stance = None
                
                for node in chain_nodes:
                    if node.opinion_id not in opinion_map:
                        continue
                        
                    opinion = opinion_map[node.opinion_id]
                    
                    # Find this speaker's stance on this opinion
                    for appearance in opinion.appearances:
                        for stance in appearance.speakers:
                            if stance.speaker_id == speaker_id:
                                # Create journey node
                                journey_node = self._create_journey_node(
                                    speaker_id=speaker_id,
                                    opinion=opinion,
                                    stance=stance,
                                    evolution_node=node,
                                    previous_node=previous_node,
                                    previous_stance=previous_stance
                                )
                                
                                journey.add_node(journey_node)
                                previous_node = journey_node
                                previous_stance = stance
                                break
            
            # Only add journeys with multiple nodes
            if len(journey.nodes) > 1:
                journeys.append(journey)
        
        logger.info(f"Built {len(journeys)} speaker journeys")
        return journeys
    
    def _create_journey_node(
        self,
        speaker_id: str,
        opinion: Opinion,
        stance: SpeakerStance,
        evolution_node: EvolutionNode,
        previous_node: Optional[SpeakerJourneyNode] = None,
        previous_stance: Optional[SpeakerStance] = None
    ) -> SpeakerJourneyNode:
        """
        Create a speaker journey node.
        
        Args:
            speaker_id: ID of the speaker
            opinion: The opinion object
            stance: The speaker's stance on this opinion
            evolution_node: The evolution node
            previous_node: Previous journey node
            previous_stance: Previous stance
            
        Returns:
            Speaker journey node object
        """
        # Get the earliest appearance date with this speaker
        date = datetime.now()
        episode_id = "unknown"
        
        for appearance in opinion.appearances:
            for app_stance in appearance.speakers:
                if app_stance.speaker_id == speaker_id:
                    date = appearance.date
                    episode_id = appearance.episode_id
                    break
        
        # Determine if stance changed
        stance_changed = False
        change_description = None
        
        if previous_stance and previous_stance.stance != stance.stance:
            stance_changed = True
            change_description = self._generate_stance_change_description(
                previous_stance=previous_stance,
                current_stance=stance
            )
        
        return SpeakerJourneyNode(
            opinion_id=opinion.id,
            speaker_id=speaker_id,
            episode_id=episode_id,
            date=date,
            stance=stance.stance,
            reasoning=stance.reasoning or "",
            previous_node_id=previous_node.id if previous_node else None,
            stance_changed=stance_changed,
            change_description=change_description
        )
    
    def _generate_stance_change_description(
        self,
        previous_stance: SpeakerStance,
        current_stance: SpeakerStance
    ) -> str:
        """
        Generate a description of a stance change.
        
        Args:
            previous_stance: Previous stance
            current_stance: Current stance
            
        Returns:
            Description of the stance change
        """
        if previous_stance.stance == "support" and current_stance.stance == "oppose":
            return "Changed from supporting to opposing this opinion"
        elif previous_stance.stance == "oppose" and current_stance.stance == "support":
            return "Changed from opposing to supporting this opinion"
        elif previous_stance.stance == "neutral" and current_stance.stance == "support":
            return "Changed from neutral to supporting this opinion"
        elif previous_stance.stance == "neutral" and current_stance.stance == "oppose":
            return "Changed from neutral to opposing this opinion"
        elif previous_stance.stance == "support" and current_stance.stance == "neutral":
            return "Moderated position from support to neutral"
        elif previous_stance.stance == "oppose" and current_stance.stance == "neutral":
            return "Moderated position from opposition to neutral"
        else:
            return f"Changed stance from {previous_stance.stance} to {current_stance.stance}"
    
    def analyze_opinion_evolution(
        self,
        opinions: List[Opinion],
        relationships: List[Relationship]
    ) -> Dict[str, Any]:
        """
        Analyze the evolution of opinions, build chains, and create speaker journeys.
        
        Args:
            opinions: List of opinion objects
            relationships: List of relationship objects
            
        Returns:
            Dictionary with evolution chains and speaker journeys
        """
        logger.info(f"Analyzing opinion evolution for {len(opinions)} opinions")
        
        # Build evolution chains
        evolution_chains = self.build_evolution_chains(
            opinions=opinions,
            relationships=relationships
        )
        
        # Build speaker journeys
        speaker_journeys = self.build_speaker_journeys(
            opinions=opinions,
            evolution_chains=evolution_chains
        )
        
        # Find common evolution patterns (future enhancement)
        # evolution_patterns = self._identify_evolution_patterns(evolution_chains)
        
        return {
            'evolution_chains': evolution_chains,
            'speaker_journeys': speaker_journeys,
            # 'evolution_patterns': evolution_patterns
        }
    
    def save_evolution_data(
        self,
        opinions: List[Opinion],
        evolution_chains: List[EvolutionChain],
        speaker_journeys: List[SpeakerJourney]
    ) -> bool:
        """
        Save evolution data back to the opinions and repository.
        
        Args:
            opinions: List of opinion objects
            evolution_chains: List of evolution chain objects
            speaker_journeys: List of speaker journey objects
            
        Returns:
            True if successful, False otherwise
        """
        if not self.opinion_repository:
            logger.warning("No opinion repository provided, cannot save evolution data")
            return False
        
        try:
            # Link evolution chains to root opinions
            opinion_map = {op.id: op for op in opinions}
            
            for chain in evolution_chains:
                if chain.root_node_id not in chain.nodes:
                    continue
                    
                root_node = chain.nodes[chain.root_node_id]
                root_opinion_id = root_node.opinion_id
                
                if root_opinion_id in opinion_map:
                    # Add evolution chain to the opinion
                    opinion_map[root_opinion_id].evolution_chain = chain.id
                    
                    # Add summary in opinion metadata
                    if 'evolution_summary' not in opinion_map[root_opinion_id].metadata:
                        opinion_map[root_opinion_id].metadata['evolution_summary'] = {}
                    
                    opinion_map[root_opinion_id].metadata['evolution_summary']['chain_id'] = chain.id
                    opinion_map[root_opinion_id].metadata['evolution_summary']['title'] = chain.title
                    opinion_map[root_opinion_id].metadata['evolution_summary']['node_count'] = len(chain.nodes)
            
            # Save the updated opinions
            for opinion in opinions:
                self.opinion_repository.save_opinion(opinion)
            
            # TODO: Save evolution chains and speaker journeys to their own repositories
            # when those are implemented
            
            return True
        
        except Exception as e:
            logger.error(f"Error saving evolution data: {e}")
            return False 