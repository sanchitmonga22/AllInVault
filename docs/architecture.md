# Opinion Evolution Tracking System - Architecture

## System Overview

The Opinion Evolution Tracking System is designed to extract, analyze, and track the evolution of opinions expressed in podcast episodes. The system follows a modular architecture adhering to SOLID principles, with clear separation of concerns and well-defined interfaces between components.

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     Opinion Evolution Tracking System                    │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                            Pipeline Orchestrator                         │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                                                                         │
│  ┌───────────────┐  ┌───────────────┐  ┌───────────────┐  ┌───────────┐  │
│  │     Raw       │  │ Categorization│  │ Relationship  │  │  Opinion  │  │
│  │  Extraction   │──▶│    Service    │──▶│   Service    │──▶│  Merger  │  │
│  │   Service     │  │               │  │               │  │  Service  │  │
│  └───────────────┘  └───────────────┘  └───────────────┘  └───────────┘  │
│                                                                         │
│  ┌───────────────┐  ┌───────────────┐                ┌─────────────────┐ │
│  │   Speaker     │  │   Evolution   │                │                 │ │
│  │   Tracking    │◀─│    Service    │◀───────────────│ Checkpoint      │ │
│  │   Service     │  │               │                │ Service         │ │
│  └───────────────┘  └───────────────┘                └─────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                     │
                                     ▼
