# Opinion Extraction Stage Architecture

## Overview

The Opinion Extraction stage is the final stage in the AllInVault podcast processing pipeline. This stage processes identified speakers and their utterances to extract opinions, track them across episodes, and monitor how they evolve over time.

## Workflow

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│ Load Episodes   ├────►│ Sort by Date    ├────►│Process Episodes ├────►│ Save Opinions   │
│                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                                                        ▼
                                          ┌─────────────────────────────┐
                                          │                             │
                                          │ For Each Episode            │
                                          │                             │
                                          └───────────────┬─────────────┘
                                                          │
                                                          ▼
                        ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
                        │                 │     │                 │     │                 │
                        │ Load Transcript ├────►│ Format for LLM  ├────►│ Get Past        │
                        │                 │     │                 │     │ Opinions        │
                        └─────────────────┘     └─────────────────┘     └────────┬────────┘
                                                                                  │
                                                                                  ▼
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│                 │     │                 │     │                 │     │                 │
│ Update Episode  │◄────┤ Create Opinion  │◄────┤ Process LLM     │◄────┤ Call LLM        │
│ Metadata        │     │ Objects         │     │ Response        │     │                 │
│                 │     │                 │     │                 │     │                 │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

## Key Components

### Input Data
- Podcast episodes with completed transcripts and speaker identification
- Repository of existing opinions (initially empty)

### Output Data
- Structured opinions linked to speakers, episodes, and related opinions
- Updated episode metadata with references to extracted opinions
- Opinions JSON file with full opinion data

## Detailed Process Flow

### 1. Stage Initialization
```python
# Initialize opinion extractor with LLM service
opinion_extractor = OpinionExtractorService(
    use_llm=True,
    llm_provider="openai",
    llm_model="gpt-4o"
)
```

### 2. Episode Selection
- Episodes with transcripts are identified
- Episodes are sorted chronologically (by published_at date)
- Only FULL episodes with speaker identification are processed

### 3. Transcript Processing Per Episode
For each episode:
1. Load the transcript JSON file
2. Extract utterances with speaker IDs and timestamps
3. Format transcript text for LLM processing:
   ```
   [12.5] Speaker 0: This inflation is transitory and will resolve by end of year.
   [25.7] Speaker 1: I disagree. Supply chain issues will persist.
   ```

### 4. Context Collection
1. Load all previously extracted opinions from repository
2. Format opinions for LLM context:
   ```
   ID: 3fa85f64-5717-4562-b3fc-2c963f66afa6
   Title: Inflation is Transitory
   Speaker: Chamath Palihapitiya
   Category: Economics
   Content: This inflation is transitory and will resolve by end of year.
   ```

### 5. LLM Prompt Construction
Construct a detailed prompt combining:
- Episode metadata (title, date, description)
- Speaker identification data
- Formatted transcript
- Previously identified opinions
- Detailed instructions for opinion extraction

### 6. LLM Processing
Call OpenAI GPT-4o with the constructed prompt, requesting:
- Opinion identification
- Title and description generation
- Speaker and timestamp extraction
- Category assignment
- Keyword extraction
- Sentiment analysis
- Relationship identification to previous opinions

### 7. Response Processing
Parse the LLM JSON response into structured Opinion objects:
```python
# Process each opinion in the LLM response
for raw_op in extracted_opinions.get("opinions", []):
    # Generate unique ID
    opinion_id = str(uuid.uuid4())
    
    # Create Opinion object with metadata
    opinion = Opinion(
        id=opinion_id,
        title=raw_op.get("title"),
        description=raw_op.get("description"),
        content=raw_op.get("content"),
        speaker_id=raw_op.get("speaker_id"),
        speaker_name=speaker_name,
        episode_id=episode.video_id,
        episode_title=episode.title,
        start_time=raw_op.get("start_time"),
        end_time=raw_op.get("end_time"),
        date=episode_date,
        keywords=raw_op.get("keywords", []),
        sentiment=raw_op.get("sentiment"),
        confidence=raw_op.get("confidence", 0.7),
        category=raw_op.get("category"),
        related_opinions=valid_related_ids,
        evolution_notes=raw_op.get("evolution_notes")
    )
```

### 8. Opinion Relationship Management
- Link new opinions to related existing opinions
- Ensure bidirectional relationships
- Track opinion evolution with notes

### 9. Storage and Metadata Update
1. Save opinions to repository
2. Update episode metadata with opinion references:
   ```python
   # Add opinion IDs to episode metadata
   for opinion in opinions:
       episode.metadata["opinions"][opinion.id] = {
           "title": opinion.title,
           "speaker_id": opinion.speaker_id,
           "speaker_name": opinion.speaker_name,
           "category": opinion.category,
           "start_time": opinion.start_time,
           "end_time": opinion.end_time
       }
   ```

### 10. Iterative Processing
- Process the next episode with all previously gathered opinions as context
- Continue until all episodes are processed

## Opinion Tracking Logic

### Identification Criteria
The LLM is instructed to identify opinions based on:
- Assertions that express subjective views
- Predictions about future events
- Strong judgments or assessments
- Policy recommendations or normative statements
- Significant analytical conclusions

### Categorization System
- Categories are not predefined but emergent
- The LLM assigns categories based on content
- Common categories include politics, economics, technology, science, etc.
- Categories become more refined as more episodes are processed

