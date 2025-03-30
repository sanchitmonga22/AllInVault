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

## Flexible Pipeline Architecture

AllInVault features a flexible, stage-based pipeline architecture that provides granular control over the podcast processing workflow:

- **Modular Stages**: Each processing step is encapsulated in a separate stage
- **Flexible Execution**: Run the entire pipeline or specific stages
- **Episode Targeting**: Process all episodes or target specific episodes by ID
- **Stage Dependencies**: Automatic handling of stage dependencies
- **Configurable Parameters**: Each stage accepts specific configuration options
- **Consistent Interface**: Unified command-line interface for all operations

The pipeline consists of these sequential stages:

1. **Fetch Metadata**: Retrieve episode information from YouTube API
2. **Analyze Episodes**: Identify full episodes vs shorts based on duration
3. **Download Audio**: Download audio files for episodes
4. **Transcribe Audio**: Generate transcriptions using Deepgram
5. **Identify Speakers**: Map speakers in transcripts to actual names

See [architecture.md](architecture.md) for detailed documentation of the system design.

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

### Unified Command Interface

AllInVault provides a single, unified command-line interface for all operations through the `pipeline.py` script:

```bash
python pipeline.py [command] [options]
```

Available commands:
- `pipeline` (default): Execute the pipeline or specific stages
- `display`: Display a transcript
- `verify`: Verify transcript metadata and display statistics

### Pipeline Command

The `pipeline` command (default) processes podcast episodes through the flexible stage-based architecture:

```bash
python pipeline.py [pipeline] [options]
```

#### Basic Pipeline Operations

```bash
# Process the latest 5 episodes through the complete pipeline
python pipeline.py

# Explicitly use the pipeline command (same as above)
python pipeline.py pipeline

# Process a specific number of episodes
python pipeline.py pipeline --num-episodes 10

# Process specific episodes by video ID
python pipeline.py pipeline --episodes "Wr12BFko-Xo,8UzQ5uf_vik"
```

#### Stage Selection Options

```bash
# Run only specific stages (comma-separated)
python pipeline.py pipeline --stages fetch_metadata,download_audio

# Run from a specific stage to the end
python pipeline.py pipeline --start-stage download_audio

# Run a range of stages
python pipeline.py pipeline --start-stage download_audio --end-stage transcribe_audio

# Skip automatic dependency resolution
python pipeline.py pipeline --stages transcribe_audio --skip-dependencies
```

Available stages:
- `fetch_metadata`: Retrieve episode information from YouTube API
- `analyze_episodes`: Identify full episodes vs shorts based on duration
- `download_audio`: Download audio files for episodes
- `transcribe_audio`: Generate transcriptions using Deepgram
- `identify_speakers`: Map speakers in transcripts to actual names

#### Fetch Metadata Options

```bash
# Limit the number of episodes to fetch
python pipeline.py pipeline --stages fetch_metadata --limit 20
```

Flags:
- `--limit`: Maximum number of episodes to fetch metadata for

#### Episode Analysis Options

```bash
# Set custom duration threshold for full episodes
python pipeline.py pipeline --stages analyze_episodes --min-duration 300
```

Flags:
- `--min-duration`: Minimum duration in seconds for an episode to be considered full (default: 180)

#### Download Audio Options

```bash
# Download in different format and quality
python pipeline.py pipeline --stages download_audio --audio-format m4a --audio-quality 256

# Download all episodes, not just full episodes
python pipeline.py pipeline --stages download_audio --all-episodes

# Specify custom audio directory
python pipeline.py pipeline --stages download_audio --audio-dir "/path/to/audio/files"
```

Flags:
- `--audio-format`: Audio format to download (e.g., mp3, m4a)
- `--audio-quality`: Audio quality in kbps (e.g., 192, 256)
- `--all-episodes`: Include all episodes for audio download, not just full episodes
- `--audio-dir`: Directory for storing downloaded audio files

#### Transcription Options

```bash
# Customize transcription settings
python pipeline.py pipeline --stages transcribe_audio --model nova-3 --no-diarize --detect-language

# Specify custom directories
python pipeline.py pipeline --stages transcribe_audio --audio-dir "/path/to/audio" --transcripts-dir "/path/to/transcripts"
```

Flags:
- `--model`: Deepgram model to use for transcription (default: nova-3)
- `--no-diarize`: Disable speaker diarization during transcription
- `--no-smart-format`: Disable smart formatting in transcripts
- `--detect-language`: Enable language detection during transcription
- `--audio-dir`: Directory containing audio files to transcribe
- `--transcripts-dir`: Directory for storing transcriptions

#### Speaker Identification Options

```bash
# Configure speaker identification
python pipeline.py pipeline --stages identify_speakers --llm-provider openai --force-reidentify

# Disable LLM for speaker identification, use heuristics only
python pipeline.py pipeline --stages identify_speakers --no-llm
```

Flags:
- `--no-llm`: Disable LLM for speaker identification and use heuristics only
- `--llm-provider`: LLM provider to use for speaker identification (options: openai, deepseq)
- `--force-reidentify`: Force re-identification of speakers even if already identified
- `--transcripts-dir`: Directory containing transcripts to process

### Display Command

The `display` command shows transcript content with various formatting options:

```bash
python pipeline.py display [options]
```

#### Basic Display Operations

```bash
# Display transcript in text format
python pipeline.py display --episode VIDEO_ID

# Display transcript in JSON format
python pipeline.py display --episode VIDEO_ID --format json

# Hide speaker information
python pipeline.py display --episode VIDEO_ID --no-speakers

# Show timestamps
python pipeline.py display --episode VIDEO_ID --show-timestamps
```

Flags:
- `--episode`: Video ID of the episode to display (required)
- `--format`: Display format (options: text, json)
- `--no-speakers`: Hide speaker information
- `--show-timestamps`: Show timestamps

### Verify Command

The `verify` command checks transcript metadata and displays statistics:

```bash
python pipeline.py verify [options]
```

#### Basic Verification Operations

```bash
# Verify all transcripts and display statistics
python pipeline.py verify

# Show only high-level statistics
python pipeline.py verify --stats-only

# Verify without updating metadata files
python pipeline.py verify --no-update
```

Flags:
- `--stats-only`: Only display statistics without details of missing items
- `--no-update`: Don't update episode metadata files when inconsistencies are found

### Complete Command Reference

For a complete list of all available options:

```bash
# Show main help
python pipeline.py --help

# Show help for a specific command
python pipeline.py pipeline --help
python pipeline.py display --help
python pipeline.py verify --help
```

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