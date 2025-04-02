# AllInVault Architecture

## Pipeline Architecture

AllInVault uses a flexible stage-based pipeline architecture for podcast processing. The pipeline consists of the following stages:

1. **FETCH_METADATA**: Retrieves episode metadata from YouTube
2. **ANALYZE_EPISODES**: Analyzes episodes to determine if they are full episodes or shorts
3. **DOWNLOAD_AUDIO**: Downloads raw audio files in WebM format
4. **CONVERT_AUDIO**: Converts WebM files to MP3 with parallel processing
5. **TRANSCRIBE_AUDIO**: Transcribes MP3 files using Deepgram API
6. **IDENTIFY_SPEAKERS**: Identifies speakers in transcripts

## Pipeline Flow

```
┌─────────────────┐
│ FETCH_METADATA  │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ ANALYZE_EPISODES│
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ DOWNLOAD_AUDIO  │ ─── WebM files ─── ▶ /data/webm
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ CONVERT_AUDIO   │ ─── MP3 files ──── ▶ /data/audio
│ (Parallel)      │
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ TRANSCRIBE_AUDIO│ ─── Transcripts ── ▶ /data/transcripts
└─────────┬───────┘
          │
          ▼
┌─────────────────┐
│ IDENTIFY_SPEAKERS│
└─────────────────┘
```

## Directory Structure

- `/data/json`: JSON metadata files
- `/data/webm`: Raw WebM audio files
- `/data/audio`: Converted MP3 audio files
- `/data/transcripts`: Transcriptions in JSON and text formats

## Key Components

### Models
- `PodcastEpisode`: Data model for podcast episodes, including metadata and file references

### Services
- `PipelineOrchestrator`: Manages the entire pipeline execution
- `YouTubeService`: Retrieves episode metadata from YouTube
- `EpisodeAnalyzerService`: Analyzes episodes to determine type
- `YtDlpDownloader`: Downloads and converts audio files
- `BatchTranscriberService`: Manages batch transcription of audio files
- `SpeakerIdentificationService`: Identifies speakers in transcripts

### Repository
- `JsonFileRepository`: Stores and retrieves podcast episode data

## Parallelization

The `CONVERT_AUDIO` stage uses Python's `concurrent.futures.ThreadPoolExecutor` to convert multiple audio files in parallel, improving performance. The number of parallel workers can be configured through the `conversion_threads` setting.