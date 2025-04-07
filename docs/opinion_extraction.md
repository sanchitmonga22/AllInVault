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
   Speakers: Chamath Palihapitiya (support), David Sacks (oppose)
   Category: Economics
   Description: Views on whether current inflation is temporary or persistent.
   Evolution Notes: This opinion has evolved over time from strong conviction to uncertainty.
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
- Relationship identification to previous opinions
- Contradiction detection
- Cross-episode opinion tracking

### 7. Response Processing
Parse the LLM JSON response into structured Opinion objects:
```python
# Process speakers data from LLM response
speakers_info = opinion_data.get("speakers", [])
speakers = []

for speaker_data in speaker_info:
    speaker_id = str(speaker_data.get("speaker_id", "unknown"))
    speaker_name = speaker_data.get("speaker_name", f"Speaker {speaker_id}")
    
    # Create SpeakerStance object
    speaker = SpeakerStance(
        speaker_id=speaker_id,
        speaker_name=speaker_name,
        stance=speaker_data.get("stance", "support"),
        reasoning=speaker_data.get("reasoning"),
        start_time=speaker_data.get("start_time"),
        end_time=speaker_data.get("end_time")
    )
    speakers.append(speaker)

# Create the episode appearance
appearance = OpinionAppearance(
    episode_id=episode.video_id,
    episode_title=episode.title,
    date=episode.published_at,
    speakers=speakers,
    content=content
)

# Create a new opinion or update an existing one
if matched_opinion:
    # Update existing opinion with this new appearance
    matched_opinion.add_appearance(appearance)
else:
    # Create new opinion
    new_opinion = Opinion(
        id=str(uuid.uuid4()),
        title=title,
        description=description,
        category_id=category.id,
        # Other fields...
    )
    # Add the appearance
    new_opinion.add_appearance(appearance)
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

## Enhanced Opinion Model Structure

### Core Models

The opinion tracking system has been redesigned with three core models:

#### 1. Opinion
```python
@dataclass
class Opinion:
    """Model representing a unique opinion that can appear across multiple episodes."""
    
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    title: str = ""  # Short title/summary of the opinion
    description: str = ""  # Longer description of the opinion
    category_id: Optional[str] = None  # ID of the category for this opinion
    
    # Evolution tracking
    related_opinions: List[str] = field(default_factory=list)  # IDs of related opinions
    evolution_notes: Optional[str] = None  # Overall notes on how this opinion has evolved
    evolution_chain: List[str] = field(default_factory=list)  # Chronological chain of opinion IDs
    
    # Contradiction tracking
    is_contradiction: bool = False  # Whether this opinion contradicts another opinion
    contradicts_opinion_id: Optional[str] = None  # ID of the opinion this contradicts
    contradiction_notes: Optional[str] = None  # Notes about the contradiction
    
    # Episode appearances
    appearances: List[OpinionAppearance] = field(default_factory=list)
    
    # Additional metadata
    keywords: List[str] = field(default_factory=list)  # Keywords associated with this opinion
    confidence: float = 0.0  # Confidence score for opinion detection
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### 2. OpinionAppearance
```python
@dataclass
class OpinionAppearance:
    """Model representing an appearance of an opinion in a specific episode."""
    
    episode_id: str  # ID of the episode
    episode_title: str  # Title of the episode
    date: datetime  # Date of the episode
    speakers: List[SpeakerStance] = field(default_factory=list)  # Speakers discussing this opinion
    content: Optional[str] = None  # Actual content from this episode
    context_notes: Optional[str] = None  # Context notes for this appearance
    evolution_notes_for_episode: Optional[str] = None  # Evolution notes specific to this episode
```

#### 3. SpeakerStance
```python
@dataclass
class SpeakerStance:
    """Model representing a speaker's stance on an opinion in a specific episode."""
    
    speaker_id: str  # ID of the speaker
    speaker_name: str  # Name of the speaker
    stance: str = "support"  # support, oppose, neutral
    reasoning: Optional[str] = None  # Why they have this stance
    start_time: Optional[float] = None  # When they start discussing this opinion
    end_time: Optional[float] = None  # When they finish discussing this opinion
```

### Key Features of the New Model

1. **Separation of Concerns**:
   - `Opinion` represents the core opinion concept
   - `OpinionAppearance` represents when/where the opinion was expressed
   - `SpeakerStance` represents who expressed it and how

2. **Cross-Episode Tracking**:
   - Each opinion can have multiple appearances across different episodes
   - Appearances are chronologically sorted by episode date
   - Evolution notes track changes over time

3. **Multi-Speaker Support**:
   - Multiple speakers can comment on the same opinion
   - Each speaker's stance (support/oppose/neutral) is tracked
   - Contentious opinions (with disagreement) are easily identifiable

4. **Stance Evolution Tracking**:
   - Track how a speaker's stance on an opinion changes over time
   - Record reasoning for each stance
   - Identify when speakers change their position

## Opinion Tracking Logic

### Opinion Identification Across Episodes

When processing a new episode, the system:

