# Opinion Evolution Tracking System Architecture

## Overview

The Opinion Evolution Tracking system processes podcast episodes to extract, categorize, and track opinions expressed by speakers across multiple episodes. This comprehensive system identifies relationships between opinions, tracks their evolution, and provides insight into how opinions change over time.

## Modular Multi-Stage Architecture

The opinion extraction process uses a fully modular multi-stage approach to address context size limitations and improve accuracy:

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│ Load Episodes   ├────►│ Sort by Date    ├────►│ Extract Raw     ├────►│ Categorize      │
│                 │     │                 │     │ Opinions        │     │ Opinions        │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                                                                                 │
                                                                                 ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│ Save Final      │◄────┤ Process         │◄────┤ Establish       │◄────┤ Group by        │
│ Opinions        │     │ Relationships   │     │ Relationships   │     │ Category        │
│                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

## System Architecture Diagram

```
┌───────────────────────────────────────────────────────────────────────────────────────┐
│                           Opinion Evolution Tracking System                            │
└────────────────────────────────────────┬──────────────────────────────────────────────┘
                                         │
                   ┌───────────────────────────────────┬─────────────────────────────────┐
                   │         DATA PREPARATION          │        RELATIONSHIP ANALYSIS    │
                   │                                   │                                 │
                   │  ┌─────────────┐ ┌─────────────┐  │  ┌─────────────┐  ┌───────────┐ │
                   │  │             │ │             │  │  │             │  │           │ │
                   │  │ Raw Opinion │ │Categorize & │  │  │ Semantic    │  │Relationship│ │
                   │  │ Extraction  ├─►Standardize  ├──┼──►│ Similarity  ├──►Detection  │ │
                   │  │             │ │             │  │  │ Analysis    │  │           │ │
                   │  └─────────────┘ └─────────────┘  │  └─────────────┘  └─────┬─────┘ │
                   │                                   │                          │       │
                   └───────────────────────────────────┘                          │       │
                                                                                  │       │
                                                                                  ▼       │
                   ┌───────────────────────────────────┐                  ┌─────────────┐ │
                   │         EVOLUTION TRACKING        │                  │             │ │
                   │                                   │                  │ Opinion      │ │
                   │  ┌─────────────┐ ┌─────────────┐  │                  │ Merger      │ │
                   │  │             │ │             │  │                  │ Service     │ │
                   │  │ Evolution   │ │Speaker      │  │                  │             │ │
                   │  │ Chain       │◄┤Stance       │◄─┼──────────────────┘             │ │
                   │  │ Building    │ │Tracking     │  │                                  │
                   │  └─────────────┘ └─────────────┘  │                                  │
                   │                                   │                                  │
                   └───────────────────────────────────┘                                  │
```

## Modular Service Architecture

The opinion extraction system is structured as a set of modular, specialized services:

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
│                                                  ┌─────────────────────┐    │
│                                                  │                     │    │
│                                                  │ Merger Service      │    │
│                                                  │                     │    │
│                                                  └──────────┬──────────┘    │
│                                                             │               │
└─────────────────────────────────────────────────────────────┼───────────────┘
                                                             │
                                                             ▼
                                          ┌───────────────────────────────────┐
                                          │                                   │
                                          │ Evolution Detection Service       │
                                          │                                   │
                                          └─────────────────┬─────────────────┘
                                                           │
                                                           ▼
                                          ┌───────────────────────────────────┐
                                          │                                   │
                                          │ Speaker Tracking Service          │
                                          │                                   │
                                          └───────────────────────────────────┘
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

5. **Evolution Detection Service**
   - Creates evolution chains from related opinions
   - Identifies evolution types (refinement, pivot, expansion, contraction)
   - Generates descriptions of how opinions evolve over time
   - Builds chronological timelines of opinion development

6. **Speaker Tracking Service**
   - Tracks speaker stance evolution across episodes
   - Identifies changes in speaker positions on specific opinions
   - Builds comprehensive speaker journeys
   - Detects contradictions in speaker positions

## Enhanced Opinion Data Models

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

## Advanced Multi-Vector Opinion Merging Algorithm

The enhanced algorithm for merging similar opinions uses a sophisticated multi-vector approach for improved accuracy:

### Merging Process

1. **Category-based Grouping**: Group opinions by category to reduce computational complexity
2. **Multi-faceted Embeddings**: Generate multiple embedding vectors capturing different aspects
   - Content embeddings - core meaning of the opinion
   - Context embeddings - surrounding discussion context
   - Speaker vectors - speaker stance relationships
   - Keywords embeddings - key terms and concepts
3. **Hierarchical Clustering**: Apply clustering within each category group
4. **LLM Verification**: Use LLM to verify similarity for borderline cases
5. **Merger Creation**: For each identified cluster, create a merged opinion preserving all history
6. **Evolution Chain Building**: Construct evolution chains from the relationships

### Evolution Detection Process

1. **Chronological Sorting**: Sort all opinions by date of appearance
2. **Evolution Link Analysis**: Analyze relationship links marked as EVOLUTION
3. **Chain Construction**: Build connected chains of evolving opinions
4. **Pattern Classification**: Identify common evolution patterns
5. **Transition Description**: Generate descriptions of each evolution step
6. **Speaker Position Tracking**: Track how each speaker's stance evolves

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

## Benefits of This Architecture

1. **Scalability**: Pipeline stages can be executed independently or in sequence
2. **Flexibility**: Each component can be replaced or extended without affecting others
3. **Maintainability**: Clear separation of concerns makes the codebase easier to maintain
4. **Extensibility**: New features can be added by creating new pipeline stages
5. **Robustness**: Each stage can handle errors independently, preventing pipeline failure
6. **Comprehensive Tracking**: Complete history of opinions across episodes
7. **Evolution Analysis**: Visibility into how opinions change over time
8. **Speaker Consistency**: Ability to track speaker positions on topics

## Checkpoint Management System

The opinion extraction pipeline implements a robust checkpoint management system that enables resuming interrupted processing:

### CheckpointManager Class
- Tracks processed episodes and completed stages
- Saves progress after each episode to minimize data loss
- Enables resuming from the last processed episode
- Allows targeting specific stages of the pipeline

### Checkpointing Features
- **Episode tracking**: Records each successfully processed episode
- **Stage completion**: Tracks completion status of each pipeline stage
- **Timestamp tracking**: Records when each checkpoint was saved
- **Resumable execution**: Can continue from previous run without duplication
- **Intermediate data persistence**: Saves outputs from each stage for reuse 