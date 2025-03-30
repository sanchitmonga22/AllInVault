# AllInVault Architecture

## System Overview

AllInVault is a podcast analysis platform designed to retrieve, process, and transcribe podcast episodes. The system is modular and follows SOLID principles to ensure maintainability, scalability, and extensibility.

## Core Components

```
┌───────────────────┐     ┌─────────────────┐     ┌───────────────────┐
│                   │     │                 │     │                   │
│  Episode Retrieval│─────▶ Audio Processing│─────▶    Transcription  │
│                   │     │                 │     │                   │
└───────────────────┘     └─────────────────┘     └───────────────────┘
          │                       │                        │
          │                       │                        │
          ▼                       ▼                        ▼
┌───────────────────┐     ┌─────────────────┐     ┌───────────────────┐
│                   │     │                 │     │                   │
│  Metadata Storage │     │  Audio Storage  │     │ Transcript Storage│
│                   │     │                 │     │                   │
└───────────────────┘     └─────────────────┘     └───────────────────┘
```

## Project Structure

```
AllInVault/
├── data/                       # Data storage
│   ├── audio/                  # Downloaded audio files
│   ├── json/                   # Metadata storage
│   └── transcripts/            # Transcript storage
├── src/                        # Source code
│   ├── cli/                    # Command-line interfaces
│   │   ├── analyze_episodes_cmd.py  # CLI for episode analysis
│   │   ├── display_transcript_cmd.py # CLI for transcript display
│   │   ├── download_podcast_cmd.py  # CLI for podcast download
│   │   ├── process_podcast_cmd.py   # CLI for full pipeline
│   │   ├── transcribe_audio_cmd.py  # CLI for audio transcription
│   │   └── transcribe_full_episodes_cmd.py # CLI for batch transcription
│   ├── models/                 # Data models
│   │   └── podcast_episode.py  # Podcast episode model
│   ├── repositories/           # Data access layer
│   │   └── episode_repository.py # Episode repository
│   ├── services/               # Business logic
│   │   ├── youtube_service.py  # YouTube API service
│   │   ├── downloader_service.py # Audio downloader service
│   │   ├── transcription_service.py # Transcription service
│   │   ├── episode_analyzer.py # Episode analysis service
│   │   ├── batch_transcriber.py # Batch transcription service
│   │   └── podcast_pipeline.py # Full pipeline orchestration
│   └── utils/                  # Utilities
│       └── config.py           # Configuration utilities
├── analyze_episodes.py         # Entry point for episode analysis
├── display_transcript.py       # Entry point for transcript display
├── download_podcast.py         # Entry point for podcast download
├── process_podcast.py          # Entry point for full pipeline
├── transcribe_audio.py         # Entry point for audio transcription
└── transcribe_full_episodes.py # Entry point for batch transcription
```

## Service Layer

### 1. Episode Retrieval Services

**Key Components:**
- `YouTubeService`: Fetches podcast episodes from YouTube
  - Retrieves metadata via the YouTube API
  - Supports filtering by channel

### 2. Audio Processing Services

**Key Components:**
- `DownloaderService`: Downloads audio content
  - Handles YouTube download integration
  - Manages audio file storage

### 3. Episode Analysis Service

**Key Components:**
- `EpisodeAnalyzerService`: Analyzes episodes based on metadata
  - Duration-based filtering to separate full episodes from shorts
  - Detailed episode information and statistics
  - Used by other services for episode filtering

### 4. Transcription Services

**Key Components:**
- `TranscriptionService`: Core transcription functionality
  - Speaker diarization to identify different speakers
  - Timestamp generation for utterances
  - Support for demo mode without actual audio processing
- `BatchTranscriberService`: Manages transcription of multiple episodes
  - Integrates with episode analysis for filtering shorts
  - Processes only applicable episodes
  - Generates both JSON and human-readable transcripts

### 5. Orchestration Service

**Key Components:**
- `PodcastPipelineService`: Orchestrates the entire workflow
  - Coordinates all other services in sequence
  - Manages the complete pipeline from download to transcription
  - Provides unified interface for the entire process

### 6. Repository Layer

**Key Components:**
- `EpisodeRepository`: Data access for episodes
  - JSON-based storage
  - CRUD operations for episode data
  - Search and filtering capabilities

## Command-Line Interface

The system includes multiple command-line interfaces:

1. **Individual Tools**:
   - `analyze_episodes.py`: Analyze and categorize episodes
   - `download_podcast.py`: Download episode metadata and audio
   - `transcribe_audio.py`: Transcribe audio files
   - `transcribe_full_episodes.py`: Batch transcribe full episodes
   - `display_transcript.py`: View formatted transcripts

2. **Unified Pipeline**:
   - `process_podcast.py`: Execute the complete pipeline in one command
     - Download episode metadata
     - Analyze and filter episodes
     - Download audio for full episodes only
     - Generate transcripts
     - All steps are configurable via command-line arguments

## Data Flow

1. Episode data is retrieved from the podcast source via `YouTubeService`
2. Episodes are analyzed and categorized via `EpisodeAnalyzerService`
   - Each episode is marked as FULL or SHORT in the repository
3. Audio is downloaded for full episodes via `DownloaderService`
4. Audio is processed through `TranscriptionService`
5. Batch processing is handled by `BatchTranscriberService`
6. The entire workflow is orchestrated by `PodcastPipelineService`
7. All operations update the repository via `EpisodeRepository`

## SOLID Principles Implementation

1. **Single Responsibility Principle**: Each service class has a single, well-defined responsibility
2. **Open/Closed Principle**: Services are designed to be extended without modification
3. **Liskov Substitution Principle**: Service interfaces allow for interchangeable implementations
4. **Interface Segregation Principle**: Service interfaces are focused and specific
5. **Dependency Inversion Principle**: High-level modules depend on abstractions, not details

## Features

- **YouTube Shorts Detection**: Automatically identifies short-form content
- **Speaker Diarization**: Detects and labels different speakers
- **Guest Speaker Recognition**: Identifies and labels guest speakers
- **Custom Episode Support**: Allows creation of custom episodes for testing
- **Demo Mode**: Enables testing without actual audio processing
- **Batch Processing**: Efficient processing of multiple episodes
- **Unified Pipeline**: Complete workflow automation from a single command

## Future Enhancements

- Integration with real-time transcription services
- Advanced speaker identification using voice characteristics
- Natural language processing for content analysis
- User interface for easy interaction with the system 