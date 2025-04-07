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

## Configuration Options

The Opinion Extraction service can be configured with the following parameters:

- `use_llm` (bool): Whether to use LLM for opinion extraction
- `llm_provider` (str): LLM provider ('openai' or other supported providers)
- `llm_model` (str): Model name for the LLM provider (default: "gpt-4o")
- `max_context_opinions` (int): Maximum number of previous opinions to include in context (default: 20)
- `max_opinions_per_episode` (int): Maximum number of opinions to extract per episode (default: 15)

## Detailed Process Flow

### 1. Stage Initialization
```python
# Initialize opinion extractor with LLM service
opinion_extractor = OpinionExtractorService(
    use_llm=True,
    llm_provider="openai",
    llm_model="gpt-4o",
    max_opinions_per_episode=15
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
   Evolution: This opinion was later revised in episode E45.
   ```

### 5. LLM Prompt Construction
Construct a detailed prompt combining:
- Episode metadata (title, date, description)
- Speaker identification data
- Formatted transcript
- Previously identified opinions
- Detailed instructions for opinion extraction
- Handling of contradictory opinions
- Maximum opinion limit
- Speaker stance tracking

### 6. LLM Processing
Call OpenAI GPT-4o with the constructed prompt, requesting:
- Opinion identification (limited to max_opinions_per_episode)
- Title and description generation
- Speaker stance and reasoning tracking
- Per-speaker timestamp extraction
- Category assignment
- Keyword extraction
- Sentiment analysis
- Relationship identification to previous opinions
- Contradiction detection
- Cross-episode opinion tracking

### 7. Response Processing
Parse the LLM JSON response into structured Opinion objects:
```python
# Process speakers data
speakers_data = raw_op.get("speakers", [])
speaker_timestamps = {}

for speaker_data in speakers_data:
    speaker_id = speaker_data.get("speaker_id")
    
    # Add speaker timing and stance data
    speaker_timestamps[speaker_id] = {
        "start_time": speaker_data.get("start_time", 0.0),
        "end_time": speaker_data.get("end_time", 0.0),
        "stance": speaker_data.get("stance", "neutral"),
        "reasoning": speaker_data.get("reasoning", ""),
        "episode_id": episode.video_id
    }

# Create Opinion object
opinion = Opinion(
    id=str(uuid.uuid4()),
    title=raw_op.get("title"),
    description=raw_op.get("description"),
    content=raw_op.get("content"),
    speaker_id=primary_speaker_id,
    speaker_name=speaker_name,
    episode_id=episode.video_id,
    episode_title=episode.title,
    start_time=overall_start_time,
    end_time=overall_end_time,
    date=episode_date,
    keywords=raw_op.get("keywords", []),
    sentiment=raw_op.get("sentiment"),
    confidence=raw_op.get("confidence", 0.7),
    category_id=category_id,
    related_opinions=valid_related_ids,
    evolution_notes=raw_op.get("evolution_notes"),
    is_contradiction=raw_op.get("is_contentious", False),
    contradicts_opinion_id=contradicts_opinion_id,
    contradiction_notes=raw_op.get("contradiction_notes"),
    speaker_timestamps=speaker_timestamps,
    appeared_in_episodes=[episode.video_id]
)
```

### 8. Opinion Relationship Management
- Link new opinions to related existing opinions
- Ensure bidirectional relationships
- Track opinion evolution with notes
- Track contradictions between opinions
- Track cross-episode appearances of opinions

### 9. Storage and Metadata Update
1. Save opinions to repository
2. Update episode metadata with opinion references
3. Record per-speaker stances and timestamps
4. Track cross-episode opinion appearances

### 10. Cross-Episode Opinion Processing
- Identify when opinions reappear in subsequent episodes
- Update original opinions with cross-episode references
- Track how opinions evolve across episodes
- Record speaker stances across different episodes

## Enhanced Opinion Model