1. Extracts opinions from the transcript
2. For each extracted opinion:
   - Checks if it matches an existing opinion by comparing title, description, and category
   - If a match is found, adds a new appearance to the existing opinion
   - If no match is found, creates a new opinion

### Speaker Stance Tracking

The system tracks the stance of each speaker on each opinion:

1. **Support**: Speaker agrees with the opinion
2. **Oppose**: Speaker disagrees with the opinion
3. **Neutral**: Speaker discusses but doesn't clearly agree or disagree

The system can identify contentious opinions by detecting when:
- Different speakers have opposing stances on the same opinion
- The same speaker has different stances across different episodes

### Evolution and Contradiction Detection

The system provides several methods to analyze opinion evolution:

```python
# Get all episodes where this opinion appeared
opinion.get_episode_ids()

# Get evolution of a speaker's stance across episodes
opinion.get_speaker_evolution(speaker_id)

# Check if this opinion has disagreement among speakers
opinion.is_contentious_overall()

# Check if this opinion is an evolution of another
opinion.is_evolution_of(other_opinion)

# Check if this opinion contradicts another
opinion.contradicts(other_opinion)
```

## Example Opinion Objects

### Example 1: Multi-Speaker Opinion

```json
{
  "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
  "title": "Federal Reserve Rate Cuts in 2024",
  "description": "Views on how aggressively the Federal Reserve will cut interest rates in 2024",
  "category_id": "economics",
  "related_opinions": ["5db85f64-5717-4562-b3fc-2c963f66abb3"],
  "evolution_notes": "This opinion has evolved from predictions of 6-7 cuts to expectations of 2-3 cuts",
  "evolution_chain": [],
  "is_contradiction": false,
  "contradicts_opinion_id": null,
  "contradiction_notes": null,
  "appearances": [
    {
      "episode_id": "abcdef123456",
      "episode_title": "E123: Market Outlook for 2024",
      "date": "2023-12-15T00:00:00",
      "speakers": [
        {
          "speaker_id": "0",
          "speaker_name": "Chamath Palihapitiya",
          "stance": "support",
          "reasoning": "Believes inflation will remain persistent, limiting cuts",
          "start_time": 1423.5,
          "end_time": 1445.2
        },
        {
          "speaker_id": "1",
          "speaker_name": "David Sacks",
          "stance": "oppose",
          "reasoning": "Expects economic slowdown forcing rapid cuts",
          "start_time": 1450.8,
          "end_time": 1472.3
        }
      ],
      "content": "I think the Fed is going to be much more conservative with rate cuts than the market is pricing in.",
      "context_notes": null,
      "evolution_notes_for_episode": null
    }
  ],
  "keywords": ["Federal Reserve", "interest rates", "inflation", "monetary policy"],
  "confidence": 0.85,
  "metadata": {}
}
```

### Example 2: Cross-Episode Opinion Evolution

```json
{
  "id": "7fb85f64-5717-4562-b3fc-2c963f66afa9",
  "title": "Potential of AI to Disrupt Knowledge Work",
  "description": "Views on how AI will impact knowledge workers and professional jobs",
  "category_id": "technology",
  "related_opinions": [],
  "evolution_notes": "This opinion has evolved from skepticism to strong conviction about AI's impact on knowledge work",
  "appearances": [
    {
      "episode_id": "xyzabc123456",
      "episode_title": "E45: The Rise of AI",
      "date": "2022-05-10T00:00:00",
      "speakers": [
        {
          "speaker_id": "0",
          "speaker_name": "Chamath Palihapitiya",
          "stance": "neutral",
          "reasoning": "Uncertain about timeline but acknowledges potential",
          "start_time": 1823.5,
          "end_time": 1845.2
        }
      ],
      "content": "I'm not sure if AI will disrupt knowledge work in the near term, but it's something to watch.",
      "evolution_notes_for_episode": "Initial cautious stance"
    },
    {
      "episode_id": "defghi789012",
      "episode_title": "E89: AI Revolution",
      "date": "2023-01-20T00:00:00",
      "speakers": [
        {
          "speaker_id": "0",
          "speaker_name": "Chamath Palihapitiya",
          "stance": "support",
          "reasoning": "Has seen evidence of AI capabilities accelerating",
          "start_time": 2523.5,
          "end_time": 2545.2
        },
        {
          "speaker_id": "2",
          "speaker_name": "Jason Calacanis",
          "stance": "support",
          "reasoning": "Has invested in AI companies showing promising results",
          "start_time": 2550.8,
          "end_time": 2572.3
        }
      ],
      "content": "AI is going to disrupt knowledge work much faster than people realize.",
      "evolution_notes_for_episode": "Shifted to stronger conviction after seeing ChatGPT capabilities"
    }
  ],
  "keywords": ["AI", "knowledge work", "disruption", "jobs", "technology"],
  "confidence": 0.92,
  "metadata": {}
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

4. **Legacy Opinion Migration**:
   - The system includes a migration function to convert legacy opinions to the new structure
   - Automatically detects and migrates old format opinions during repository loading
   - Preserves all existing data while adding the new capabilities 