# AllInVault Architecture

This document describes the architecture of the AllInVault system, focusing on the podcast processing pipeline and the opinion extraction feature.

## System Overview

AllInVault is a platform for processing, analyzing, and extracting insights from podcast episodes. The system follows a modular, pipeline-based architecture that processes podcast episodes through several stages, from fetching metadata to extracting opinions.

## Core Architecture Components

### 1. Data Model Layer

- **PodcastEpisode**: Represents a single podcast episode with metadata, audio files, and transcripts
- **Opinion**: Represents an opinion expressed by a speaker in a podcast episode, including details about the speaker, context, and sentiment
- **Category**: Represents a classification for opinions with unique IDs and descriptive information

### 2. Repository Layer

- **JsonFileRepository**: Manages storage and retrieval of podcast episodes in JSON format
- **OpinionRepository**: Manages storage and retrieval of opinions in JSON format
- **CategoryRepository**: Manages storage and retrieval of opinion categories in JSON format

### 3. Service Layer

- **Pipeline Orchestrator**: Manages the execution of the multi-stage pipeline
- **LLM Service**: Provides integration with language models for enhanced analysis
- **Opinion Extractor Service**: Extracts opinions from podcast transcripts using LLM
- **Checkpoint Service**: Manages extraction progress and enables resumable operations

### 4. CLI Layer

- **Pipeline Command**: Provides a unified command-line interface for running the pipeline

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
6. **IDENTIFY_SPEAKERS**: Maps speakers in the transcripts to actual identities.
7. **EXTRACT_OPINIONS**: Uses LLM to extract opinions from the transcripts.

## LLM Integration

The AllInVault platform utilizes Large Language Models (LLMs) to perform several key functions:

1. **Speaker Identification**: Identifying podcast hosts and guests from transcript data
2. **Opinion Extraction**: Extracting key opinions expressed in podcast episodes
3. **Opinion Categorization**: Categorizing opinions into predefined categories
4. **Relationship Analysis**: Finding relationships and contradictions between opinions

### LLM Provider Architecture

The platform is designed with a modular architecture that supports multiple LLM providers. The current implementation includes:

- **DeepSeek-V3** (Primary Provider)
- **OpenAI** (Alternative Provider)

```
┌───────────────────┐
│                   │
│   LLMService      │
│                   │
└─────────┬─────────┘
          │
          ▼
┌─────────────────────┐
│    LLMProvider      │
│    (Abstract)       │
└─────────────────────┘
          ▲
          │
┌─────────┴─────────┐
│                   │
▼                   ▼
┌───────────────┐   ┌───────────────┐
│ DeepSeekProvider│  │ OpenAIProvider│
└───────────────┘   └───────────────┘
```

### Integration Components

#### LLMService

The main service class that provides a unified interface for all LLM operations. It delegates to the appropriate provider based on configuration.

#### LLMProvider (Abstract Base Class)

Defines the contract for all LLM providers with these abstract methods:
- `extract_speakers()`: Identifies speakers in podcast episodes
- `extract_opinions_from_transcript()`: Extracts opinions from transcript text

#### DeepSeekProvider

Implementation of the LLM provider interface that uses DeepSeek-V3. The model is accessed via the "deepseek-chat" model name through the DeepSeek API.

Key features:
- Compatible with OpenAI format but uses DeepSeek's models
- Uses DeepSeek-V3 for improved performance
- Requires DEEP_SEEK_API_KEY environment variable

#### OpenAIProvider

Alternative implementation using OpenAI models, kept for compatibility and comparison.

### Configuration

LLM settings can be configured:
- Via environment variables for API keys
- Via command-line arguments for scripts (e.g., `--llm-model`)
- Via class constructor parameters for programmatic use

The default configuration now uses:
- Provider: `deepseek`
- Model: `deepseek-chat` (DeepSeek-V3)

## Multi-format Transcript Support

AllInVault supports both JSON and TXT transcript formats:

1. **OpinionExtractorService Modifications**:
   - Added `_load_txt_transcript()` method to parse TXT transcript files
   - Updated `load_transcript()` to detect file format and choose appropriate loading method
   - Refactored `_format_transcript_for_llm()` to handle both format structures

