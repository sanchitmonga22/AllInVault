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

## Opinion Extraction and Evolution Tracking

The opinion extraction system has been enhanced to better track and analyze how opinions evolve over time:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│  PodcastEpisode │────▶│ OpinionExtractor│────▶│     Opinion     │────▶│ OpinionEvolution│
│                 │     │                 │     │                 │     │                 │
└─────────────────┘     └────────┬────────┘     └───────┬─────────┘     └─────────────────┘
                                 │                      │
                                 │                      │
                         ┌───────▼───────┐      ┌───────▼───────┐
                         │               │      │               │
                         │   LLM Service │      │ CategorySystem│
                         │               │      │               │
                         └───────────────┘      └───────────────┘
```

### Enhanced Speaker Identification

The system now implements robust speaker identification:

1. **Proper Name Resolution**: Maps speaker IDs to full names using episode metadata
2. **Role Identification**: Identifies speakers as hosts, guests, or unknown participants
3. **Consistent Tracking**: Ensures the same speaker's opinions are properly connected across episodes
4. **Metadata Enrichment**: Includes all available speaker information for better context
5. **Multi-Speaker Support**: Properly handles opinions shared by multiple speakers

### Enhanced Opinion Model

The Opinion model has been improved with:

1. **Categorization**: Opinions now link to a Category entity with unique IDs, allowing for structured categorization
2. **Evolution Tracking**: New fields track how opinions evolve across episodes:
   - `related_opinions`: Connects to other opinions on the same topic
   - `evolution_notes`: Contains details on how opinions change
   - `original_opinion_id`: References the first opinion in an evolution chain
   - `evolution_chain`: Tracks the chronological development of an opinion
3. **Multi-Speaker Opinions**: Support for opinions shared by multiple speakers:
   - Tracks all speaker IDs associated with a shared opinion
   - Displays combined speaker names for shared opinions
   - Provides helper methods for working with multi-speaker opinions
   - Includes metadata to identify and analyze shared opinions

### Intelligent Context Management

The system now optimizes the context sent to the LLM by:

1. **Relevance Filtering**: Only sending the most relevant previous opinions based on:
   - Same speaker
   - Same category
   - Recent opinions
   
2. **Context Limitation**: Capping the number of context opinions to avoid overwhelming the LLM

3. **Structured Formatting**: Organizing opinions by category for clearer context

### Opinion Evolution Analysis

The system analyzes how opinions evolve through several mechanisms:

1. **Contradiction Detection**: Identifies when speakers change their stance
2. **Refinement Tracking**: Captures when opinions are clarified or expanded
3. **Cross-Speaker Relations**: Links related opinions across different speakers
4. **Chain Building**: Constructs chronological chains of evolving opinions
5. **Consensus Tracking**: Identifies when multiple speakers share the same opinion
6. **Agreement/Disagreement**: Captures when speakers agree or disagree on the same topic

## Dynamic Category Management

The category system has been enhanced to support flexible classification:

1. **Predefined Categories**: The system comes with default categories for common topics
2. **Dynamic Creation**: New categories can be created when the LLM identifies new topics
3. **LLM Suggestions**: The LLM can suggest new categories when opinions don't fit existing ones
4. **ID-Based Reference**: Opinions reference categories by ID rather than string names
5. **Hierarchical Support**: Categories can have parent-child relationships
6. **Category Migration**: Legacy opinions are automatically migrated to the new category system

## Opinion Processing Workflow

The system processes opinions in a chronological workflow:

1. **Sequential Processing**: Episodes are processed in date order
2. **Context Building**: Each episode builds on the context from previous episodes
3. **Rate Limit Management**: Processing includes delays to handle API rate limits
4. **Existing Opinion Detection**: Avoids reprocessing episodes that already have opinions
5. **Statistical Analysis**: Provides opinion distribution statistics after each episode

## Opinion Retrieval Capabilities

The enhanced system supports retrieving opinions by:

1. **Category**: Find all opinions in a specific category
2. **Speaker**: Find all opinions expressed by a specific speaker
3. **Episode**: Find all opinions from a specific episode
4. **Evolution Chain**: Trace the evolution of an opinion over time
5. **Related Opinions**: Find all opinions related to a specific opinion
6. **Shared Opinions**: Find opinions shared by multiple speakers
7. **Agreement/Disagreement**: Find patterns of agreement or disagreement between speakers

## Data Flow

```
YouTube API ─────► Metadata ─────► Audio Files ─────► Transcripts ─────► Speaker Identification ─────► Opinion Extraction
     │               │                │                   │                        │                         │
     │               │                │                   │                        │                         │
     ▼               ▼                ▼                   ▼                        ▼                         ▼
