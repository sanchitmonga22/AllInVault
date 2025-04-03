"""
Utility for preparing transcript chunks for vector embeddings.
Implements intelligent chunking strategies and metadata enrichment for optimal retrieval.
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path

class EpisodeMetadataRepository:
    """
    Repository for managing episode metadata from episodes.json.
    """
    
    def __init__(self, episodes_json_path: Path):
        """
        Initialize the repository.
        
        Args:
            episodes_json_path: Path to episodes.json file
        """
        self.episodes_json_path = episodes_json_path
        self.episodes: Dict[str, Dict[str, Any]] = {}
        self._load_episodes()
    
    def _load_episodes(self):
        """Load episodes from JSON file."""
        try:
            with open(self.episodes_json_path, 'r') as f:
                episodes_data = json.load(f)
                # Index episodes by video_id for quick lookup
                # Episodes are in an array under the "episodes" key
                for episode in episodes_data.get('episodes', []):
                    self.episodes[episode['video_id']] = episode
        except Exception as e:
            print(f"Warning: Could not load episodes.json: {e}")
    
    def get_episode_metadata(self, video_id: str) -> Optional[Dict[str, Any]]:
        """
        Get metadata for a specific episode.
        
        Args:
            video_id: YouTube video ID
            
        Returns:
            Episode metadata dictionary or None if not found
        """
        return self.episodes.get(video_id)

@dataclass
class TranscriptChunk:
    """
    Represents a chunk of transcript ready for embedding.
    Includes all necessary context and metadata for effective retrieval.
    """
    # Core content
    text: str                    # The actual text content to be embedded
    
    # Temporal context
    start_time: float           # Start time in seconds
    end_time: float            # End time in seconds
    
    # Speaker information
    speaker_id: int            # Speaker identifier
    speaker_confidence: float  # Confidence in speaker identification
    
    # Episode context
    video_id: str             # YouTube video ID
    episode_title: str        # Episode title
    published_at: datetime    # Publication date
    episode_metadata: Dict[str, Any]  # Full episode metadata
    
    # Chunk context
    chunk_index: int          # Position of chunk in episode
    previous_chunk_text: str  # Brief context from previous chunk
    next_chunk_text: str      # Brief context from next chunk
    
    # Quality metrics
    confidence_score: float   # Transcription confidence
    
    def to_embedding_dict(self) -> Dict[str, Any]:
        """
        Convert the chunk to a dictionary format suitable for embedding storage.
        Includes all metadata needed for effective retrieval and reranking.
        """
        # Extract episode-specific metadata
        episode_type = self.episode_metadata.get('metadata', {}).get('type', 'UNKNOWN')
        episode_duration = self.episode_metadata.get('metadata', {}).get('duration_seconds')
        episode_description = self.episode_metadata.get('description', '')
        episode_tags = self.episode_metadata.get('tags', [])
        view_count = self.episode_metadata.get('view_count')
        like_count = self.episode_metadata.get('like_count')
        comment_count = self.episode_metadata.get('comment_count')
        
        return {
            # Primary content for embedding
            "content": self.text,
            
            # Time context (for video jumping)
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": round(self.end_time - self.start_time, 2),
            
            # Speaker context
            "speaker_id": self.speaker_id,
            "speaker_confidence": round(self.speaker_confidence, 3),
            
            # Episode metadata
            "video_id": self.video_id,
            "episode_title": self.episode_title,
            "published_at": self.published_at.isoformat(),
            "episode_type": episode_type,
            "episode_duration": episode_duration,
            "episode_description": episode_description,
            
            # Rich episode metadata
            "tags": episode_tags,
            
            # Statistics
            "statistics": {
                "view_count": view_count,
                "like_count": like_count,
                "comment_count": comment_count
            },
            
            # Chunk context
            "chunk_index": self.chunk_index,
            "context": {
                "previous": self.previous_chunk_text,
                "next": self.next_chunk_text
            },
            
            # Quality indicators
            "confidence_score": round(self.confidence_score, 3),
            
            # Unique identifier for the chunk
            "chunk_id": f"{self.video_id}_{self.chunk_index}",
            
            # Timestamp for the chunk (useful for time-based queries)
            "timestamp": self.start_time,
            
            # Additional metadata for filtering
            "metadata": {
                "year": self.published_at.year,
                "month": self.published_at.month,
                "day": self.published_at.day,
                "duration_seconds": round(self.end_time - self.start_time, 2),
                "confidence_tier": "high" if self.confidence_score > 0.9 else "medium" if self.confidence_score > 0.7 else "low",
                "episode_type": episode_type,
                "has_tags": len(episode_tags) > 0,
                "engagement_metrics": {
                    "views": view_count,
                    "likes": like_count,
                    "comments": comment_count
                }
            }
        }

class TranscriptChunker:
    """
    Handles the chunking of transcripts into embedding-ready segments.
    Implements various chunking strategies and metadata enrichment.
    """
    
    def __init__(self, 
                 episode_repository: EpisodeMetadataRepository,
                 max_chunk_size: int = 512,
                 min_chunk_size: int = 100,
                 overlap_size: int = 50):
        """
        Initialize the chunker with configuration parameters.
        
        Args:
            episode_repository: Repository for episode metadata
            max_chunk_size: Maximum number of characters in a chunk
            min_chunk_size: Minimum number of characters in a chunk
            overlap_size: Number of characters to overlap between chunks
        """
        self.episode_repository = episode_repository
        self.max_chunk_size = max_chunk_size
        self.min_chunk_size = min_chunk_size
        self.overlap_size = overlap_size
    
    def process_transcript(self, transcript_path: Path) -> List[TranscriptChunk]:
        """
        Process a transcript file into chunks ready for embedding.
        
        Args:
            transcript_path: Path to the transcript JSON file
            
        Returns:
            List of TranscriptChunk objects ready for embedding
        """
        # Load the transcript
        with open(transcript_path, 'r') as f:
            transcript = json.load(f)
        
        # Extract episode metadata
        episode_meta = transcript['episode_metadata']
        
        # Get full episode metadata from repository
        full_episode_metadata = self.episode_repository.get_episode_metadata(episode_meta['video_id']) or {}
        
        # Process utterances into chunks
        chunks = []
        current_chunk = []
        current_length = 0
        
        # Get all utterances
        utterances = transcript['results']['utterances']
        
        for i, utterance in enumerate(utterances):
            # Get context from adjacent utterances
            prev_text = utterances[i-1]['transcript'] if i > 0 else ""
            next_text = utterances[i+1]['transcript'] if i < len(utterances)-1 else ""
            
            # Create chunk
            chunk = TranscriptChunk(
                text=utterance['transcript'],
                start_time=utterance['start'],
                end_time=utterance['end'],
                speaker_id=utterance['speaker'],
                speaker_confidence=utterance.get('speaker_confidence', 0.0),
                video_id=episode_meta['video_id'],
                episode_title=episode_meta['title'],
                published_at=datetime.fromisoformat(episode_meta['published_at'].replace('Z', '+00:00')),
                episode_metadata=full_episode_metadata,
                chunk_index=i,
                previous_chunk_text=self._get_context_snippet(prev_text),
                next_chunk_text=self._get_context_snippet(next_text),
                confidence_score=utterance['confidence']
            )
            
            chunks.append(chunk)
        
        return chunks
    
    def _get_context_snippet(self, text: str, max_length: int = 100) -> str:
        """Get a shortened context snippet."""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    def merge_short_chunks(self, chunks: List[TranscriptChunk]) -> List[TranscriptChunk]:
        """
        Merge chunks that are too short while preserving speaker boundaries.
        
        Args:
            chunks: List of transcript chunks
            
        Returns:
            List of merged chunks
        """
        merged = []
        temp_chunk = None
        
        for chunk in chunks:
            if temp_chunk is None:
                temp_chunk = chunk
                continue
            
            # If same speaker and combined length is under max, merge
            if (temp_chunk.speaker_id == chunk.speaker_id and 
                len(temp_chunk.text) + len(chunk.text) <= self.max_chunk_size):
                # Merge chunks
                temp_chunk.text += " " + chunk.text
                temp_chunk.end_time = chunk.end_time
                temp_chunk.confidence_score = (temp_chunk.confidence_score + chunk.confidence_score) / 2
                temp_chunk.next_chunk_text = chunk.next_chunk_text
            else:
                # Add completed chunk and start new one
                merged.append(temp_chunk)
                temp_chunk = chunk
        
        # Add last chunk
        if temp_chunk:
            merged.append(temp_chunk)
        
        return merged

def prepare_transcript_embeddings(
    transcripts_dir: Path,
    episodes_json_path: Path,
    output_dir: Path
) -> None:
    """
    Process all transcripts in a directory and prepare them for embedding.
    
    Args:
        transcripts_dir: Directory containing transcript JSON files
        episodes_json_path: Path to episodes.json file
        output_dir: Directory to save processed chunks
    """
    # Create output directory if it doesn't exist
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize episode repository and chunker
    episode_repository = EpisodeMetadataRepository(episodes_json_path)
    chunker = TranscriptChunker(episode_repository)
    
    # Process each transcript file
    for transcript_file in transcripts_dir.glob('*.json'):
        try:
            print(f"Processing {transcript_file.name}...")
            
            # Process transcript into chunks
            chunks = chunker.process_transcript(transcript_file)
            
            # Convert chunks to embedding format
            embedding_data = [chunk.to_embedding_dict() for chunk in chunks]
            
            # Save to output file
            output_file = output_dir / f"{transcript_file.stem}_chunks.json"
            with open(output_file, 'w') as f:
                json.dump(embedding_data, f, indent=2)
                
            print(f"Saved {len(chunks)} chunks to {output_file}")
            
        except Exception as e:
            print(f"Error processing {transcript_file.name}: {e}")

if __name__ == "__main__":
    # Set up paths
    base_dir = Path.cwd()
    transcripts_dir = base_dir / "data" / "transcripts"
    episodes_json_path = base_dir / "data" / "json" / "episodes.json"
    output_dir = base_dir / "data" / "embedding_chunks"
    
    # Run the processing
    prepare_transcript_embeddings(transcripts_dir, episodes_json_path, output_dir) 