2. **Script Updates**:
   - Added `--transcript-format` command-line argument to specify preferred format
   - Created `update_transcript_filenames()` function to match episodes with appropriate transcript files
   - Enhanced logging to show transcript format information

### TXT Format Handling

The TXT transcript files follow this format:
```
# Episode Title
Video ID: [VIDEO_ID]
Published: [DATE]

================================================================================

[TIMESTAMP] Speaker N: [TEXT]
[TIMESTAMP] Speaker N: [TEXT]
...
```

The system parses this format and converts it to a standardized internal structure compatible with the existing JSON format processing.

## Opinion Evolution Tracking System Architecture

The Opinion Evolution Tracking system processes podcast episodes to extract, categorize, and track opinions expressed by speakers across multiple episodes. This comprehensive system identifies relationships between opinions, tracks their evolution, and provides insight into how opinions change over time.

### System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                     OPINION EVOLUTION TRACKING SYSTEM                                      │
└───────────────────────────────────────────────────────┬───────────────────────────────────────────────────┘
                                                        │
                   ┌───────────────────────────────────┐│┌─────────────────────────────────────┐
                   │         DATA PREPARATION          │││        RELATIONSHIP ANALYSIS        │
                   │                                   │││                                     │
                   │  ┌─────────────┐ ┌─────────────┐  │││  ┌─────────────┐  ┌─────────────┐  │
                   │  │             │ │             │  │││  │             │  │             │  │
                   │  │ Raw Opinion │ │Categorize & │  │││  │ Semantic    │  │ Relationship│  │
                   │  │ Extraction  ├─►Standardize  ├──┼┼┼─►│ Similarity  ├──►Detection    │  │
                   │  │             │ │             │  ││││ │ Analysis    │  │             │  │
                   │  └─────────────┘ └─────────────┘  ││││ └─────────────┘  └──────┬──────┘  │
                   │                                   ││││                          │         │
                   └───────────────────────────────────┘│││                          │         │
                                                        │││                          │         │
                                                        │││                          ▼         │
                   ┌───────────────────────────────────┐│││ ┌─────────────┐  ┌─────────────┐  │
                   │         EVOLUTION TRACKING        ││││ │             │  │             │  │
                   │                                   ││││ │ Contradiction│  │ Evolution   │  │
                   │  ┌─────────────┐ ┌─────────────┐  ││││ │ Detection   │◄─┤ Tracking    │  │
                   │  │             │ │             │  ││││ │             │  │             │  │
                   │  │ Evolution   │ │Speaker      │  ││││ └─────────────┘  └──────┬──────┘  │
                   │  │ Chain       │◄┤Stance       │◄─┼┼┼┘                         │         │
                   │  │ Building    │ │Tracking     │  ││                           │         │
                   │  └─────────────┘ └─────────────┘  ││                           │         │
                   │                                   ││                            │         │
                   └───────────────────────────────────┘│                            │         │
                                                        │                            │         │
                                                        │                            ▼         │
                   ┌───────────────────────────────────┐│                    ┌─────────────┐  │
                   │          DATA INTEGRATION         ││                    │             │  │
                   │                                   ││                    │Opinion      │  │
                   │  ┌─────────────┐ ┌─────────────┐  ││                    │Merger      │  │
                   │  │             │ │             │  ││                    │Service     │  │
                   │  │Unified      │ │Timeline     │  ││                    │            │  │
                   │  │Opinion      │◄┤Generation   │◄─┼┘                    └─────────────┘  │
                   │  │Repository   │ │             │  │                                      │
                   │  └─────────────┘ └─────────────┘  │                                      │
                   │                                   │                                      │
                   └───────────────────────────────────┘                                      │