episodes.json     metadata      audio files         transcript files        speaker metadata           opinions.json
```

## Key Design Principles

1. **Modularity**: Each component handles a specific responsibility
2. **Pipeline Structure**: Clear dependencies between stages
3. **Flexibility**: Support for different LLM providers
4. **Error Handling**: Robust handling of API rate limits and failures
5. **Data Persistence**: JSON-based storage for episodes and opinions
6. **Evolution Tracking**: Comprehensive tracking of opinion changes over time

## Benefits of This Architecture

1. **Scalability**: Pipeline stages can be executed independently or in sequence.
2. **Flexibility**: Each component can be replaced or extended without affecting others.
3. **Maintainability**: Clear separation of concerns makes the codebase easier to maintain.
4. **Extensibility**: New features can be added by creating new pipeline stages.
5. **Robustness**: Each stage can handle errors independently, preventing pipeline failure.

## Future Architecture Enhancements

1. Database integration for more efficient data storage and retrieval
2. Advanced opinion evolution visualization tools
3. Support for additional LLM providers
4. API layer for web/mobile application integration
5. Semantic search for finding related opinions across different wording

## AllInVault Architecture Overview

## System Architecture

AllInVault is designed to extract, process, and track opinions from podcast transcripts using a modular, extensible architecture following SOLID principles.

### Core Components

```
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  PipelineOrchestrator│────▶│OpinionExtractorService│───▶│   LLM Service      │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
          │                          │                            │
          │                          │                            │
          ▼                          ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│  Episode Repository  │     │  Opinion Repository │     │ Category Repository │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
          │                          │                            │
          │                          │                            │
          ▼                          ▼                            ▼
┌─────────────────────┐     ┌─────────────────────┐     ┌─────────────────────┐
│   Podcast Episode   │     │       Opinion       │     │      Category       │
└─────────────────────┘     └─────────────────────┘     └─────────────────────┘
```

## Opinion Extraction Pipeline

The opinion extraction process flows through several key components:

1. **PipelineOrchestrator**: Coordinates the extraction process across multiple episodes
2. **OpinionExtractorService**: Processes transcript files and extracts opinions
3. **LLMService**: Interfaces with language models (like OpenAI) to analyze transcripts
4. **Repositories**: Store and manage podcast episodes, opinions, and categories

## Recent Enhancement: Multi-format Transcript Support

### Changes Made

We've enhanced the system to support both JSON and TXT transcript formats:

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

## Data Flow

1. User runs the script with desired options, including transcript format preference
2. System loads episodes and matches them with transcript files
3. For each transcript:
   - The file is loaded based on its format (.json or .txt)
   - Content is converted to a standardized structure
   - The transcript is formatted for LLM processing
   - The LLM extracts opinions
   - Opinions are processed and stored

## Benefits of the New Architecture

1. **Format Flexibility**: The system can now work with multiple transcript formats
2. **Fault Tolerance**: Falls back to available format if preferred format isn't available
3. **Maintainability**: Clean separation of concerns with dedicated methods for format handling
4. **Extensibility**: Easy to add support for additional formats in the future

## Future Enhancements

Potential future improvements include:

1. Support for additional transcript formats (SRT, VTT, etc.)
2. Streaming transcript processing for very large files
3. Parallel processing of multiple episodes
4. Advanced caching of intermediate results

# Opinion Evolution Tracking Architecture

## Overview

This document outlines the architecture for tracking opinion evolution across podcast episodes. The system is designed to track how speakers' opinions on specific topics evolve over time, identify contradictions, and analyze relationships between opinions.

## Data Models

### Opinion

The core model representing a unique opinion that can appear in multiple episodes:

```
Opinion
├── id: Unique identifier
├── title: Short summary 
├── description: Detailed description
├── category_id: Category classification
├── related_opinions: List of related opinion IDs
├── evolution_notes: Notes on how this opinion evolved
├── evolution_chain: Chronological chain of opinion IDs
├── is_contradiction: Flag for contradiction
├── contradicts_opinion_id: ID of contradicted opinion
├── contradiction_notes: Notes about the contradiction
├── appearances: List of OpinionAppearance objects
├── keywords: Associated keywords
└── metadata: Additional metadata
```

### OpinionAppearance

Represents a specific appearance of an opinion in an episode:

```
OpinionAppearance
├── episode_id: Episode identifier
├── episode_title: Episode title
├── date: Episode date
├── speakers: List of SpeakerStance objects
├── content: Actual content from this episode
├── context_notes: Context for this appearance
└── evolution_notes_for_episode: Episode-specific evolution notes
```

### SpeakerStance

Tracks a speaker's position on an opinion in a specific episode:

```
SpeakerStance
├── speaker_id: Speaker identifier
├── speaker_name: Speaker name
├── stance: Position (support, oppose, neutral)
├── reasoning: Explanation of stance
├── start_time: Start timestamp
└── end_time: End timestamp
```

## Workflow

1. **Opinion Extraction**: Analyze transcripts to identify opinions
2. **Category Classification**: Assign categories to opinions
3. **Opinion Linking**: Connect related opinions across episodes
4. **Evolution Tracking**: Track changes in speaker stances over time
5. **Contradiction Detection**: Identify when opinions contradict each other

## Opinion Evolution Process

The opinion evolution tracking process works as follows:

1. When processing a new episode:
   - Extract opinions with their speakers and stances
   - Categorize each opinion

2. For each extracted opinion:
   - Compare with existing opinions in the same category
   - If it's related to an existing opinion, link them together
   - Track how speaker positions on this opinion have changed

3. After processing multiple episodes:
   - Generate evolution timelines for each opinion
   - Identify patterns of opinion changes for each speaker

## Diagram

```
┌─────────────────┐     ┌────────────────┐     ┌───────────────────┐
│  Episode 1      │     │  Episode 2     │     │  Episode 3        │
│  Date: Jan 2023 │     │  Date: Feb 2023│     │  Date: Mar 2023   │
└────────┬────────┘     └───────┬────────┘     └──────────┬────────┘
         │                      │                         │
         ▼                      ▼                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                       Opinion Database                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────┐                                            │