The Opinion model has been enhanced with several new fields:

### Contradiction Tracking
```python
# Contradiction and agreement tracking
is_contradiction: bool = False  # Whether this opinion contradicts another
contradicts_opinion_id: Optional[str] = None  # ID of the contradicted opinion
contradiction_notes: Optional[str] = None  # Notes about the contradiction
```

### Per-Speaker Timing and Stances
```python
# Per-speaker timestamps and positions
speaker_timestamps: Dict[str, Dict[str, Any]] = field(default_factory=dict)
# Map of speaker_id -> {start_time, end_time, stance, reasoning, episode_id}
```

### Cross-Episode Tracking
```python
# Cross-episode tracking
appeared_in_episodes: List[str] = field(default_factory=list)
# List of episode IDs where this opinion appeared
```

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
- New categories can be dynamically suggested by the LLM

### Stance and Contradiction Handling
Opinions are analyzed for different stances:
1. **Support**: Speaker agrees with the opinion
2. **Oppose**: Speaker disagrees with the opinion
3. **Neutral**: Speaker discusses but doesn't clearly agree or disagree
4. **Contentious**: Multiple speakers express conflicting stances

When contradictions are identified, the system:
1. Records which opinion is being contradicted
2. Notes the reasoning behind each speaker's stance
3. Tracks the exact timing when each speaker discusses the opinion
4. Provides detailed contradiction notes explaining the disagreement

### Cross-Episode Opinion Tracking
When an opinion appears across multiple episodes:
1. The original opinion is updated with references to all episodes
2. Evolution notes track how the opinion changes over time
3. Speaker stances are recorded per episode
4. Timestamps are maintained separately for each episode

## LLM Prompt Design

The prompt is designed with several key sections:
1. **Task Definition**: Clear explanation of the opinion extraction task
2. **Episode Context**: Metadata about the current episode
3. **Speaker Information**: List of identified speakers
4. **Previously Identified Opinions**: Formatted list of existing opinions
5. **Transcript**: The full transcript with timestamps and speaker IDs
6. **Output Format**: Strict JSON schema for response
7. **Special Instructions**:
   - Limit on number of opinions to extract
   - Guidelines for handling contradictions
   - Instructions for tracking per-speaker stances
   - Cross-episode opinion identification

## Opinion Statistics

The system tracks comprehensive statistics about extracted opinions:
1. **Total Opinions**: Count of all extracted opinions
2. **Evolution Tracking**: Opinions with evolution notes
3. **Related Opinions**: Opinions linked to other opinions
4. **Multi-Speaker Opinions**: Opinions discussed by multiple speakers
5. **Contradictions**: Opinions that contradict other opinions
6. **Contentious Opinions**: Opinions with disagreement among speakers
7. **Cross-Episode Opinions**: Opinions that appear in multiple episodes
8. **Stance Distribution**: Count of support/oppose/neutral stances
9. **Category Distribution**: Opinions by category
10. **Speaker Distribution**: Opinions by speaker
11. **Episode Distribution**: Opinions by episode

## Example LLM Response