```

### Opinion Extraction Service Architecture

The modular service architecture enables accurate opinion extraction, categorization, tracking, and merging:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Opinion Extraction Service                         │
└───────────────────────────────┬──────────────────────────────────────────────┘
                               │
                               │ Orchestrates
                               ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                                                                              │
│  ┌───────────────────┐    ┌──────────────────┐    ┌─────────────────────┐   │
│  │                   │    │                  │    │                     │   │
│  │ Raw Extraction    ├───►│ Categorization   ├───►│ Relationship        │   │
│  │ Service           │    │ Service          │    │ Analysis Service    │   │
│  │                   │    │                  │    │                     │   │
│  └───────────────────┘    └──────────────────┘    └──────────┬──────────┘   │
│                                                              │              │
│                                                              ▼              │
│                                                   ┌─────────────────────┐   │
│                                                   │                     │   │
│                                                   │ Merger Service      │   │
│                                                   │                     │   │
│                                                   └──────────┬──────────┘   │
│                                                              │              │
└──────────────────────────────────────────────────────────────┼──────────────┘
                                                              │
                                                              ▼
                            ┌───────────────────────────────────────────────────┐
                            │                                                   │
                            │ Checkpoint Service                                │
                            │                                                   │
                            └───────────────────┬───────────────────────────────┘
                                               │
                                               ▼
                            ┌──────────────────────────────────────┐
                            │                                      │
                            │ Opinion Repository                   │
                            │                                      │
                            └──────────────────────────────────────┘
```

### Component Responsibilities

1. **Raw Extraction Service**
   - Extracts raw opinions from individual episode transcripts
   - Focuses on high-quality extraction without considering cross-episode relationships
   - Captures complete speaker metadata (ID, name, timestamps, stance, reasoning)

2. **Categorization Service**
   - Standardizes opinion categories
   - Groups opinions by category for focused relationship analysis
   - Maps custom categories to standard ones

3. **Relationship Analysis Service**
   - Analyzes relationships between opinions in the same category
   - Identifies SAME_OPINION, RELATED, EVOLUTION, and CONTRADICTION relationships
   - Processes opinions in manageable batches

4. **Merger Service**
   - Merges opinions that represent the same core opinion
   - Processes relationship links between opinions
   - Creates structured Opinion objects with all metadata

5. **Checkpoint Service**
   - Tracks progress of the opinion extraction process
   - Stores checkpoint data for each stage of the extraction pipeline
   - Enables resumable processing of long-running extraction tasks
   - Manages raw opinion data persistence during extraction
   - Provides extraction statistics and progress information

6. **Opinion Repository**
   - Handles persistence of opinions
   - Provides methods to retrieve existing opinions
   - Ensures efficient storage and retrieval

### Checkpoint Service Architecture

The Checkpoint Service enables resumable extraction processing with the following components:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                               Checkpoint Service                              │
└──────────────────────────────────────┬───────────────────────────────────────┘
                                       │
           ┌───────────────────────────┼───────────────────────────┐
           │                           │                           │
           ▼                           ▼                           ▼
┌────────────────────────┐  ┌────────────────────────┐  ┌────────────────────────┐
│                        │  │                        │  │                        │
│ Stage Completion       │  │ Episode Tracking       │  │ Raw Opinion Storage    │
│ Tracking               │  │                        │  │                        │
│                        │  │                        │  │                        │
└────────────────────────┘  └────────────────────────┘  └────────────────────────┘
           │                           │                           │
           └───────────────────────────┼───────────────────────────┘
                                       │
                                       ▼
                        ┌─────────────────────────────────┐
                        │                                 │
                        │       Checkpoint File           │
                        │     (JSON Persistence)          │
                        │                                 │
                        └─────────────────────────────────┘
```

#### Key Features

1. **Stage-based Checkpointing**
   - Tracks completion of each extraction stage independently
   - Allows skipping already completed stages when resuming
   - Provides clear progress indication for complex extraction pipelines

2. **Episode-level Tracking**
   - Maintains a list of processed episode IDs
   - Allows selective processing of only new episodes
   - Prevents duplicate processing of already extracted episodes

3. **Raw Opinion Persistence**
   - Stores extracted raw opinions in a separate JSON file
   - Enables resuming from intermediate extraction stages
   - Reduces need to re-extract opinions from transcripts

4. **Extraction Statistics**
   - Tracks processing time for each stage
   - Monitors number of opinions extracted
   - Provides summary of extraction progress and completion status

5. **Resumable Processing**
   - Enables stopping and resuming long-running extraction tasks
   - Preserves intermediate data during extraction
   - Minimizes repeated work when process is interrupted

6. **JSON-based Persistence**
   - Uses simple JSON files for checkpoint data storage
   - Maintains human-readable checkpoint state
   - Enables easy debugging and manual intervention if needed

### Parallel Processing Architecture

The raw opinion extraction stage has been optimized with parallel processing to improve performance:

```
┌─────────────────┐     ┌─────────────────┐     ┌────────────────────┐
│                 │     │                 │     │                    │
│  Episode Batch  │────▶│  Thread Pool    │────▶│  Opinion Storage   │
│                 │     │  Executor       │     │                    │
└─────────────────┘     └─────────────────┘     └────────────────────┘
                              │  │  │
                              │  │  │
                              ▼  ▼  ▼
                        ┌─────────────────┐
                        │  LLM Service    │
                        │  (API Calls)    │
                        └─────────────────┘
