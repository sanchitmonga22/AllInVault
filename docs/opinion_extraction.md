# Opinion Evolution Tracking System

## Overview

The Opinion Evolution Tracking system is a sophisticated pipeline that processes podcast episodes to extract, categorize, and track opinions expressed by speakers over time. The system creates rich interconnections between opinions, revealing how they evolve across episodes and identifying relationships between different viewpoints.

## Pipeline Stages

The opinion extraction process follows a sequential multi-stage pipeline:

| Stage | Name | Description |
|-------|------|-------------|
| 1️⃣ | **Raw Extraction** | Extract initial opinions from episode transcripts using LLM |
| 2️⃣ | **Categorization** | Group and standardize opinions by category |
| 3️⃣ | **Relationship Analysis** | Identify semantic relationships between opinions |
| 4️⃣ | **Opinion Merging** | Consolidate similar opinions while preserving history |
| 5️⃣ | **Evolution Detection** | Build chronological chains showing opinion development |
| 6️⃣ | **Speaker Tracking** | Track speaker stance changes and detect contradictions |

Each stage is checkpoint-enabled for resumable processing.

## Pipeline Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│ Load Episodes   ├────►│ Extract Raw     ├────►│ Categorize      ├────►│ Analyze         │
│ & Raw Opinions  │     │ Opinions        │     │ Opinions        │     │ Relationships   │
│                 │     │                 │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │                       │
         ▼                       ▼                       ▼                       ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐            ┌─────────┐     
    │Checkpoint│            │Checkpoint│            │Checkpoint│            │Checkpoint│     
    └─────────┘            └─────────┘            └─────────┘            └─────────┘     
                                                                              │
                                                                              │
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐          │
│                 │     │                 │     │                 │          │
│ Save Final      │◄────┤ Track Speaker   │◄────┤ Build Evolution │◄─────────┘
│ Opinions        │     │ Journeys        │     │ Chains          │
│                 │     │                 │     │                 │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         ▼                       ▼                       ▼
    ┌─────────┐            ┌─────────┐            ┌─────────┐
    │Checkpoint│            │Checkpoint│            │Checkpoint│
    └─────────┘            └─────────┘            └─────────┘
```

## Stage Details

### 1️⃣ Raw Opinion Extraction

**Input**: Podcast episode transcript  
**Process**:
- Parse transcript to identify speakers and timestamps
- Send transcript chunks to LLM for opinion extraction
- Format responses into structured raw opinion objects

**Output**: List of raw opinion objects:
```json
{
  "id": "unique-opinion-id",
  "title": "Concise opinion title",
  "description": "Detailed opinion description",
  "content": "Direct quote or paraphrase",
  "speakers": [
    {
      "speaker_id": "speaker1",
      "speaker_name": "Speaker Name",
      "stance": "support/oppose/neutral",
      "reasoning": "Reasoning for their stance",
      "start_time": 123.45,
      "end_time": 167.89
    }
  ],
  "category": "Category name",
  "keywords": ["keyword1", "keyword2"],
  "episode_id": "episode-123"
}
```

### 2️⃣ Opinion Categorization

**Input**: Raw opinion objects  
**Process**:
- Map custom categories to standardized ones
- Group opinions by category
- Ensure all categories exist in the repository

**Output**: Dictionary of opinions grouped by category

### 3️⃣ Relationship Analysis

**Input**: Categorized opinions  
**Process**:
- Generate semantic embeddings for opinions
- Calculate similarity scores using multiple vectors:
  - Content similarity (semantic meaning)
  - Speaker stance patterns
  - Temporal context
  - Keyword overlap
- Classify relationships as:
  - SAME_OPINION: Essentially the same opinion
  - RELATED: Connected but distinct opinions
  - EVOLUTION: One opinion evolved from another
  - CONTRADICTION: Opinions that contradict each other

**Output**: Relationship data with connections between opinions

### 4️⃣ Opinion Merging

**Input**: Raw opinions and relationship data  
**Process**:
- Identify clusters of highly similar opinions
- Merge closely related opinions while preserving:
  - Original appearance contexts
  - Speaker stances
  - Episode metadata
- Resolve conflicts using configurable strategies

**Output**: Merged opinion objects with consolidated information

### 5️⃣ Evolution Detection

**Input**: Merged opinion objects  
**Process**:
- Sort opinions chronologically
- Identify evolution relationships between opinions
- Construct evolution chains showing opinion development
- Classify evolution types:
  - Refinement: Clarification without changing core position
  - Expansion: Adding new details or broadening scope
  - Contraction: Narrowing focus or scope
  - Pivot: Significant shift in perspective or framing
  - Reversal: Fundamental change in position

**Output**: Evolution chains linking opinions across time

### 6️⃣ Speaker Tracking

**Input**: Merged opinions with evolution data  
**Process**:
- Track each speaker's stance on opinions over time
- Identify stance changes and their reasoning
- Detect contradictions in speaker positions
- Build speaker journey narratives

**Output**: Speaker journey objects showing stance evolution

## Checkpoint System

The system implements a robust checkpoint mechanism that enables resuming interrupted processing:

### Checkpoint Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                         Checkpoint Service                            │
└────────────────────────────────┬─────────────────────────────────────┘
                                │
        ┌─────────────────────┬─┴───────────────────┬─────────────────────┐
        │                     │                     │                     │
        ▼                     ▼                     ▼                     ▼
┌────────────────┐    ┌────────────────┐    ┌────────────────┐    ┌────────────────┐
│                │    │                │    │                │    │                │
│ Stage Tracking │    │Episode Tracking│    │ Raw Opinion    │    │   Statistics   │
│                │    │                │    │   Storage      │    │  Collection    │
│                │    │                │    │                │    │                │
└────────┬───────┘    └────────┬───────┘    └────────┬───────┘    └────────┬───────┘
         │                     │                     │                     │
         └─────────────────────┴─────────────────────┴─────────────────────┘
                                        │
                                        ▼
                         ┌─────────────────────────────┐
                         │                             │
                         │     Persistence Layer       │
                         │     (JSON Storage)          │
                         │                             │
                         └─────────────────────────────┘
```