┌─────────────────────────────────────────────────────────────────────────┐
│                           Data Repositories                              │
└─────────────────────────────────────────────────────────────────────────┘
```

## Core Components

### 1. Pipeline Orchestrator

**Class**: `OpinionExtractionService`

The pipeline orchestrator is responsible for coordinating the entire opinion extraction and analysis process. It:

- Initializes and manages the various service components
- Controls the flow of data between stages
- Handles error recovery and resumption through the checkpoint service
- Provides a unified API for triggering the extraction process

### 2. Raw Opinion Extraction Service

**Class**: `RawOpinionExtractionService`

This service extracts raw opinions from podcast transcripts using LLM-based analysis:

- Processes episode transcripts to identify key opinions
- Structures opinion data with metadata (speaker, category, etc.)
- Adheres to a standardized JSON schema for extracted opinions
- Leverages LLMs for natural language understanding

### 3. Categorization Service

**Class**: `OpinionCategorizationService`

Responsible for classifying and enriching raw opinions:

- Assigns opinions to predefined or dynamic categories
- Extracts key topics and themes
- Identifies opinion polarity and sentiment
- Enhances metadata with additional context

### 4. Relationship Analysis Service

**Class**: `OpinionRelationshipService`

Analyzes relationships between opinions:

- Identifies contradictions between opinions
- Detects supporting or opposing viewpoints
- Maps connections between related opinions
- Establishes temporal relationships

### 5. Opinion Merger Service

**Class**: `OpinionMergerService`

Consolidates similar or duplicate opinions:

- Identifies semantically similar opinions using vector similarity
- Combines related opinions while preserving unique aspects
- Reconciles metadata from multiple sources
- Maintains links to original opinions

### 6. Evolution Service

**Class**: `OpinionEvolutionService`

Tracks how opinions evolve over time:

- Builds evolution chains linking related opinions
- Detects shifts in viewpoints
- Identifies refinements or elaborations on previous opinions
- Establishes chronological progression of opinion development

### 7. Speaker Tracking Service

**Class**: `SpeakerTrackingService`

Monitors speaker stances over time:

- Tracks speaker consistency and contradictions
- Maps opinion journeys for individual speakers
- Identifies opinion changes or developments by speaker
- Supports analysis of speaker dynamics

### 8. Checkpoint Service

**Class**: `CheckpointService`

Manages the extraction progress and enables resumable processing:

- Tracks completion status of each extraction stage
- Maintains records of processed episodes
- Preserves intermediate data for recovery
- Supports stage-specific progress tracking
- Enables resumption from any point in the pipeline

## Data Model

### Opinion Structure

Opinions evolve through the pipeline, gaining enrichment at each stage:

1. **Raw Opinion**:
   ```json
   {
     "id": "op123",
     "title": "Climate Policy Effectiveness",
     "description": "View on effectiveness of carbon taxes",
     "content": "Carbon taxes are the most effective tool for emissions reduction",
     "speakers": ["John Doe"],
     "category": "Climate Policy",
     "keywords": ["carbon tax", "emissions", "climate policy"],
     "episode_id": "ep456"
   }
   ```

2. **Processed Opinion** (after pipeline completion):
   ```json
   {
     "id": "op123",
     "title": "Climate Policy Effectiveness",
     "description": "View on effectiveness of carbon taxes",
     "content": "Carbon taxes are the most effective tool for emissions reduction",
     "speakers": ["John Doe"],
     "category": "Climate Policy",
     "keywords": ["carbon tax", "emissions", "climate policy"],
     "episode_id": "ep456",
     "sentiment": "positive",
     "relationships": [
       {"opinion_id": "op124", "type": "supports"},
       {"opinion_id": "op125", "type": "contradicts"}
     ],
     "evolution_chain": ["op121", "op122", "op123"],
     "merged_opinions": ["op127", "op128"],
     "speaker_stance_history": [
       {"speaker": "John Doe", "previous_stance": "neutral", "current_stance": "supportive"}
     ]
   }
   ```

## Persistence Layer

The system uses a flexible repository pattern for data persistence:

- **JsonFileRepository**: Stores data in JSON files for simplicity and portability
- **DatabaseRepository**: (Future) Will support structured database storage
- **Opinion Repository**: Manages opinion objects and their relationships
- **Episode Repository**: Handles podcast episode metadata and references

## Checkpoint System

The checkpoint system is a critical component enabling robust, resumable processing:

- **Checkpoint Data Structure**:
  ```json
  {
    "last_updated": "2023-07-15T14:30:00Z",
    "processed_episodes": {
      "ep123": {
        "completed": true,
        "stages": {
          "raw_extraction": true,
          "categorization": true,
          "relationship_analysis": true,
          "merging": false,
          "evolution": false,
          "speaker_tracking": false
        },
        "opinion_count": 15
      }
    },
    "stage_progress": {
      "raw_extraction": 10,
      "categorization": 8,
      "relationship_analysis": 5,
      "merging": 0,
      "evolution": 0,
      "speaker_tracking": 0
    },
    "last_completed_stage": 2
  }
  ```

- **Stage Completion Tracking**: Records which stages are complete for each episode
- **Episode-Level Processing**: Tracks individual episode progress independently
- **Intermediate Data Persistence**: Preserves processed data at each stage
- **Error Recovery**: Enables resumption after failures or interruptions
- **Progress Reporting**: Provides detailed statistics on extraction progress

## Service Configuration and Extensibility

The system is designed for modularity and extensibility:

- LLM providers can be easily switched (OpenAI, Deepseek, etc.)
- Processing parameters are configurable via command-line arguments
- Each service can be extended or replaced with alternative implementations
- New pipeline stages can be added with minimal changes to existing code

## Error Handling and Logging

The system includes comprehensive error handling and logging:

- Each service includes robust error handling with specific error types
- Detailed logging at each processing stage
- Error recovery through checkpoint system
- Process statistics and metrics collection

## Future Architecture Extensions

Planned enhancements to the architecture include:

1. **Distributed Processing**: Support for parallel processing of episodes
2. **Real-time Opinion Tracking**: Streaming updates for new episode content
3. **API Layer**: RESTful API for integration with other systems
4. **Visualization Components**: Interactive dashboards for opinion analysis
5. **Extended NLP Capabilities**: Enhanced entity recognition and sentiment analysis

## Design Principles

The system architecture adheres to several key design principles:

1. **Separation of Concerns**: Each service has a single, well-defined responsibility
2. **Open/Closed Principle**: Services are open for extension but closed for modification
3. **Dependency Inversion**: High-level modules depend on abstractions, not details
4. **Single Responsibility**: Each class has a single reason to change
5. **Interface Segregation**: Clients depend only on the interfaces they use

## Execution Flow

1. **Initialization**: Load episodes and configure services
2. **Checkpoint Loading**: Check for existing checkpoint data
3. **Pipeline Execution**: Process each episode through the pipeline stages
4. **Progress Tracking**: Update checkpoint data after each stage
5. **Result Storage**: Save processed opinions and metadata
6. **Statistics Generation**: Compile extraction statistics

This modular architecture enables robust opinion extraction and analysis while supporting interruptible, resumable processing—essential for handling large podcast libraries efficiently. 