```

#### Key Features

1. **Batched Processing**
   - Episodes are processed in configurable batches to manage memory usage
   - Each batch is processed completely before moving to the next

2. **Thread Pool Executor**
   - Concurrent extraction using ThreadPoolExecutor
   - Configurable number of workers

3. **Timeout Management**
   - Each extraction job has a configurable timeout
   - Prevents hung jobs from blocking the entire process

4. **Incremental Saving**
   - Results from each batch are saved immediately
   - Minimizes data loss in case of interruption

### Enhanced Opinion Data Models

The system uses a comprehensive set of data models to represent opinions, their relationships, and evolution over time:

```
┌──────────────────┐     ┌───────────────────┐     ┌───────────────────┐
│                  │     │                   │     │                   │
│    Opinion       │─────┤  OpinionAppearance│─────┤   SpeakerStance   │
│                  │     │                   │     │                   │
└───────┬──────────┘     └───────────────────┘     └───────────────────┘
        │                                                    ▲
        │                                                    │
        │                                           ┌────────┴──────────┐
        │                                           │                   │
        │                                           │  PreviousStance   │
        │                                           │                   │
        │                                           └───────────────────┘
        │
        │
        ├───────────────┐     ┌───────────────────┐     ┌───────────────────┐
        │               │     │                   │     │                   │
        ▼               │     │                   │     │                   │
┌──────────────────┐    │     │   Relationship    │─────┤RelationshipEvidence│
│                  │    │     │                   │     │                   │
│  EvolutionChain  │    │     └───────────────────┘     └───────────────────┘
│                  │    │
└───────┬──────────┘    │
        │               │
        │               │
        ▼               │     ┌───────────────────┐     ┌───────────────────┐
┌──────────────────┐    │     │                   │     │                   │
│                  │    │     │   SpeakerJourney  │─────┤SpeakerJourneyNode │
│  EvolutionNode   │    │     │                   │     │                   │
│                  │    │     └───────────────────┘     └───────────────────┘
└──────────────────┘    │
        ▲               │
        │               │
        │               │     ┌───────────────────┐     ┌───────────────────┐
        │               │     │                   │     │                   │
        └───────────────┼─────┤  EvolutionPattern │     │   MergeRecord     │─────┐
                        │     │                   │     │                   │     │
                        │     └───────────────────┘     └───────────────────┘     │
                        │                                                          │
                        │                                                          │
                        │                                                          ▼
                        │                                               ┌───────────────────┐
                        │                                               │                   │
                        └───────────────────────────────────────────────┤ConflictResolution │
                                                                        │                   │
                                                                        └───────────────────┘