### Checkpoint Features

1. **Stage Completion Tracking**
   - Records completion status of each pipeline stage
   - Enables skipping already completed stages when resuming

2. **Episode-level Processing**
   - Tracks which episodes have been fully processed
   - Enables selective processing of only new episodes

3. **Intermediate Data Persistence**
   - Saves raw opinions after extraction
   - Preserves progress data at each stage

4. **Error Recovery**
   - Gracefully handles errors at any stage
   - Preserves progress up to the point of failure
   - Enables resuming from the last successful point

### Resuming from Checkpoint

```python
# Initialize with existing checkpoint paths
extraction_service = OpinionExtractionService(
    checkpoint_path="data/checkpoints/extraction_checkpoint.json",
    raw_opinions_path="data/checkpoints/raw_opinions.json"
)

# Resume processing from the last checkpoint
updated_episodes = extraction_service.extract_opinions(
    episodes=episodes_to_process,
    transcripts_dir="data/transcripts",
    resume_from_checkpoint=True
)
```

## Running the Next Stage

If you already have raw opinions extracted in `raw_opinions.json`, you can continue with the next stage (categorization) using:

```python
from src.services.opinion_extraction import OpinionExtractionService

# Initialize service with your checkpoint paths
service = OpinionExtractionService(
    checkpoint_path="data/checkpoints/extraction_checkpoint.json",
    raw_opinions_path="path/to/raw_opinions.json"
)

# Run the pipeline, which will detect existing raw opinions and continue
results = service.extract_opinions(
    episodes=episodes,
    transcripts_dir="data/transcripts",
    resume_from_checkpoint=True
)
```

This will load your existing raw opinions and continue with categorization, relationship analysis, and subsequent stages.

## Data Models

The system uses a comprehensive set of data models to represent opinions, their relationships, and evolution over time:

### Core Models

- **Opinion**: Central model representing an opinion that can appear across multiple episodes
  - Contains metadata, description, category, and appearances
  - Tracks relationships with other opinions
  - Has evolution chain information

- **OpinionAppearance**: Represents a specific appearance of an opinion in an episode
  - Links to episode metadata
  - Contains speaker stances for this appearance
  - Includes episode-specific content and context

- **SpeakerStance**: Represents a speaker's position on an opinion
  - Tracks support, opposition, or neutrality
  - Includes reasoning behind the stance
  - Contains timing information

### Evolution Models

- **EvolutionChain**: Represents the progression of an opinion over time
  - Contains ordered nodes representing evolution points
  - Tracks pattern classification
  - Provides overall evolution metadata

- **EvolutionNode**: Represents a point in an opinion's evolution
  - Links to specific opinion and episode
  - Classifies the evolution type
  - Contains description of the evolution

- **SpeakerJourney**: Tracks a speaker's stance evolution
  - Contains speaker metadata
  - Maps opinions to journey nodes
  - Provides current stances on all opinions

## Technology Stack

- **Language**: Python 3.9+
- **NLP**: Sentence Transformers, spaCy
- **ML**: PyTorch, scikit-learn
- **LLM**: DeepSeek API, OpenAI API
- **Storage**: JSON files with structured schemas
- **Parallelization**: ThreadPoolExecutor

## How to Run the Next Stage

If you already have raw opinions extracted in `raw_opinions.json`, you can continue with the next stage (categorization) using:

```python
from src.services.opinion_extraction import OpinionExtractionService

# Initialize service with your checkpoint paths
service = OpinionExtractionService(
    checkpoint_path="data/checkpoints/extraction_checkpoint.json",
    raw_opinions_path="data/raw_opinions.json"
)

# Run the pipeline, which will detect existing raw opinions and continue from there
results = service.extract_opinions(
    episodes=episodes,
    transcripts_dir="data/transcripts",
    resume_from_checkpoint=True
)
```

This will load your existing raw opinions and continue with categorization, relationship analysis, and subsequent stages while maintaining checkpoints throughout the process. 