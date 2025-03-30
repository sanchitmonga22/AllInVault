# All In Vault - Podcast Analysis Platform

All In Vault is a comprehensive platform for downloading, transcribing, and analyzing the All In podcast episodes. The system retrieves metadata from YouTube, downloads audio files, performs transcription using Deepgram's Nova-3 model, and provides tools for analyzing the content.

## Core Features

- **YouTube Integration**: Retrieves podcast episodes and metadata from YouTube
- **Audio Processing**: Downloads high-quality audio for transcription
- **Advanced Transcription**: Uses Deepgram's Nova-3 model with speaker diarization
- **Metadata Management**: Stores and organizes all podcast metadata
- **Pipeline Automation**: Complete workflow from retrieval to transcription
- **Episode Analysis**: Distinguishes between full episodes and shorts

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

## API Keys

- **YouTube API Key**: Required for fetching episode metadata
- **Deepgram API Key**: Required for audio transcription

## Usage

### Complete Pipeline

Run the entire pipeline with a single command:

```bash
python process_podcast.py --limit 5
```

This will:
1. Fetch the latest 5 episodes from YouTube
2. Analyze and identify full episodes
3. Download audio for full episodes
4. Transcribe the audio using Deepgram

### Individual Steps

#### 1. Download Episode Metadata

```bash
python download_podcast.py --info-only
```

#### 2. Analyze Episodes

```bash
python analyze_episodes.py
```

#### 3. Download Audio

```bash
python download_podcast.py
```

#### 4. Transcribe Audio

```bash
python transcribe_audio.py
```

#### 5. Display Transcripts

```bash
python display_transcript.py --episode VIDEO_ID
```

#### 6. Verify and Update Metadata

The system includes a verification tool to ensure YouTube metadata and transcript information are properly integrated:

```bash
# Verify and update all episodes
python verify_transcripts.py

# View only statistics without updating
python verify_transcripts.py --stats-only

# Specify custom paths
python verify_transcripts.py --episodes path/to/episodes.json --transcripts path/to/transcripts
```

This script:
- Updates transcript metadata for better integration with YouTube data
- Calculates coverage percentages for transcripts
- Adds missing duration information
- Generates statistics about your transcription progress

## Command-Line Options

Each script supports various options:

- `--limit`: Number of episodes to process
- `--info-only`: Only fetch metadata (for download_podcast.py)
- `--episode`: Process a specific episode by video ID
- `--format`: Audio format (mp3, m4a, etc.)
- `--quality`: Audio quality in kbps

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
└── *.py                       # Entry point scripts
```

## Architecture

The project follows a modular, service-oriented architecture adhering to SOLID principles. See `architecture.md` for detailed documentation.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 