│  │ Opinion A       │                                            │
│  │ Category: Tech  │◄────┐                                      │
│  └────────┬────────┘     │                                      │
│           │              │                                      │
│           ▼              │                                      │
│  ┌─────────────────┐     │ contradicts                          │
│  │ Appearance 1    │     │                                      │
│  │ Episode: Ep1    │     │                                      │
│  │ ┌────────────┐  │     │                                      │
│  │ │Speaker 1   │  │     │                                      │
│  │ │Stance: Pro │  │     │     ┌─────────────────┐             │
│  │ └────────────┘  │     └─────┤ Opinion B       │             │
│  └─────────────────┘           │ Category: Tech  │             │
│                                └────────┬────────┘             │
│                                         │                      │
│                             evolves into│                      │
│                                         ▼                      │
│  ┌─────────────────┐           ┌─────────────────┐             │
│  │ Appearance 2    │           │ Opinion C       │             │
│  │ Episode: Ep2    │           │ Category: Tech  │◄────┐       │
│  │ ┌────────────┐  │           └────────┬────────┘     │       │
│  │ │Speaker 1   │  │                    │              │       │
│  │ │Stance: Con │  │                    ▼              │       │
│  │ └────────────┘  │           ┌─────────────────┐     │       │
│  │ ┌────────────┐  │           │ Appearance 3    │     │       │
│  │ │Speaker 2   │  │           │ Episode: Ep3    │     │related│
│  │ │Stance: Pro │  │           │ ┌────────────┐  │     │       │
│  │ └────────────┘  │           │ │Speaker 1   │  │     │       │
│  └─────────────────┘           │ │Stance: Pro │  │     │       │
│                                │ └────────────┘  │     │       │
│                                └─────────────────┘     │       │
│                                                        │       │
│                                ┌─────────────────┐     │       │
│                                │ Opinion D       │◄────┘       │
│                                │ Category: Tech  │             │
│                                └─────────────────┘             │
│                                                                │
└─────────────────────────────────────────────────────────────────┘
```

## Benefits of this Architecture

1. **Speaker Tracking**: Tracks individual speaker opinions over time
2. **Contradiction Detection**: Identifies when speakers contradict themselves
3. **Cross-Episode Analysis**: Links opinions across multiple episodes
4. **Evolution Visualization**: Shows how opinions evolve chronologically
5. **Multi-Speaker Support**: Handles shared opinions with different stances

## Future Enhancements

1. Add sentiment analysis for opinions
2. Implement confidence scoring for opinion matches
3. Create visualizations of opinion evolution
4. Add support for topic clustering
5. Develop an opinion search and filtering interface

## Opinion Extraction System

The opinion extraction system in AllInVault is designed to accurately extract, categorize, track, and merge opinions from podcast transcripts. The system uses a multi-stage approach to address context size limitations and improve accuracy.

### System Architecture Diagram

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                            Opinion Extraction Service                         │
└───────────────────────────────────┬──────────────────────────────────────────┘
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
                                         ┌──────────────────────────────────────┐
                                         │                                      │
                                         │ Opinion Repository                   │
                                         │                                      │
                                         └──────────────────────────────────────┘
```

