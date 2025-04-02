import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv


@dataclass
class AppConfig:
    """Application configuration."""
    # YouTube API
    youtube_api_key: str
    
    # Channel IDs
    all_in_channel_id: str
    
    # Paths
    data_dir: Path
    audio_dir: Path
    webm_dir: Path  # Directory for storing webm files before conversion
    json_dir: Path
    transcripts_dir: Path
    
    # Download settings
    audio_format: str = "mp3"
    audio_quality: str = "192"
    conversion_threads: int = 4  # Number of parallel threads for conversion
    
    # Database settings
    episodes_db_path: Path = None
    
    # Transcription settings
    deepgram_api_key: Optional[str] = None
    deepgram_language: str = "en-US"
    deepgram_model: str = "nova"
    
    def __post_init__(self):
        """Post initialization setup."""
        if self.episodes_db_path is None:
            self.episodes_db_path = self.json_dir / "episodes.json"


def load_config() -> AppConfig:
    """Load application configuration from environment variables."""
    # Load environment variables from .env file
    load_dotenv()
    
    # Get required environment variables or use default values
    youtube_api_key = os.getenv("YOUTUBE_API_KEY")
    if not youtube_api_key:
        raise ValueError("YOUTUBE_API_KEY environment variable is required")
    
    all_in_channel_id = os.getenv("ALL_IN_CHANNEL_ID", "UCESLZhusAkFfsNsApnjF_Cg")
    
    # Set up directories
    data_dir = Path(os.getenv("DATA_DIR", "data"))
    audio_dir = Path(os.getenv("AUDIO_DIR", data_dir / "audio"))
    webm_dir = Path(os.getenv("WEBM_DIR", data_dir / "webm"))  # New webm directory
    json_dir = Path(os.getenv("JSON_DIR", data_dir / "json"))
    transcripts_dir = Path(os.getenv("TRANSCRIPTS_DIR", data_dir / "transcripts"))
    
    # Create directories if they don't exist
    audio_dir.mkdir(parents=True, exist_ok=True)
    webm_dir.mkdir(parents=True, exist_ok=True)  # Create webm directory
    json_dir.mkdir(parents=True, exist_ok=True)
    transcripts_dir.mkdir(parents=True, exist_ok=True)
    
    # Download settings
    audio_format = os.getenv("AUDIO_FORMAT", "mp3")
    audio_quality = os.getenv("AUDIO_QUALITY", "192")
    conversion_threads = int(os.getenv("CONVERSION_THREADS", "4"))
    
    # Transcription settings
    deepgram_api_key = os.getenv("DEEPGRAM_API_KEY")
    deepgram_language = os.getenv("DEEPGRAM_LANGUAGE", "en-US")
    deepgram_model = os.getenv("DEEPGRAM_MODEL", "nova")
    
    return AppConfig(
        youtube_api_key=youtube_api_key,
        all_in_channel_id=all_in_channel_id,
        data_dir=data_dir,
        audio_dir=audio_dir,
        webm_dir=webm_dir,
        json_dir=json_dir,
        transcripts_dir=transcripts_dir,
        audio_format=audio_format,
        audio_quality=audio_quality,
        conversion_threads=conversion_threads,
        deepgram_api_key=deepgram_api_key,
        deepgram_language=deepgram_language,
        deepgram_model=deepgram_model
    ) 