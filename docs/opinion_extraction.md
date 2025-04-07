# Opinion Extraction Stage Architecture

## Overview

The Opinion Extraction stage is the final stage in the AllInVault podcast processing pipeline. This stage processes identified speakers and their utterances to extract opinions, track them across episodes, and monitor how they evolve over time.

## Modular Multi-Stage Architecture

The opinion extraction process has been redesigned with a fully modular multi-stage approach to address context size limitations and improve accuracy:

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

## Modular Service Architecture

The opinion extraction system has been completely refactored into a set of modular, specialized services:

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
│                                                  └─────────────────────┘    │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 1. Base Opinion Service
- Provides common functionality shared across all opinion services
- Handles transcript loading and text similarity checking
- Implements speaker information extraction

### 2. Raw Extraction Service
- Specializes in extracting initial opinions from a single transcript
- Uses LLM to identify and extract opinions with complete metadata
- Focuses on high-quality extraction without cross-episode context

### 3. Categorization Service
- Ensures consistent categorization of opinions
- Maps non-standard categories to standard ones using LLM when needed
- Creates and manages category entities in the repository

### 4. Relationship Analysis Service
- Analyzes relationships between opinions in the same category
- Supports both LLM-based and heuristic relationship detection
- Establishes various relationship types (same opinion, related, evolution, contradiction)

### 5. Merger Service
- Merges related opinions into unified opinion objects
- Creates structured Opinion objects from processed data
- Handles saving to the opinion repository

### 6. Main Extraction Service
- Orchestrates the entire multi-stage pipeline
- Manages communication between component services
- Provides a simple, unified API for opinion extraction

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

## Key Improvements Over Previous Version

1. **Reduced Context Size**: Each component handles a specific task with focused context
2. **Better Categorization**: Improved category standardization and mapping
3. **Enhanced Relationship Detection**: More accurate detection with manageable opinion batches
4. **Complete Speaker Tracking**: Preserves all speaker metadata during merging
5. **Sophisticated Merging**: More intelligent opinion merging that preserves all appearances
6. **Resilient Processing**: Added checkpoint system for robust, resumable operation
7. **LLM Provider Flexibility**: Support for both OpenAI and DeepSeek LLM providers

## Configuration Options

The Opinion Extraction service can be configured with the following parameters:

- `use_llm` (bool): Whether to use LLM for opinion extraction
- `llm_provider` (str): LLM provider ('openai' or 'deepseek')
- `llm_model` (str): Model name for the LLM provider (default: "deepseek-chat")
- `relation_batch_size` (int): Maximum number of opinions to compare in a single relationship analysis
- `max_opinions_per_episode` (int): Maximum number of opinions to extract per episode (default: 15)
- `similarity_threshold` (float): Threshold for opinion similarity to be considered related (default: 0.7)

## Usage Examples

### Processing Multiple Episodes

```python
from src.services.opinion_extraction.extraction_service import OpinionExtractionService

# Initialize the service
extractor = OpinionExtractionService(
    use_llm=True,
    llm_model="deepseek-chat",
    relation_batch_size=20,
    max_opinions_per_episode=15,
    similarity_threshold=0.7
)

# Process episodes
updated_episodes = extractor.extract_opinions(
    episodes=episodes_list,
    transcripts_dir="data/transcripts"
)
```

### Processing a Single Episode

```python
from src.services.opinion_extraction.extraction_service import OpinionExtractionService

# Initialize the service
extractor = OpinionExtractionService(use_llm=True)

# Process a single episode
opinions = extractor.extract_opinions_from_transcript(
    episode=episode,
    transcript_path="data/transcripts/episode123.txt"
)
```

## Multi-Stage Process Flow

### 1. Raw Opinion Extraction
The `RawExtractionService` extracts opinions from each episode individually:

```python
def extract_raw_opinions(self, episode, transcript_path):
    """Extract raw opinions from a transcript without considering previous opinions."""
    # Load the transcript
    transcript_data = self.load_transcript(transcript_path)
    
    # Format for LLM processing
    transcript_text = self._format_transcript_for_llm(transcript_data)
    
    # Extract speaker information
    speakers_info = self._extract_speaker_info(episode)
    
    # Prepare episode metadata
    episode_metadata = {
        "id": episode.video_id,
        "title": episode.title,
        "date": episode.published_at,
        "description": episode.description
    }
    
    # Call LLM to extract opinions
    raw_opinions = self._call_llm_for_raw_extraction(
        episode_metadata=episode_metadata,
        transcript_text=transcript_text,
        speakers_info=speakers_info
    )
    
    # Process and enhance raw opinions
    processed_raw_opinions = self._process_raw_extraction_results(
        raw_opinions=raw_opinions,
        episode=episode
    )
    
    return processed_raw_opinions
```

### 2. Categorization
The `OpinionCategorizationService` categorizes and standardizes opinions:

```python
def categorize_opinions(self, raw_opinions):
    """Categorize raw opinions and group them by standard category."""
    categorized_opinions = {}
    
    # Process each opinion to ensure proper categorization
    for opinion in raw_opinions:
        raw_category = opinion.get("category", "Uncategorized")
        
        # Map to standard category
        standard_category = self._map_to_standard_category(raw_category)
        
        # Update the opinion with the standard category
        opinion["category"] = standard_category
        
        # Add to grouped opinions
        if standard_category not in categorized_opinions:
            categorized_opinions[standard_category] = []
        
        categorized_opinions[standard_category].append(opinion)
    
    return categorized_opinions
```

### 3. Relationship Analysis
The `OpinionRelationshipService` analyzes relationships between opinions:

```python
def analyze_relationships(self, categorized_opinions):
    """Analyze relationships between opinions in the same category."""
    all_relationship_data = []
    
    # Process each category separately
    for category, opinions in categorized_opinions.items():
        # Sort opinions chronologically
        opinions.sort(key=lambda op: op.get("episode_date", datetime.min))
        
        # Process in batches
        for i in range(0, len(opinions), self.relation_batch_size):
            batch = opinions[i:i+self.relation_batch_size]
            relationship_data = self._analyze_opinion_batch(batch, category)
            all_relationship_data.extend(relationship_data)
    
    return all_relationship_data
```

### 4. Opinion Merging
The `OpinionMergerService` processes relationships and merges opinions:

```python
def process_relationships(self, raw_opinions, relationship_data):
    """Process relationship data to merge and link opinions."""
    # Create a map of opinion IDs to their objects
    opinion_map = {op['id']: op for op in raw_opinions}
    
    # Track merged opinions
    merged_map = {}
    
    # Process each relationship
    for relationship in relationship_data:
        source_id = relationship.get('source_id')
        target_id = relationship.get('target_id')
        relation_type = relationship.get('relation_type')
        
        # Handle different relationship types
        if relation_type == RelationshipType.SAME_OPINION:
            # Merge these opinions
            merged_id = self._merge_opinions(
                source=opinion_map[source_id], 
                target=opinion_map[target_id],
                opinion_map=opinion_map,
                merged_map=merged_map
            )
            
            merged_map[source_id] = merged_id
            merged_map[target_id] = merged_id
        
        elif relation_type == RelationshipType.RELATED:
            # Add as related opinions
            self._add_related_opinions(opinion_map[source_id], opinion_map[target_id])
        
        elif relation_type == RelationshipType.EVOLUTION:
            # Add to evolution chain
            self._add_to_evolution_chain(opinion_map[source_id], opinion_map[target_id])
        
        elif relation_type == RelationshipType.CONTRADICTION:
            # Mark contradiction relationship
            self._mark_contradiction(opinion_map[source_id], opinion_map[target_id])
    
    # Filter out merged opinions
    final_opinions = []
    merged_ids = set(merged_map.values())
    
    for opinion_id, opinion in opinion_map.items():
        if opinion_id in merged_ids:
            final_opinions.append(opinion)
        elif opinion_id not in merged_map:
            final_opinions.append(opinion)
    
    return final_opinions
```

### 5. Creating Opinion Objects
Finally, create structured Opinion objects:

```python
def create_opinion_objects(self, final_opinions):
    """Create structured Opinion objects from the processed opinion data."""
    opinion_objects = []
    
    for opinion_data in final_opinions:
        # Create the Opinion object
        opinion = self._create_opinion_object(opinion_data)
        
        if opinion:
            opinion_objects.append(opinion)
    
    return opinion_objects
```

## Enhanced Opinion Model

The system uses a structured data model for opinions:

### Opinion
- Core opinion entity that can appear across multiple episodes
- Tracks relationships, contradictions, and evolution
- Contains metadata like keywords and confidence scores

### OpinionAppearance
- Instance of an opinion's appearance in a specific episode
- Contains all episode-specific data
- Tracks speakers' stances in this particular instance

### SpeakerStance
- Records a speaker's stance on an opinion (support/oppose/neutral)
- Captures timestamps and reasoning
- Enables tracking of individual speaker's positions on opinions

## Runtime Scripts

### Processing All Episodes Chronologically

The `run_opinion_extraction_for_all_episodes.py` script provides a powerful way to process all episodes with full checkpointing and resumable execution:

```bash
python run_opinion_extraction_for_all_episodes.py [--count N] [--delay N] [--stage STAGE]
```

Key features:
- Processes episodes in chronological order (oldest first)
- Saves progress after each episode and stage
- Can be interrupted and resumed without data loss
- Supports running specific stages of the pipeline
- Provides detailed logs of the extraction process
- Handles batching to optimize memory usage

Command-line options:
- `--count N`: Process only the first N episodes (default: all)
- `--delay N`: Add a delay of N seconds between episodes (default: 10)
- `--max-opinions N`: Maximum opinions per episode (default: 15)
- `--relation-batch-size N`: Batch size for relationship analysis (default: 20)
- `--llm-model MODEL`: LLM model to use (default: deepseek-chat)
- `--stage STAGE`: Run only a specific stage (extraction/categorization/relationships/merging/all)
- `--checkpoint-file PATH`: Path to the checkpoint file (default: data/intermediate/checkpoint.json)
- `--start-from ID`: Start processing from a specific episode ID
- `--skip-shorts`: Skip episodes labeled as SHORT
- `--force-continue`: Continue processing even if errors occur with individual episodes

### Processing Sample Episodes

The `run_opinion_extraction_for_first_10.py` script provides a convenient way to run the opinion extraction pipeline on a sample of episodes:

```python
# Initialize the opinion extraction service
opinion_extraction_service = OpinionExtractionService(
    use_llm=True,
    llm_model="deepseek-chat",
    opinions_file_path="data/json/opinions.json",
    categories_file_path="data/json/categories.json",
    relation_batch_size=20,
    max_opinions_per_episode=15,
    similarity_threshold=0.7
)

# Process episodes using the multi-stage approach
updated_episodes = opinion_extraction_service.extract_opinions(
    episodes=episodes_with_transcripts,
    transcripts_dir="data/transcripts"
)
```

## Benefits of the Modular Architecture

1. **Maintainability**: Each component has a single responsibility
2. **Testability**: Services can be tested independently
3. **Flexibility**: Components can be replaced or upgraded individually
4. **Scalability**: Process can be distributed or parallelized by component
5. **Extensibility**: New capabilities can be added by creating additional services
6. **Resilience**: Checkpointing allows resumable operation for long-running processes 