### Relationship Determination
Opinions are related when they:
1. Address the same topic or subject
2. Represent an evolution or change in a previously stated view
3. Directly reference or respond to a prior opinion
4. Contradict or support a previous opinion
5. Elaborate on or provide additional context for a prior opinion

## LLM Prompt Design

The prompt is designed with several key sections:
1. **Task Definition**: Clear explanation of the opinion extraction task
2. **Episode Context**: Metadata about the current episode
3. **Speaker Information**: List of identified speakers
4. **Previously Identified Opinions**: Formatted list of existing opinions
5. **Transcript**: The full transcript with timestamps and speaker IDs
6. **Output Format**: Strict JSON schema for response
7. **Special Instructions**: Guidelines for what constitutes an opinion

## Technical Implementation Details

### Opinion Identity and Tracking
- Each opinion has a UUID
- Opinions maintain a list of related opinion IDs
- Evolution notes describe the relationship between opinions

### Data Structures
1. **Opinion Object**: Core data structure for opinions
2. **OpinionRepository**: Manages persistence and relationships
3. **Formatted Transcript**: Timestamped utterances with speaker IDs
4. **LLM Response**: Structured JSON with extracted opinions

### Processing Algorithm
```
Algorithm: ProcessEpisodes
Input: episodes (list of PodcastEpisode), transcripts_dir (string)
Output: updated_episodes (list of PodcastEpisode with opinion metadata)

1. Sort episodes chronologically by published_at date
2. existing_opinions = Load all opinions from repository
3. For each episode in sorted_episodes:
   a. Skip if no transcript available
   b. formatted_transcript = Format transcript for LLM
   c. prompt = Construct detailed prompt with context
   d. llm_response = Call LLM with prompt
   e. new_opinions = Process LLM response into Opinion objects
   f. Link new_opinions with related existing_opinions
   g. Save new_opinions to repository
   h. Update episode metadata with opinion references
   i. Add new_opinions to existing_opinions for next iteration
4. Return updated_episodes
```

## Running the Opinion Extraction Stage

To run the opinion extraction stage, use the following command:

```bash
python -m src.cli.pipeline_cmd --stages EXTRACT_OPINIONS
```

For a specific episode:

```bash
python -m src.cli.pipeline_cmd --stages EXTRACT_OPINIONS --episodes VIDEO_ID
```

## Opinion Model Structure

The Opinion model contains the following fields:

```python
@dataclass
class Opinion:
    id: str                      # Unique identifier for the opinion
    title: str                   # Short title/summary of the opinion
    description: str             # Longer description of the opinion
    content: str                 # The actual text of the opinion as expressed
    
    # Speaker information
    speaker_id: str              # ID of the speaker expressing the opinion
    speaker_name: str            # Name of the speaker
    
    # Episode information
    episode_id: str              # ID of the episode where the opinion was expressed
    episode_title: str           # Title of the episode
    
    # Timestamps
    start_time: float            # Start timestamp in seconds
    end_time: float              # End timestamp in seconds
    date: datetime               # Date of the episode
    
    # Metadata
    keywords: List[str]          # Keywords associated with this opinion
    sentiment: Optional[float]   # Sentiment score of the opinion (-1 to 1)
    confidence: float            # Confidence score for opinion detection
    category: Optional[str]      # Category or topic of the opinion
    
    # Tracking over time
    related_opinions: List[str]  # IDs of related opinions
    evolution_notes: Optional[str] # Notes on how this opinion has evolved
    
    # Additional metadata
    metadata: Dict[str, Any]     # Any additional metadata
```

## Example Output

An example of extracted opinion from the opinions.json file:

```json
{
  "opinions": [
    {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "title": "Fed Rate Cuts Will Be Limited in 2024",
      "description": "Chamath believes the Federal Reserve will make fewer interest rate cuts than the market expects in 2024 due to persistent inflation concerns.",
      "content": "I think the Fed is going to be much more conservative with rate cuts than the market is pricing in. We're not going to see six cuts in 2024, maybe two or three at most.",
      "speaker_id": "0",
      "speaker_name": "Chamath Palihapitiya",
      "episode_id": "abcdef123456",
      "episode_title": "E123: Market Outlook for 2024",
      "start_time": 1423.5,
      "end_time": 1445.2,
      "date": "2023-12-15T00:00:00",
      "keywords": ["Federal Reserve", "interest rates", "inflation", "monetary policy", "rate cuts"],
      "sentiment": -0.2,
      "confidence": 0.85,
      "category": "Economics",
      "related_opinions": ["5db85f64-5717-4562-b3fc-2c963f66abb3"],
      "evolution_notes": "This represents a shift from Chamath's previous position in episode E110 where he predicted more aggressive rate cuts by mid-2024.",
      "metadata": {
        "episode_published_at": "2023-12-15T14:30:00Z",
        "extraction_date": "2024-01-10T12:34:56.789Z"
      }
    }
  ]
}
```

## Implementation Notes

1. **Performance Considerations**:
   - Processing full episode transcripts can be resource-intensive
   - The LLM prompt can become very large as more opinions are accumulated
   - Consider limiting context size for very large opinion collections

2. **Error Handling**:
   - The system gracefully handles failures in opinion extraction
   - If the LLM returns invalid JSON, the system attempts to recover
   - Episodes with failed extraction are marked but do not halt the pipeline

3. **Extensibility**:
   - The system can be extended to use different LLM providers
   - The opinion model can be enhanced with additional fields
   - New relationship types can be added to track different opinion connections 