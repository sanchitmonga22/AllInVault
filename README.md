# All In Vault - Podcast Downloader and Transcriber

This tool downloads the All In podcast episodes as audio files, transcribes them using Deepgram API, and stores their metadata in a local JSON database. It's part of the All In Vault project, which aims to create a searchable knowledge base of podcast content.

## Features

- Downloads audio for All In podcast episodes
- Transcribes audio files into detailed text transcripts with timestamps
- Extracts comprehensive metadata for each episode
- Stores metadata in a JSON database
- Configurable audio quality and format
- Command-line interface with various options

## Prerequisites

- Python 3.8+
- YouTube API Key
- Deepgram API Key (for transcription)
- FFmpeg (for audio extraction)

## Installation

1. Clone this repository:
   ```bash
   git clone https://github.com/yourusername/allinvault.git
   cd allinvault
   ```

2. Install required packages:
   ```bash
   pip install -r requirements.txt
   ```

3. Copy the example environment file and edit it:
   ```bash
   cp .env.example .env
   # Edit .env to add your YouTube API key and Deepgram API key
   ```

## Quick Start Guide

### Step 1: Set Up Your API Keys

1. Get a YouTube API key from the [Google Cloud Console](https://console.cloud.google.com/).
2. Get a Deepgram API key from the [Deepgram Console](https://console.deepgram.com/).
3. Add them to your `.env` file:
   ```
   YOUTUBE_API_KEY=your_youtube_api_key_here
   DEEPGRAM_API_KEY=your_deepgram_api_key_here
   ```

### Step 2: Download Metadata

To download metadata for all episodes:

```bash
python download_podcast.py --info-only
```

This will fetch metadata for all episodes and store it in `data/json/episodes.json`.

To limit the number of episodes:

```bash
python download_podcast.py --info-only --limit 10
```

### Step 3: Download Audio Files

To download both metadata and audio files:

```bash
python download_podcast.py
```

Or with a limit:

```bash
python download_podcast.py --limit 5
```

**Note**: Due to YouTube's restrictions on programmatic downloading, the current implementation creates placeholder files instead of actual audio content. In a production environment, you would need an alternative approach to obtain the audio files.

### Step 4: Transcribe Audio Files

To transcribe downloaded audio files:

```bash
python transcribe_audio.py
```

This will transcribe all episodes that have audio files and store the transcripts in `data/transcripts/`.

To transcribe a specific episode by its video ID:

```bash
python transcribe_audio.py --episode VIDEO_ID
```

Or with a limit:

```bash
python transcribe_audio.py --limit 3
```

## Command-Line Options

### Download Podcast Script

- `-l, --limit`: Limit the number of episodes to download
- `-i, --info-only`: Only fetch metadata without downloading audio
- `-f, --format`: Audio format (default: mp3)
- `-q, --quality`: Audio quality in kbps (default: 192)

### Transcribe Audio Script

- `-l, --limit`: Limit the number of episodes to transcribe
- `-e, --episode`: Transcribe only a specific episode by video ID
- `--language`: Language code for transcription (default: en-US)
- `--model`: Deepgram model to use (default: nova)

## Project Structure

```
allinvault/
├── data/              # Data storage directory
│   ├── audio/         # Downloaded audio files
│   ├── json/          # JSON database files
│   └── transcripts/   # Transcripts of audio files
├── src/               # Source code
│   ├── models/        # Data models
│   ├── repositories/  # Data storage layers
│   ├── services/      # Business logic services
│   └── utils/         # Utility functions
├── .env.example       # Example environment variables
├── download_podcast.py # Main download script
├── transcribe_audio.py # Transcription script
├── README.md          # Project documentation
└── requirements.txt   # Python dependencies
```

## Architecture

The project follows SOLID principles with a modular architecture:

- **Models Layer**: Data representation for podcast episodes
- **Services Layer**: Business logic for YouTube API, audio downloads, and transcription
- **Repository Layer**: Data storage and retrieval
- **Utils Layer**: Configuration and helper functions

See `architecture.md` for a detailed description of the architecture.

## License

MIT

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. 