from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class PodcastEpisode:
    """Data model for a podcast episode."""
    video_id: str
    title: str
    description: str
    published_at: datetime
    channel_id: str
    channel_title: str
    tags: List[str] = field(default_factory=list)
    duration: Optional[str] = None
    view_count: Optional[int] = None
    like_count: Optional[int] = None
    comment_count: Optional[int] = None
    thumbnail_url: Optional[str] = None
    audio_filename: Optional[str] = None
    transcript_filename: Optional[str] = None
    transcript_duration: Optional[float] = None
    transcript_utterances: Optional[int] = None
    speaker_count: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert the episode to a dictionary for serialization."""
        return {
            "video_id": self.video_id,
            "title": self.title,
            "description": self.description,
            "published_at": self.published_at.isoformat(),
            "channel_id": self.channel_id,
            "channel_title": self.channel_title,
            "tags": self.tags,
            "duration": self.duration,
            "view_count": self.view_count,
            "like_count": self.like_count,
            "comment_count": self.comment_count,
            "thumbnail_url": self.thumbnail_url,
            "audio_filename": self.audio_filename,
            "transcript_filename": self.transcript_filename,
            "transcript_duration": self.transcript_duration,
            "transcript_utterances": self.transcript_utterances,
            "speaker_count": self.speaker_count
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'PodcastEpisode':
        """Create an episode from a dictionary."""
        if isinstance(data["published_at"], str):
            data["published_at"] = datetime.fromisoformat(data["published_at"])
        return cls(**data) 