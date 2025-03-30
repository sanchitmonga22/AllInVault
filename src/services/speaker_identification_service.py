"""
Speaker Identification Service

This module provides functionality for identifying and mapping anonymous speakers 
from transcripts to actual speaker names.
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
import re
import logging
from collections import Counter

from src.models.podcast_episode import PodcastEpisode
from src.services.llm_service import LLMService

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SpeakerIdentificationService:
    """Service for identifying speakers in podcast transcripts."""
    
    def __init__(self, 
                 default_speakers: Optional[Dict] = None,
                 use_llm: bool = False,
                 llm_provider: str = "openai",
                 llm_api_key: Optional[str] = None,
                 llm_model: Optional[str] = None):
        """
        Initialize the speaker identification service.
        
        Args:
            default_speakers: Dictionary of default speakers with their IDs and names
            use_llm: Whether to use LLM for speaker identification
            llm_provider: LLM provider ('openai' or 'deepseq')
            llm_api_key: API key for the LLM provider
            llm_model: Model name for the LLM provider
        """
        # Default mapping of known podcast hosts
        self.default_speakers = default_speakers or {
            "chamath": {"id": 0, "full_name": "Chamath Palihapitiya"},
            "jason": {"id": 1, "full_name": "Jason Calacanis"},
            "david": {"id": 2, "full_name": "David Sacks", "alt_name": "Sacks"},
            "friedberg": {"id": 3, "full_name": "David Friedberg"}
        }
        
        # Common speaker patterns
        self.name_patterns = {
            re.compile(r'\b(chamath|palihapitiya)\b', re.IGNORECASE): {"full_name": "Chamath Palihapitiya"},
            re.compile(r'\b(jason|calacanis|jake|jacal)\b', re.IGNORECASE): {"full_name": "Jason Calacanis"},
            re.compile(r'\b(david\s+sacks|sacks)\b', re.IGNORECASE): {"full_name": "David Sacks"},
            re.compile(r'\b(david\s+friedberg|friedberg)\b', re.IGNORECASE): {"full_name": "David Friedberg"},
            re.compile(r'\bjacal\b', re.IGNORECASE): {"full_name": "Jason Calacanis"},
            re.compile(r'\bbesties\b', re.IGNORECASE): {"full_name": "All Hosts"}
        }
        
        # Self-introduction patterns
        self.intro_patterns = [
            re.compile(r"(?:i am|i'm|this is)\s+([a-z]+(?:\s+[a-z]+){0,2})", re.IGNORECASE),
            re.compile(r"([a-z]+(?:\s+[a-z]+){0,2}) here", re.IGNORECASE),
            re.compile(r"([a-z]+(?:\s+[a-z]+){0,2}) speaking", re.IGNORECASE)
        ]
        
        # Speaker voice characteristics (placeholder for future implementation)
        self.speaker_fingerprints = {}
        
        # Cross-episode speaker history
        self.speaker_history = {}
        
        # LLM integration
        self.use_llm = use_llm
        self.llm_service = None
        
        if use_llm:
            try:
                self.llm_service = LLMService(
                    provider=llm_provider,
                    api_key=llm_api_key,
                    model=llm_model
                )
                logger.info(f"LLM integration enabled with provider: {llm_provider}")
            except Exception as e:
                logger.error(f"Failed to initialize LLM service: {e}")
                logger.warning("Continuing with heuristic-based speaker identification only")
                self.use_llm = False
    
    def load_transcript(self, transcript_path: str) -> Dict:
        """
        Load transcript data from file.
        
        Args:
            transcript_path: Path to the transcript JSON file
            
        Returns:
            Dictionary with transcript data
        """
        try:
            with open(transcript_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading transcript: {e}")
            return {}
    
    def extract_speakers_from_transcript(self, transcript_data: Dict) -> Dict[int, Dict]:
        """
        Extract unique speaker IDs from transcript data.
        
        Args:
            transcript_data: Transcript data dictionary
            
        Returns:
            Dictionary mapping speaker IDs to speaker info dictionaries
        """
        speakers = {}
        
        if not transcript_data or 'results' not in transcript_data:
            return speakers
        
        # Extract from utterances if available
        if 'utterances' in transcript_data['results']:
            for utterance in transcript_data['results']['utterances']:
                if 'speaker' in utterance:
                    speaker_id = int(utterance['speaker'])
                    if speaker_id not in speakers:
                        speakers[speaker_id] = {
                            "id": speaker_id,
                            "speaker_tag": f"Speaker {speaker_id}",
                            "name": None,
                            "utterance_count": 0,
                            "samples": [],
                            "confidence": 0.0
                        }
                    
                    speakers[speaker_id]["utterance_count"] += 1
                    
                    # Store sample utterances for later analysis
                    if len(speakers[speaker_id]["samples"]) < 10 and 'transcript' in utterance:
                        speakers[speaker_id]["samples"].append(utterance['transcript'])
        
        return speakers
    
    def extract_potential_guests_from_metadata(self, episode: PodcastEpisode) -> Set[str]:
        """
        Extract potential guest names from episode metadata.
        
        Args:
            episode: The podcast episode
            
        Returns:
            Set of potential guest names
        """
        potential_guests = set()
        
        # Extract from title
        title = episode.title
        # Look for patterns like "with Guest Name" or "feat. Guest Name"
        title_patterns = [
            re.compile(r"(?:with|featuring|feat\.?|ft\.?)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})", re.IGNORECASE),
            re.compile(r"(?:E\d+\s*[:|-]\s*)([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3})", re.IGNORECASE)
        ]
        
        for pattern in title_patterns:
            matches = pattern.findall(title)
            for match in matches:
                if match and not any(host.lower() in match.lower() for host in [s["full_name"] for s in self.default_speakers.values()]):
                    potential_guests.add(match.strip())
        
        # Extract from description
        description = episode.description
        # Look for mentions of people who aren't hosts
        # Simplified pattern - in reality this needs more sophisticated NER
        description_pattern = re.compile(r"([A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,2})")
        matches = description_pattern.findall(description)
        
        for match in matches:
            # Filter out common words, hosts, etc.
            if (match and len(match) > 5 and 
                " " in match and  # At least first and last name
                not match.lower().startswith(("the", "this", "that", "these", "those", "they", "there")) and
                not any(host.lower() in match.lower() for host in [s["full_name"] for s in self.default_speakers.values()])):
                potential_guests.add(match.strip())
        
        return potential_guests
    
    def find_self_introductions(self, transcript_data: Dict) -> Dict[int, str]:
        """
        Find speakers introducing themselves in the transcript.
        
        Args:
            transcript_data: Transcript data dictionary
            
        Returns:
            Dictionary mapping speaker IDs to their names
        """
        self_introductions = {}
        
        if not transcript_data or 'results' not in transcript_data or 'utterances' not in transcript_data['results']:
            return self_introductions
        
        utterances = transcript_data['results']['utterances']
        
        for utterance in utterances:
            if 'speaker' not in utterance or 'transcript' not in utterance:
                continue
                
            speaker_id = int(utterance['speaker'])
            text = utterance['transcript']
            
            # Check for self-introduction patterns
            for pattern in self.intro_patterns:
                matches = pattern.findall(text)
                if matches:
                    # Take the first match as the potential name
                    name = matches[0].strip()
                    # Filter out common words that aren't names
                    if (name and 
                        not name.lower() in ["me", "myself", "here", "speaking", "going", "i", "am", "a", "the"]):
                        self_introductions[speaker_id] = name
        
        return self_introductions
    
    def identify_speakers_by_name_mentions(self, speakers: Dict[int, Dict], transcript_data: Dict) -> Dict[int, Dict]:
        """
        Identify speakers by mentions of their names in transcript.
        
        Args:
            speakers: Dictionary of speaker information
            transcript_data: Transcript data dictionary
            
        Returns:
            Updated speakers dictionary with identified names
        """
        if not transcript_data or 'results' not in transcript_data or 'utterances' not in transcript_data['results']:
            return speakers
        
        utterances = transcript_data['results']['utterances']
        direct_address_map = {}
        
        # First pass: find direct addresses
        for i, utterance in enumerate(utterances):
            if 'speaker' not in utterance or 'transcript' not in utterance:
                continue
                
            current_speaker_id = int(utterance['speaker'])
            current_text = utterance['transcript']
            
            # Check for direct address patterns like "Hey Chamath" or "Jason, what do you think?"
            for pattern, speaker_info in self.name_patterns.items():
                matches = pattern.findall(current_text)
                if matches:
                    # The mentioned name likely belongs to a different speaker than the current one
                    addressed_name = speaker_info["full_name"]
                    
                    # Check next utterance to see who responds
                    if i < len(utterances) - 1 and 'speaker' in utterances[i+1]:
                        next_speaker_id = int(utterances[i+1]['speaker'])
                        if next_speaker_id != current_speaker_id:
                            if next_speaker_id not in direct_address_map:
                                direct_address_map[next_speaker_id] = []
                            direct_address_map[next_speaker_id].append(addressed_name)
        
        # Apply the most common direct address for each speaker
        for speaker_id, names in direct_address_map.items():
            if speaker_id in speakers and speakers[speaker_id]["name"] is None:
                most_common_name = Counter(names).most_common(1)
                if most_common_name:
                    speakers[speaker_id]["name"] = most_common_name[0][0]
                    speakers[speaker_id]["confidence"] = min(0.7, speakers[speaker_id]["confidence"] + 0.2)
        
        return speakers
    
    def identify_speakers_from_intro(self, speakers: Dict[int, Dict], transcript_data: Dict) -> Dict[int, Dict]:
        """
        Identify speakers from podcast intro/outro sections.
        
        Args:
            speakers: Dictionary of speaker information
            transcript_data: Transcript data dictionary
            
        Returns:
            Updated speakers dictionary with identified names
        """
        if not transcript_data or 'results' not in transcript_data or 'utterances' not in transcript_data['results']:
            return speakers
        
        # Look at first few and last few utterances for intro/outro patterns
        utterances = transcript_data['results']['utterances']
        intro_range = min(15, len(utterances))
        outro_range = min(15, len(utterances))
        
        # Common intro patterns
        intro_pattern = re.compile(r'\b(welcome to|this is|all-in podcast|episode \d+|besties)\b', re.IGNORECASE)
        host_pattern = re.compile(r'\b(chamath|jason|david|sacks|friedberg|calacanis|palihapitiya)\b', re.IGNORECASE)
        
        # Self-introductions from intro section
        self_introductions = {}
        
        # Check intro
        for i in range(intro_range):
            if 'transcript' in utterances[i] and 'speaker' in utterances[i]:
                text = utterances[i]['transcript']
                speaker_id = int(utterances[i]['speaker'])
                
                if intro_pattern.search(text):
                    # This is likely an intro, check for host mentions
                    # The person speaking the intro is often Jason (common for All-In podcast)
                    if speakers[speaker_id]["name"] is None:
                        # Assign based on intro speaker heuristic (e.g., Jason often does intros)
                        if "jason" in text.lower() or "calacanis" in text.lower() or "jake" in text.lower():
                            speakers[speaker_id]["name"] = "Jason Calacanis"
                            speakers[speaker_id]["confidence"] = min(0.9, speakers[speaker_id]["confidence"] + 0.4)
                
                # Check for self-introductions
                for pattern in self.intro_patterns:
                    matches = pattern.findall(text)
                    if matches:
                        # Combine with known host names to improve accuracy
                        name = matches[0].strip()
                        for host_name, host_info in self.default_speakers.items():
                            if host_name.lower() in name.lower():
                                self_introductions[speaker_id] = host_info["full_name"]
                                speakers[speaker_id]["confidence"] = min(0.95, speakers[speaker_id]["confidence"] + 0.5)
        
        # Check outro
        for i in range(len(utterances) - outro_range, len(utterances)):
            if i >= 0 and 'transcript' in utterances[i] and 'speaker' in utterances[i]:
                text = utterances[i]['transcript']
                outro_pattern = re.compile(r'\b(thanks for|thank you|see you next|that\'s it for|episode|all-in podcast)\b', re.IGNORECASE)
                if outro_pattern.search(text):
                    # This is likely an outro, check for host mentions
                    speaker_id = int(utterances[i]['speaker'])
                    if speakers[speaker_id]["name"] is None and host_pattern.search(text):
                        # Try to identify the speaker from outro context
                        for name in ["Jason Calacanis", "Chamath Palihapitiya", "David Sacks", "David Friedberg"]:
                            if name.lower().split()[0] in text.lower():
                                speakers[speaker_id]["name"] = name
                                speakers[speaker_id]["confidence"] = min(0.8, speakers[speaker_id]["confidence"] + 0.3)
                                break
        
        # Apply self-introductions with high confidence
        for speaker_id, name in self_introductions.items():
            if speaker_id in speakers and (speakers[speaker_id]["name"] is None or speakers[speaker_id]["confidence"] < 0.8):
                speakers[speaker_id]["name"] = name
                speakers[speaker_id]["confidence"] = min(0.9, speakers[speaker_id]["confidence"] + 0.4)
        
        return speakers
    
    def match_speakers_to_guests(
        self, 
        speakers: Dict[int, Dict], 
        potential_guests: Set[str],
        transcript_data: Dict
    ) -> Dict[int, Dict]:
        """
        Match potential guest names to unidentified speakers.
        
        Args:
            speakers: Dictionary of speaker information
            potential_guests: Set of potential guest names
            transcript_data: Transcript data dictionary
            
        Returns:
            Updated speakers dictionary with identified guests
        """
        if not potential_guests or not transcript_data:
            return speakers
            
        utterances = transcript_data['results']['utterances']
        guest_counts = {guest: 0 for guest in potential_guests}
        
        # Count name mentions per speaker
        speaker_name_mentions = {speaker_id: {} for speaker_id in speakers.keys()}
        
        for utterance in utterances:
            if 'speaker' not in utterance or 'transcript' not in utterance:
                continue
                
            speaker_id = int(utterance['speaker'])
            text = utterance['transcript']
            
            # Count mentions of potential guest names in each speaker's utterances
            for guest in potential_guests:
                # Create a regex pattern for the guest name
                pattern = re.compile(r'\b' + re.escape(guest) + r'\b', re.IGNORECASE)
                matches = pattern.findall(text)
                
                if matches:
                    if guest not in speaker_name_mentions[speaker_id]:
                        speaker_name_mentions[speaker_id][guest] = 0
                    speaker_name_mentions[speaker_id][guest] += len(matches)
        
        # Identify guests by analyzing who speaks most about them vs. who IS them
        for guest in potential_guests:
            # Calculate total mentions across all speakers
            total_mentions = sum(speaker_name_mentions[speaker_id].get(guest, 0) for speaker_id in speakers.keys())
            
            if total_mentions == 0:
                continue
                
            # Calculate percentage of mentions by each speaker
            mention_percentages = {}
            for speaker_id in speakers.keys():
                mentions = speaker_name_mentions[speaker_id].get(guest, 0)
                mention_percentages[speaker_id] = mentions / total_mentions if total_mentions > 0 else 0
            
            # Analyze the pattern - in general, people talk ABOUT guests more than the guests talk about themselves
            # Find the speaker with the LOWEST percentage of mentions who still has significant utterances
            # This is often the actual person (they don't refer to themselves by name much)
            min_mentions_speaker = None
            min_mentions_pct = 1.0
            
            for speaker_id, pct in mention_percentages.items():
                # Only consider speakers with significant utterances
                if speakers[speaker_id]["utterance_count"] > 10:
                    # If they never mention the name but speak a lot, they might BE that person
                    if pct == 0:
                        min_mentions_speaker = speaker_id
                        min_mentions_pct = 0
                        break
                    # Otherwise find the one with least mentions
                    elif 0 < pct < min_mentions_pct:
                        min_mentions_speaker = speaker_id
                        min_mentions_pct = pct
            
            # Assign the guest name if we found a good candidate
            if min_mentions_speaker is not None and speakers[min_mentions_speaker]["name"] is None:
                speakers[min_mentions_speaker]["name"] = guest
                speakers[min_mentions_speaker]["confidence"] = min(0.75, speakers[min_mentions_speaker]["confidence"] + 0.35)
                speakers[min_mentions_speaker]["is_guest"] = True
        
        return speakers
    
    def analyze_speaker_patterns(self, speakers: Dict[int, Dict], transcript_data: Dict) -> Dict[int, Dict]:
        """
        Analyze speaking patterns to identify speakers.
        
        Args:
            speakers: Dictionary of speaker information
            transcript_data: Transcript data dictionary
            
        Returns:
            Updated speakers dictionary with identified names
        """
        if not transcript_data or 'results' not in transcript_data or 'utterances' not in transcript_data['results']:
            return speakers
            
        utterances = transcript_data['results']['utterances']
        
        # Calculate statistics for each speaker
        for speaker_id, speaker_info in speakers.items():
            # Skip already identified speakers with high confidence
            if speaker_info["name"] is not None and speaker_info["confidence"] > 0.8:
                continue
                
            # Gather this speaker's utterances
            speaker_utterances = [u for u in utterances if 'speaker' in u and int(u['speaker']) == speaker_id]
            
            if not speaker_utterances:
                continue
                
            # Calculate average utterance length
            avg_length = sum(len(u.get('transcript', '')) for u in speaker_utterances) / len(speaker_utterances)
            
            # Count filler words and phrases (characteristic of each speaker)
            filler_patterns = {
                "jason": re.compile(r'\b(you know what i mean|i mean|right|um|uh)\b', re.IGNORECASE),
                "chamath": re.compile(r'\b(obviously|fundamentally|basically|right|sort of)\b', re.IGNORECASE),
                "david_sacks": re.compile(r'\b(look|i think|the reality is|the point is)\b', re.IGNORECASE),
                "friedberg": re.compile(r'\b(actually|sort of|if you look at|data|trend)\b', re.IGNORECASE)
            }
            
            filler_counts = {}
            for name, pattern in filler_patterns.items():
                count = sum(len(pattern.findall(u.get('transcript', ''))) for u in speaker_utterances)
                filler_counts[name] = count / len(speaker_utterances) if speaker_utterances else 0
            
            # Determine the most likely speaker based on filler word usage
            max_filler_speaker = max(filler_counts.items(), key=lambda x: x[1])
            if max_filler_speaker[1] > 0.5:  # Threshold for significance
                if max_filler_speaker[0] == "jason":
                    speakers[speaker_id]["name"] = "Jason Calacanis"
                elif max_filler_speaker[0] == "chamath":
                    speakers[speaker_id]["name"] = "Chamath Palihapitiya"
                elif max_filler_speaker[0] == "david_sacks":
                    speakers[speaker_id]["name"] = "David Sacks"
                elif max_filler_speaker[0] == "friedberg":
                    speakers[speaker_id]["name"] = "David Friedberg"
                
                speakers[speaker_id]["confidence"] = min(0.7, speakers[speaker_id]["confidence"] + 0.2)
        
        return speakers
    
    def assign_speakers_by_heuristics(self, speakers: Dict[int, Dict]) -> Dict[int, Dict]:
        """
        Assign remaining speakers based on heuristics and defaults.
        
        Args:
            speakers: Dictionary of speaker information
            
        Returns:
            Updated speakers dictionary with assigned names
        """
        # Initial speakers usually follow a pattern (e.g., in All-In podcast)
        # Often Jason (1) starts, followed by introductions of other hosts
        
        # Create a list of default speakers to assign
        default_speaker_names = [s["full_name"] for s in self.default_speakers.values()]
        
        # Count how many speakers already identified
        identified_hosts = set()
        for speaker_id, info in speakers.items():
            if info["name"] in default_speaker_names:
                identified_hosts.add(info["name"])
        
        # Get remaining default hosts
        remaining_hosts = [name for name in default_speaker_names if name not in identified_hosts]
        
        # Assign remaining unidentified speakers using defaults in order
        default_idx = 0
        for speaker_id in sorted(speakers.keys()):
            # Only assign to speakers with low confidence or no name
            if (speakers[speaker_id]["name"] is None or speakers[speaker_id]["confidence"] < 0.5) and default_idx < len(remaining_hosts):
                speakers[speaker_id]["name"] = remaining_hosts[default_idx]
                speakers[speaker_id]["confidence"] = min(0.6, speakers[speaker_id]["confidence"] + 0.2)
                default_idx += 1
        
        return speakers
    
    def identify_speakers_with_llm(self, 
                              speakers: Dict[int, Dict], 
                              episode: PodcastEpisode, 
                              transcript_data: Dict) -> Dict[int, Dict]:
        """
        Use LLM to identify speakers in transcript.
        
        Args:
            speakers: Dictionary mapping speaker IDs to speaker info dictionaries
            episode: The podcast episode
            transcript_data: The transcript data
            
        Returns:
            Updated speakers dictionary with LLM-identified speakers
        """
        # If LLM integration is not configured or unavailable, skip this step
        if not self.use_llm or not self.llm_service:
            logger.info("LLM integration is not available, skipping LLM-based identification")
            return speakers
        
        try:
            # Extract a representative sample from the transcript
            transcript_sample = self._get_transcript_sample(transcript_data, max_length=4000)
            logger.info(f"Using transcript sample for LLM:\n{transcript_sample[:500]}...(truncated)")
            
            # Use LLM to identify potential speakers
            llm_speakers = self.llm_service.extract_speakers_from_episode(
                episode, transcript_sample
            )
            
            logger.info(f"LLM identified speakers: {llm_speakers}")
            
            # Process hosts from LLM results
            if "hosts" in llm_speakers:
                # Create a mapping of host names to confidence scores
                host_confidence = {}
                for host in llm_speakers["hosts"]:
                    name = host.get("name")
                    confidence = host.get("confidence", 0.8)  # Default to 0.8 if not provided
                    if name:
                        host_confidence[name] = confidence
                
                # First pass: assign hosts with high confidence
                # Find speakers with the most utterances to assign to hosts
                speaker_utterance_counts = [(id, info["utterance_count"]) 
                                           for id, info in speakers.items() 
                                           if info["name"] is None or info["confidence"] < 0.7]
                speaker_utterance_counts.sort(key=lambda x: x[1], reverse=True)
                
                # Assign hosts to the speakers with most utterances
                for host_name, confidence in host_confidence.items():
                    if not speaker_utterance_counts:
                        break
                    
                    speaker_id, _ = speaker_utterance_counts.pop(0)
                    speakers[speaker_id]["name"] = host_name
                    speakers[speaker_id]["confidence"] = min(0.85, speakers[speaker_id]["confidence"] + confidence)
                    speakers[speaker_id]["identified_by_llm"] = True
            
            # Process guests from LLM results
            if "guests" in llm_speakers and llm_speakers["guests"]:
                # Create a set of potential guest names
                guest_names = {guest.get("name"): guest.get("confidence", 0.7)
                             for guest in llm_speakers["guests"] if guest.get("name")}
                
                # Find unassigned speakers for guests
                unassigned_speakers = [id for id, info in speakers.items() 
                                     if info["name"] is None or info["confidence"] < 0.6]
                
                # Assign guests to unassigned speakers
                for i, speaker_id in enumerate(unassigned_speakers):
                    if i < len(guest_names):
                        guest_name = list(guest_names.keys())[i]
                        confidence = guest_names[guest_name]
                        speakers[speaker_id]["name"] = guest_name
                        speakers[speaker_id]["confidence"] = min(0.8, speakers[speaker_id]["confidence"] + confidence)
                        speakers[speaker_id]["is_guest"] = True
                        speakers[speaker_id]["identified_by_llm"] = True
            
            return speakers
            
        except Exception as e:
            logger.error(f"Error using LLM for speaker identification: {e}")
            return speakers
    
    def identify_speakers(self, transcript_path: str, episode: Optional[PodcastEpisode] = None) -> Dict[int, Dict]:
        """
        Identify speakers in a transcript using multiple strategies.
        
        Args:
            transcript_path: Path to the transcript JSON file
            episode: Optional episode metadata to help with identification
            
        Returns:
            Dictionary mapping speaker IDs to speaker info
        """
        # Load transcript data
        transcript_data = self.load_transcript(transcript_path)
        if not transcript_data:
            return {}
        
        # Extract speakers
        speakers = self.extract_speakers_from_transcript(transcript_data)
        
        # LLM-based identification (if enabled)
        if self.use_llm and episode:
            speakers = self.identify_speakers_with_llm(speakers, episode, transcript_data)
        
        # Find potential guest speakers from episode metadata
        potential_guests = set()
        if episode:
            potential_guests = self.extract_potential_guests_from_metadata(episode)
            logger.info(f"Potential guests extracted from metadata: {potential_guests}")
        
        # Find self-introductions
        self_introductions = self.find_self_introductions(transcript_data)
        for speaker_id, name in self_introductions.items():
            if speaker_id in speakers and (speakers[speaker_id]["name"] is None or speakers[speaker_id]["confidence"] < 0.8):
                speakers[speaker_id]["name"] = name
                speakers[speaker_id]["confidence"] = min(0.8, speakers[speaker_id].get("confidence", 0) + 0.4)
        
        # Apply identification methods in sequence, with increasing specificity
        speakers = self.identify_speakers_from_intro(speakers, transcript_data)
        speakers = self.identify_speakers_by_name_mentions(speakers, transcript_data)
        
        if potential_guests:
            speakers = self.match_speakers_to_guests(speakers, potential_guests, transcript_data)
        
        speakers = self.analyze_speaker_patterns(speakers, transcript_data)
        
        # Only use heuristics for speakers that haven't been identified
        # or have low confidence
        unidentified_speakers = {
            id: info for id, info in speakers.items()
            if info["name"] is None or info["confidence"] < 0.5
        }
        
        if unidentified_speakers:
            speakers = self.assign_speakers_by_heuristics(speakers)
        
        # Clean up and finalize
        for speaker_id, info in speakers.items():
            if info["name"] is None:
                info["name"] = f"Unknown Speaker {speaker_id}"
                info["confidence"] = 0.1
                info["is_unknown"] = True
        
        return speakers
    
    def process_episode(self, episode: PodcastEpisode, transcripts_dir: str) -> PodcastEpisode:
        """
        Process an episode to identify speakers and update metadata.
        
        Args:
            episode: PodcastEpisode to process
            transcripts_dir: Directory containing transcript files
            
        Returns:
            Updated PodcastEpisode with speaker information
        """
        if not episode.transcript_filename:
            logger.warning(f"Episode {episode.title} has no transcript")
            return episode
        
        transcript_path = os.path.join(transcripts_dir, episode.transcript_filename)
        if not os.path.exists(transcript_path):
            logger.warning(f"Transcript file {transcript_path} not found")
            return episode
        
        # Identify speakers using the episode metadata for context
        speakers = self.identify_speakers(transcript_path, episode)
        
        # Update episode metadata with speaker information
        if speakers:
            episode.speaker_count = len(speakers)
            
            # Create speaker metadata
            speaker_metadata = {}
            for speaker_id, speaker_info in speakers.items():
                speaker_metadata[str(speaker_id)] = {
                    "name": speaker_info["name"],
                    "utterance_count": speaker_info["utterance_count"],
                    "confidence": speaker_info.get("confidence", 0),
                    "is_guest": speaker_info.get("is_guest", False),
                    "is_unknown": speaker_info.get("is_unknown", False),
                    "identified_by_llm": speaker_info.get("identified_by_llm", False)
                }
            
            # Update episode metadata
            if "speakers" not in episode.metadata:
                episode.metadata["speakers"] = speaker_metadata
            else:
                episode.metadata["speakers"].update(speaker_metadata)
        
        return episode
    
    def process_episodes(self, episodes: List[PodcastEpisode], transcripts_dir: str) -> List[PodcastEpisode]:
        """
        Process multiple episodes to identify speakers.
        
        Args:
            episodes: List of PodcastEpisode instances to process
            transcripts_dir: Directory containing transcript files
            
        Returns:
            List of updated PodcastEpisode instances with speaker information
        """
        updated_episodes = []
        
        for episode in episodes:
            updated_episode = self.process_episode(episode, transcripts_dir)
            updated_episodes.append(updated_episode)
        
        return updated_episodes
    
    def _get_transcript_sample(self, transcript_data: Dict, max_length: int = 4000) -> str:
        """
        Extract a representative sample from the transcript for LLM analysis.
        
        Args:
            transcript_data: The transcript data
            max_length: Maximum length of sample in characters
            
        Returns:
            A string containing a sample of utterances
        """
        sample_utterances = []
        total_length = 0
        
        # Extract from utterances if available
        if 'results' in transcript_data and 'utterances' in transcript_data['results']:
            utterances = transcript_data['results']['utterances']
            
            # Sample from beginning, middle, and end of the transcript for better context
            sample_points = [
                (0, min(20, len(utterances))),                      # Beginning (first 20 utterances)
                (len(utterances)//2, min(20, len(utterances)//2)),  # Middle (20 utterances from middle)
                (max(0, len(utterances)-20), min(20, len(utterances)))  # End (last 20 utterances)
            ]
            
            for start_idx, count in sample_points:
                # Skip if we already have enough text
                if total_length >= max_length:
                    break
                    
                # Get a section header
                if start_idx == 0:
                    sample_utterances.append("--- BEGINNING OF TRANSCRIPT ---")
                elif start_idx == len(utterances)//2:
                    sample_utterances.append("--- MIDDLE OF TRANSCRIPT ---")
                else:
                    sample_utterances.append("--- END OF TRANSCRIPT ---")
                
                # Extract utterances from this section
                section_length = 0
                end_idx = min(start_idx + count, len(utterances))
                
                for i in range(start_idx, end_idx):
                    if 'speaker' in utterances[i] and 'transcript' in utterances[i]:
                        utterance_text = f"Speaker {utterances[i]['speaker']}: {utterances[i]['transcript']}"
                        sample_utterances.append(utterance_text)
                        section_length += len(utterance_text)
                        total_length += len(utterance_text)
                        
                        # If this section is getting too long, move to next section
                        if section_length > max_length / 3:
                            break
        
        # If we have no utterances, try to extract from plain transcript
        if not sample_utterances and 'results' in transcript_data and 'transcript' in transcript_data['results']:
            # Split into lines and take samples from beginning, middle, and end
            transcript_lines = transcript_data['results']['transcript'].split('\n')
            
            if len(transcript_lines) > 30:
                # Beginning
                sample_utterances.append("--- BEGINNING OF TRANSCRIPT ---")
                sample_utterances.extend(transcript_lines[:10])
                
                # Middle
                middle_start = len(transcript_lines) // 2 - 5
                sample_utterances.append("--- MIDDLE OF TRANSCRIPT ---")
                sample_utterances.extend(transcript_lines[middle_start:middle_start+10])
                
                # End
                sample_utterances.append("--- END OF TRANSCRIPT ---")
                sample_utterances.extend(transcript_lines[-10:])
            else:
                # Just take all lines if there aren't many
                sample_utterances.extend(transcript_lines)
        
        return "\n".join(sample_utterances) 