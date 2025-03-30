# All In Vault - Podcast Analysis Platform

All In Vault is a comprehensive platform for downloading, transcribing, and analyzing the All In podcast episodes. The system retrieves metadata from YouTube, downloads audio files, performs transcription using Deepgram's Nova-3 model, and provides tools for analyzing the content.

## Core Features

- **YouTube Integration**: Retrieves podcast episodes and metadata from YouTube
- **Audio Processing**: Downloads high-quality audio for transcription
- **Advanced Transcription**: Uses Deepgram's Nova-3 model with speaker diarization
- **Metadata Management**: Stores and organizes all podcast metadata
- **Pipeline Automation**: Complete workflow from retrieval to transcription
- **Episode Analysis**: Distinguishes between full episodes and shorts
- **Speaker Identification**: Uses heuristics and optional LLM integration to identify speakers

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/allinvault.git
   cd allinvault
   ```

2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

3. Configure environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

## API Keys Required

- **YouTube API Key**: Required for fetching episode metadata
- **Deepgram API Key**: Required for audio transcription
- **OpenAI API Key**: Optional, used for LLM-based speaker identification
- **DeepSeek API Key**: Optional alternative for LLM-based speaker identification

## Usage

### Complete Pipeline

Run the entire pipeline with a single command:

```bash
python process_podcast.py --num-episodes 5
```

This will:
1. Fetch the latest 5 episodes from YouTube
2. Analyze and identify full episodes
3. Download audio for full episodes
4. Transcribe the audio using Deepgram
5. Optionally identify speakers using heuristics or LLM

### Individual Steps

#### 1. Download Episode Metadata

```bash
python download_podcast.py --info-only
```

Options:
- `--limit`: Number of episodes to fetch (default: 10)
- `--info-only`: Only fetch metadata, don't download audio
- `--format`: Audio format (default: mp3)
- `--quality`: Audio quality in kbps (default: 192)

#### 2. Analyze Episodes

```bash
python analyze_episodes.py
```

Options:
- `--limit`: Number of episodes to analyze (default: all)
- `--min-duration`: Minimum duration in seconds for a full episode (default: 180)

#### 3. Download Audio

```bash
python download_podcast.py
```

Options:
- `--limit`: Number of episodes to download (default: 10)
- `--format`: Audio format (default: mp3)
- `--quality`: Audio quality in kbps (default: 192)

#### 4. Transcribe Audio

```bash
python transcribe_audio.py
```

Options:
- `--episode`: Process a specific episode by video ID
- `--model`: Deepgram model to use (default: nova-3)
- `--detect-language`: Auto-detect language (default: false)
- `--smart-format`: Apply smart formatting to transcripts (default: true)
- `--utterances`: Generate utterance-level transcripts (default: true)
- `--diarize`: Perform speaker diarization (default: true)

#### 5. Transcribe Full Episodes (Batch Operation)

```bash
python transcribe_full_episodes.py
```

Options:
- `--limit`: Number of episodes to transcribe (default: all full episodes)

#### 6. Display Transcripts

```bash
python display_transcript.py --episode VIDEO_ID
```

Options:
- `--episode`: Video ID of the episode to display
- `--format`: Display format (default: text)
- `--show-speakers`: Show speaker information (default: true)
- `--show-timestamps`: Show timestamps (default: false)

#### 7. Verify and Update Metadata

```bash
python verify_transcripts.py
```

Options:
- `--stats-only`: View only statistics without updating
- `--episodes`: Path to episodes JSON file
- `--transcripts`: Path to transcripts directory

#### 8. Identify Speakers

```bash
python identify_speakers.py
```

Options:
- `--episode`: Process a specific episode by video ID
- `--no-llm`: Disable LLM for speaker identification (not recommended)
- `--llm-provider`: LLM provider to use (default: openai, options: openai, deepseq)
- `--force-reidentify`: Re-identify speakers even if already identified

## Services and Modules

### Core Services

1. **YouTube Service** (`src/services/youtube_service.py`)
   - Fetches podcast episode metadata from YouTube API
   - Handles API pagination for retrieving multiple episodes
   - Converts YouTube API responses to internal data models

2. **Downloader Service** (`src/services/downloader_service.py`)
   - Downloads audio files using yt-dlp
   - Manages audio format and quality settings
   - Handles file naming and storage conventions

3. **Episode Analyzer Service** (`src/services/episode_analyzer.py`)
   - Categorizes episodes as full episodes or shorts based on duration
   - Parses ISO 8601 durations from YouTube metadata
   - Updates episode metadata with duration information

4. **Transcription Service** (`src/services/transcription_service.py`)
   - Handles audio transcription using Deepgram API
   - Manages speaker diarization and transcript formatting
   - Processes transcripts and updates episode metadata

5. **Batch Transcriber Service** (`src/services/batch_transcriber.py`)
   - Coordinates transcription of multiple episodes
   - Handles parallel processing of transcription tasks
   - Manages transcript storage and organization

6. **Podcast Pipeline Service** (`src/services/podcast_pipeline.py`)
   - Orchestrates the entire workflow from download to transcription
   - Coordinates all other services in sequence
   - Provides unified interface for the complete process

7. **Speaker Identification Service** (`src/services/speaker_identification_service.py`)
   - Identifies speakers in transcripts using LLM integration
   - Maps anonymous speaker tags to actual speaker names
   - Optionally works with multiple LLM providers for improved accuracy

8. **LLM Service** (`src/services/llm_service.py`)
   - Provides LLM integration for enhanced speaker identification
   - Supports multiple LLM providers (OpenAI, DeepSeek)
   - Extracts speaker information from transcript context

### Data Layer

1. **Episode Repository** (`src/repositories/episode_repository.py`)
   - Manages storage and retrieval of episode metadata
   - Provides CRUD operations for episode data
   - Ensures data consistency across pipeline stages

2. **Podcast Episode Model** (`src/models/podcast_episode.py`)
   - Data model representing a podcast episode
   - Contains fields for both YouTube metadata and transcript information
   - Implements serialization/deserialization logic

### Utilities

1. **Configuration Utilities** (`src/utils/config.py`)
   - Loads environment variables and configuration settings
   - Provides application-wide configuration access
   - Manages default values and path resolution

## Command-Line Interfaces

Each CLI module provides a user-friendly interface to interact with the corresponding service:

1. **Process Podcast CLI** (`src/cli/process_podcast_cmd.py`)
   - Runs the complete pipeline from metadata fetch to transcription
   - Command: `python process_podcast.py`

2. **Download Podcast CLI** (`src/cli/download_podcast_cmd.py`)
   - Handles downloading episode metadata and audio files
   - Command: `python download_podcast.py`

3. **Analyze Episodes CLI** (`src/cli/analyze_episodes_cmd.py`)
   - Analyzes episodes to identify full episodes vs shorts
   - Command: `python analyze_episodes.py`

4. **Transcribe Audio CLI** (`src/cli/transcribe_audio_cmd.py`)
   - Manages audio transcription with various options
   - Command: `python transcribe_audio.py`

5. **Transcribe Full Episodes CLI** (`src/cli/transcribe_full_episodes_cmd.py`)
   - Batch transcribes all full episodes
   - Command: `python transcribe_full_episodes.py`

6. **Display Transcript CLI** (`src/cli/display_transcript_cmd.py`)
   - Displays transcripts in various formats
   - Command: `python display_transcript.py`

7. **Verify Transcripts CLI** (`src/cli/verify_transcripts.py`)
   - Verifies transcript metadata and integrity
   - Command: `python verify_transcripts.py`

8. **Identify Speakers CLI** (`src/cli/identify_speakers_cmd.py`)
   - Identifies speakers in transcripts
   - Command: `python identify_speakers.py`

## Project Structure

```
allinvault/
├── data/                      # Data storage
│   ├── audio/                 # Downloaded audio files
│   ├── json/                  # Metadata storage
│   └── transcripts/           # Transcript storage
├── src/                       # Source code
│   ├── cli/                   # Command-line interfaces
│   ├── models/                # Data models
│   ├── repositories/          # Data access layer
│   ├── services/              # Business logic
│   └── utils/                 # Utilities
├── *.py                       # Entry point scripts
├── .env                       # Environment variables (create from .env.example)
├── .env.example               # Example environment variables
├── requirements.txt           # Python dependencies
└── architecture.md            # Detailed architecture documentation
```

## Architecture

The project follows a modular, service-oriented architecture adhering to SOLID principles. See `architecture.md` for detailed documentation.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 