# AllInVault Architecture

This document describes the architecture of the AllInVault system, focusing on the podcast processing pipeline and the opinion extraction feature.

## System Overview

AllInVault is a system for processing, analyzing, and extracting insights from podcast episodes, specifically designed for the All-In Podcast. The system follows a modular, pipeline-based architecture where each stage performs a specific function in the data processing workflow.

## Pipeline Architecture

The pipeline is designed with a stage-based architecture, where each stage has a clear responsibility and can depend on previous stages:

```
                                           ┌───────────────────┐
                                           │                   │
                                           │  FETCH_METADATA   │
                                           │                   │
                                           └─────────┬─────────┘
                                                     │
                                                     ▼
                                           ┌───────────────────┐
                                           │                   │
                                           │  ANALYZE_EPISODES │
                                           │                   │
                                           └─────────┬─────────┘
                                                     │
                                                     ▼
                                           ┌───────────────────┐
                                           │                   │
                                           │  DOWNLOAD_AUDIO   │
                                           │                   │
                                           └─────────┬─────────┘
                                                     │
                                                     ▼
                                           ┌───────────────────┐
                                           │                   │
                                           │  CONVERT_AUDIO    │
                                           │                   │
                                           └─────────┬─────────┘
                                                     │
                                                     ▼
                                           ┌───────────────────┐
                                           │                   │
                                           │  TRANSCRIBE_AUDIO │
                                           │                   │
                                           └─────────┬─────────┘
                                                     │
                                                     ▼
                                           ┌───────────────────┐
                                           │                   │
                                           │  IDENTIFY_SPEAKERS│
                                           │                   │
                                           └─────────┬─────────┘
                                                     │
                                                     ▼
                                           ┌───────────────────┐
                                           │                   │
                                           │  EXTRACT_OPINIONS │
                                           │                   │
                                           └───────────────────┘
```

### Pipeline Stages

1. **FETCH_METADATA**: Retrieves episode metadata from YouTube API, including titles, descriptions, and publish dates.
2. **ANALYZE_EPISODES**: Analyzes episode metadata to classify and enrich episode information.
3. **DOWNLOAD_AUDIO**: Downloads episode audio files using a downloader service.
4. **CONVERT_AUDIO**: Converts audio to a consistent format suitable for transcription.
5. **TRANSCRIBE_AUDIO**: Transcribes audio into text, creating structured transcript files.
6. **IDENTIFY_SPEAKERS**: Identifies speakers in the transcripts using LLM.
7. **EXTRACT_OPINIONS**: Extracts opinions from the transcripts, tracking them over time.

## Opinion Extraction Architecture

The opinion extraction feature is a new component that processes transcripts to identify and track opinions expressed by podcast speakers over time. This feature follows the SOLID principles and is designed for scalability and extensibility.

### Opinion Extraction Components

```
┌─────────────────────────────┐      ┌────────────────────────┐
│                             │      │                        │
│  OpinionExtractorService    ├─────►│  OpinionRepository     │
│                             │      │                        │
└───────────────┬─────────────┘      └────────────────────────┘
                │                                 │
                │                                 │
                ▼                                 ▼
┌─────────────────────────────┐      ┌────────────────────────┐
│                             │      │                        │
│  LLMService                 │      │  Opinion (Model)       │
│                             │      │                        │
└───────────────┬─────────────┘      └────────────────────────┘
                │
                │
                ▼
┌─────────────────────────────┐
│                             │
│  OpenAIProvider             │
│                             │
└─────────────────────────────┘
```

### Component Responsibilities

1. **Opinion Model**: Data structure representing opinions with metadata, including:
   - Title, description, content
   - Speaker information
   - Episode information
   - Timestamps
   - Categorization and sentiment
   - Related opinions for tracking over time

2. **OpinionRepository**: Manages the storage and retrieval of opinion data:
   - Saves opinions to JSON file
   - Retrieves opinions by various criteria
   - Creates relationships between related opinions

3. **OpinionExtractorService**: Coordinates the extraction of opinions:
   - Processes transcripts in chronological order
   - Formats transcript data for LLM analysis
   - Constructs comprehensive prompts with context
   - Processes LLM results into structured opinion objects
   - Tracks opinion evolution over time

4. **LLMService**: Provides integration with language models:
   - Abstracts provider-specific implementation details
   - Handles API communication
   - Processes structured responses

5. **OpenAIProvider**: Implements LLM communication with OpenAI:
   - Formats prompts for opinion extraction
   - Handles API-specific parameters
   - Processes and validates responses

### Opinion Extraction Process Flow

1. Each episode is processed chronologically starting from the earliest.
2. The transcript is formatted for LLM processing.
3. A prompt is constructed that includes:
   - Episode metadata
   - Speaker information
   - Previously identified opinions for context
   - The formatted transcript
4. The LLM analyzes the transcript to identify opinions.
5. The raw LLM response is processed into structured Opinion objects.
6. Opinions are saved to the repository.
7. Episode metadata is updated with opinion references.
8. The collective knowledge of all prior opinions is used for context when processing subsequent episodes.

### Opinion Tracking Over Time

A key feature is the ability to track how opinions evolve over time:

1. When analyzing a new episode, all previously identified opinions are provided as context.
2. The LLM identifies relationships between new opinions and existing ones.
3. These relationships are stored, creating a graph of opinion evolution.
4. Each opinion includes metadata about how it relates to or evolves from previous opinions.

## Data Flow

```
YouTube API ─────► Metadata ─────► Audio Files ─────► Transcripts ─────► Speaker Identification ─────► Opinion Extraction
     │               │                │                   │                        │                         │
     │               │                │                   │                        │                         │
     ▼               ▼                ▼                   ▼                        ▼                         ▼
episodes.json     metadata      audio files         transcript files        speaker metadata           opinions.json
```

## Key Design Principles

1. **Single Responsibility**: Each component has a clear, focused responsibility.
2. **Open/Closed**: The system is open for extension (e.g., adding new LLM providers) but closed for modification.
3. **Interface Segregation**: Clear interfaces between components allow for flexible implementation.
4. **Dependency Inversion**: High-level modules don't depend on low-level modules but on abstractions.
5. **Modularity**: Each component can be developed, tested, and maintained independently.

## Benefits of This Architecture

1. **Scalability**: Pipeline stages can be executed independently or in sequence.
2. **Flexibility**: Each component can be replaced or extended without affecting others.
3. **Maintainability**: Clear separation of concerns makes the codebase easier to maintain.
4. **Extensibility**: New features can be added by creating new pipeline stages.
5. **Robustness**: Each stage can handle errors independently, preventing pipeline failure.

## Future Improvements

1. **Parallel Processing**: Implementing parallel processing for independent pipeline stages.
2. **Advanced Opinion Analysis**: Deeper analysis of opinions, including contradiction detection.
3. **Topic Modeling**: Clustering opinions around common topics or themes.
4. **Multi-Modal Analysis**: Incorporating visual and audio cues in opinion detection.
5. **User Interface**: Building a UI to explore opinions and their relationships.