### Component Responsibilities

1. **Opinion Extraction Service**
   - Main orchestration service
   - Initializes and coordinates the other services
   - Provides a high-level API for the application

2. **Raw Extraction Service**
   - Extracts raw opinions from individual episode transcripts
   - Focuses on high-quality extraction without considering cross-episode relationships
   - Captures complete speaker metadata (ID, name, timestamps, stance, reasoning)

3. **Categorization Service**
   - Standardizes opinion categories
   - Groups opinions by category for focused relationship analysis
   - Maps custom categories to standard ones

4. **Relationship Analysis Service**
   - Analyzes relationships between opinions in the same category
   - Identifies SAME_OPINION, RELATED, EVOLUTION, and CONTRADICTION relationships
   - Processes opinions in manageable batches

5. **Merger Service**
   - Merges opinions that represent the same core opinion
   - Processes relationship links between opinions
   - Creates structured Opinion objects with all metadata

6. **Opinion Repository**
   - Handles persistence of opinions
   - Provides methods to retrieve existing opinions
   - Ensures efficient storage and retrieval

### Multi-Stage Workflow

The system follows a clearly defined workflow:

1. **Raw Opinion Extraction**
   - Process each episode individually
   - Extract detailed opinion data with speaker information
   - Focus on quality extraction without cross-episode context

2. **Categorization**
   - Standardize categories across all opinions
   - Group opinions by category for focused analysis

3. **Relationship Analysis**
   - Process opinions within the same category
   - Identify relationships between opinions
   - Analyze in smaller batches to avoid context limits

4. **Opinion Merging and Finalization**
   - Merge related opinions 
   - Establish contradiction and evolution links
   - Create final Opinion objects with all metadata

5. **Storage**
   - Save opinions to the repository
   - Update episode metadata with references to opinions

### Data Models

The system uses three main data models:

1. **Opinion**
   - Represents a unique opinion that can appear across episodes
   - Contains metadata, appearances, and relationship info

2. **OpinionAppearance**  
   - Represents a specific appearance of an opinion in an episode
   - Contains episode metadata and speaker information

3. **SpeakerStance**
   - Represents a speaker's stance on an opinion
   - Contains detailed speaker metadata and timestamps

### Benefits of This Architecture

1. **Scalability**
   - Processes episodes incrementally
   - Handles large numbers of opinions efficiently
   - Divides work into manageable chunks

2. **Accuracy**
   - Multi-stage approach improves opinion extraction quality
   - Categorized relationship analysis reduces noise
   - Detailed speaker metadata enables better tracking

3. **Maintainability**
   - Clear separation of concerns
   - Modular components that can be improved independently
   - Well-defined interfaces between components

4. **Flexibility**
   - Easy to add new relationship types
   - Can be extended with additional analysis steps
   - Configurable parameters for tuning performance

5. **Resilience**
   - Each stage has independent error handling
   - Failed operations can be retried without affecting others
   - Detailed logging helps identify and fix issues

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

### Usage by Services

Several services utilize the LLM integration:

- **SpeakerIdentificationService**: Maps anonymous speakers to real names
- **OpinionExtractionService**: Main orchestrator for opinion analysis
  - **RawOpinionExtractionService**: Extracts initial opinions
  - **OpinionCategorizationService**: Categorizes opinions
  - **OpinionRelationshipService**: Analyzes relationships

### Configuration

LLM settings can be configured:
- Via environment variables for API keys
- Via command-line arguments for scripts (e.g., `--llm-model`)
- Via class constructor parameters for programmatic use

The default configuration now uses:
- Provider: `deepseek`
- Model: `deepseek-chat` (DeepSeek-V3)

### Implementation Changes

- Modified `DeepSeekProvider` to use DeepSeek's implementation of the API
- Updated default provider across all services from OpenAI to DeepSeek
- Changed default model from "gpt-4o" to "deepseek-chat"
- Added DeepSeek API URL and client configuration
- Ensured proper error handling for DeepSeek API responses

### API Format Compatibility

DeepSeek API uses a format compatible with OpenAI. The primary differences are:
- Base URL: `https://api.deepseek.com`
- Authentication: Uses the same Bearer token format but with DeepSeek API key
- Model name: Uses "deepseek-chat" for DeepSeek-V3