```json
{
  "opinions": [
    {
      "title": "Fed Rate Cuts Will Be Limited in 2024",
      "description": "Views on how aggressively the Federal Reserve will cut interest rates in 2024.",
      "content": "The Federal Reserve's approach to interest rate cuts in 2024 is likely to be more conservative than market expectations.",
      "speakers": [
        {
          "speaker_id": "0",
          "stance": "support",
          "reasoning": "Believes inflation will remain persistent, limiting the Fed's ability to cut rates aggressively",
          "start_time": 1423.5,
          "end_time": 1445.2
        },
        {
          "speaker_id": "1",
          "stance": "oppose",
          "reasoning": "Expects significant economic slowdown forcing the Fed to cut rates more rapidly",
          "start_time": 1450.8,
          "end_time": 1472.3
        }
      ],
      "primary_speaker_id": "0",
      "category": "Economics",
      "keywords": ["Federal Reserve", "interest rates", "inflation", "monetary policy"],
      "sentiment": -0.2,
      "confidence": 0.85,
      "related_opinion_ids": ["5db85f64-5717-4562-b3fc-2c963f66abb3"],
      "evolution_notes": "This represents a shift from Chamath's previous position in episode E110 where he predicted more aggressive rate cuts by mid-2024.",
      "is_contentious": true,
      "contradicts_opinion_id": null,
      "contradiction_notes": "Speakers disagree on the pace of rate cuts due to different views on inflation persistence"
    }
  ],
  "new_categories": [],
  "cross_episode_opinions": [
    {
      "opinion_id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "evolution_notes": "The speaker now expresses less certainty about this position",
      "speakers": [
        {
          "speaker_id": "0",
          "stance": "neutral",
          "reasoning": "Now hedging predictions due to uncertain economic data",
          "start_time": 1522.7,
          "end_time": 1535.4
        }
      ]
    }
  ]
}
```

## Example Opinion Object

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Fed Rate Cuts Will Be Limited in 2024",
  "description": "Chamath believes the Federal Reserve will make fewer interest rate cuts than the market expects in 2024 due to persistent inflation concerns.",
  "content": "I think the Fed is going to be much more conservative with rate cuts than the market is pricing in. We're not going to see six cuts in 2024, maybe two or three at most.",
  "speaker_id": "0",
  "speaker_name": "Chamath Palihapitiya, David Sacks",
  "episode_id": "abcdef123456",
  "episode_title": "E123: Market Outlook for 2024",
  "start_time": 1423.5,
  "end_time": 1472.3,
  "date": "2023-12-15T00:00:00",
  "keywords": ["Federal Reserve", "interest rates", "inflation", "monetary policy", "rate cuts"],
  "sentiment": -0.2,
  "confidence": 0.85,
  "category_id": "economics",
  "related_opinions": ["5db85f64-5717-4562-b3fc-2c963f66abb3"],
  "evolution_notes": "This represents a shift from Chamath's previous position in episode E110 where he predicted more aggressive rate cuts by mid-2024.",
  "is_contradiction": false,
  "contradicts_opinion_id": null,
  "contradiction_notes": null,
  "appeared_in_episodes": ["abcdef123456", "ghijkl789012"],
  "speaker_timestamps": {
    "0": {
      "start_time": 1423.5,
      "end_time": 1445.2,
      "stance": "support",
      "reasoning": "Believes inflation will remain persistent, limiting the Fed's ability to cut rates aggressively",
      "episode_id": "abcdef123456"
    },
    "1": {
      "start_time": 1450.8,
      "end_time": 1472.3,
      "stance": "oppose",
      "reasoning": "Expects significant economic slowdown forcing the Fed to cut rates more rapidly",
      "episode_id": "abcdef123456"
    }
  },
  "metadata": {
    "episode_published_at": "2023-12-15T14:30:00Z",
    "extraction_date": "2024-01-10T12:34:56.789Z",
    "is_multi_speaker": true,
    "all_speaker_ids": ["0", "1"]
  }
}
```

## Implementation Notes

1. **Performance Considerations**:
   - Processing full episode transcripts can be resource-intensive
   - The LLM prompt can become very large as more opinions are accumulated
   - Consider limiting context size for very large opinion collections
   - The max_opinions_per_episode setting can be adjusted based on episode length

2. **Error Handling**:
   - The system gracefully handles failures in opinion extraction
   - If the LLM returns invalid JSON, the system attempts to recover
   - Episodes with failed extraction are marked but do not halt the pipeline
   - Rate limit handling includes automatic retries with exponential backoff

3. **Extensibility**:
   - The system can be extended to use different LLM providers
   - The opinion model can be enhanced with additional fields
   - New relationship types can be added to track different opinion connections
   - The max_opinions_per_episode setting is configurable 