```

#### Core Opinion Models

- **Opinion**: The central model representing a unique opinion that can appear across multiple episodes
  - Contains metadata, description, category info, and appearances
  - Tracks relationships with other opinions
  - Contains evolution chain info
  
- **OpinionAppearance**: Represents an appearance of an opinion in a specific episode
  - Links to episode metadata
  - Contains speaker stances for this appearance
  - Tracks episode-specific content and context

- **SpeakerStance**: Models a speaker's stance on an opinion in a specific episode
  - Tracks support, opposition, or neutrality
  - Includes reasoning behind the stance
  - Contains timing information

#### Evolution Tracking Models

- **EvolutionChain**: Represents the chronological progression of an opinion across episodes
  - Contains ordered nodes representing opinion evolution points
  - Tracks pattern classification
  - Provides overall evolution metadata

- **EvolutionNode**: Models a single point in an opinion's evolution
  - Links to a specific opinion ID and episode
  - Classifies the evolution type (initial, refinement, pivot, etc.)
  - Contains description of the evolution at this point

- **EvolutionPattern**: Represents common patterns in opinion evolution
  - Provides pattern name and description
  - Lists typical steps in this pattern
  - Links to example chains that exhibit this pattern

#### Speaker Journey Models

- **SpeakerJourney**: Tracks a speaker's stance evolution across episodes
  - Contains speaker metadata
  - Maps opinions to journey nodes
  - Provides current stances on all opinions

- **SpeakerJourneyNode**: Represents a point in a speaker's journey with a specific stance
  - Links to opinion and episode
  - Tracks stance changes
  - Provides reasoning for stance positions

- **PreviousStance**: Extends SpeakerStance to track historical stances
  - Contains metadata about when and why a stance changed
  - Links to the episode where the change occurred
  - Tracks what the stance changed to

#### Relationship Models

- **Relationship**: Models connections between opinions
  - Classifies relationship type (same, similar, evolution, contradiction)
  - Contains directional information
  - Includes confidence scores and evidence

- **RelationshipEvidence**: Provides evidence for why a relationship exists
  - Describes the evidence in detail
  - Classifies evidence type (semantic, lexical, temporal, logical, LLM)
  - Includes confidence score for this piece of evidence

#### Merge Tracking Models

- **MergeRecord**: Tracks when opinions are merged together
  - Contains source and resulting opinion IDs
  - Includes merge rationale and method
  - Tracks conflicts that occurred during merge

- **ConflictResolution**: Models how a conflict was resolved during opinion merging
  - Documents the conflict field and conflicting values
  - Tracks resolution method and reasoning
  - Includes confidence in the resolution

These models work together to provide a comprehensive system for tracking opinions, their relationships, and their evolution across podcast episodes, while maintaining the history of speaker stances and opinion merges.

## Key Algorithms

### Semantic Similarity Detection

Uses a multi-faceted approach:
1. Embedding-based similarity (using sentence transformers)
2. LLM verification for borderline cases
3. Contextual analysis considering speaker, episode context, and timestamps

### Evolution Chain Building

1. Sorts opinions chronologically
2. Identifies evolution relationships between opinions
3. Constructs chains showing how opinions develop over time
4. Classifies evolution types (refinement, pivot, expansion, contraction)

### Speaker Stance Analysis

1. Tracks each speaker's stance on opinions
2. Identifies changes in stance over time
3. Provides reasoning for stance changes
4. Detects contradictions within a speaker's statements

### Checkpoint and Recovery

1. Tracks progress through extraction stages
2. Persists intermediate extraction data
3. Identifies already processed episodes
4. Provides resumable extraction capabilities
5. Optimizes extraction by skipping completed stages

## Benefits of This Architecture

1. **Scalability**: Pipeline stages can be executed independently or in sequence
2. **Flexibility**: Each component can be replaced or extended without affecting others
3. **Maintainability**: Clear separation of concerns makes the codebase easier to maintain
4. **Extensibility**: New features can be added by creating new pipeline stages
5. **Robustness**: Each stage can handle errors independently, preventing pipeline failure
6. **Comprehensive Tracking**: Complete history of opinions across episodes
7. **Evolution Analysis**: Visibility into how opinions change over time
8. **Speaker Consistency**: Ability to track speaker positions on topics
9. **Resumable Processing**: Ability to resume long-running extraction tasks after interruption
10. **Progress Tracking**: Detailed visibility into extraction progress and completion status

## Technology Stack

- **Language**: Python 3.9+
- **NLP Libraries**: Sentence Transformers, spaCy
- **Machine Learning**: PyTorch, scikit-learn
- **LLM Integration**: OpenAI API, DeepSeek API
- **Data Storage**: JSON files with structured schemas
- **Visualization**: Matplotlib, Plotly

## Future Enhancements

1. Database integration for more efficient data storage and retrieval
2. Advanced opinion evolution visualization tools
3. Support for additional LLM providers
4. API layer for web/mobile application integration
5. Semantic search for finding related opinions across different wording
6. Streaming transcript processing for very large files
7. Additional transcript format support (SRT, VTT, etc.)
8. Distributed processing for large-scale extraction tasks
9. Real-time extraction progress monitoring interface
10. Advanced checkpoint compression for efficient storage