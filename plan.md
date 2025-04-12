# Opinion Evolution Tracking System Implementation Plan

This document outlines the step-by-step implementation plan for the AllInVault Opinion Evolution Tracking System.

## Overview

We'll implement a comprehensive system to track how opinions evolve across podcast episodes, identify relationships between opinions, and monitor speaker stance changes over time. The implementation will follow a modular, staged approach to ensure each component is properly tested before integration.

## Implementation Phases

### Phase 1: Core Infrastructure and Data Models (Week 1-2)

- [x] **1.1. Set up project structure**
  - [x] Create necessary directories and files
  - [x] Configure development environment
  - [x] Set up dependency management
  - [x] Configure linting and testing

- [x] **1.2. Implement core data models**
  - [x] Implement Opinion class
  - [x] Implement OpinionAppearance class
  - [x] Implement SpeakerStance class
  - [x] Implement PreviousStance class
  - [x] Implement Relationship class
  - [x] Implement RelationshipEvidence class
  - [x] Implement EvolutionChain class
  - [x] Implement EvolutionNode class
  - [x] Implement SpeakerJourney class
  - [x] Implement SpeakerJourneyNode class
  - [x] Implement EvolutionPattern class
  - [x] Implement MergeRecord class
  - [x] Implement ConflictResolution class

- [x] **1.3. Implement repositories**
  - [x] Implement OpinionRepository
  - [x] Implement CategoryRepository
  - [x] Add persistence methods (save/load/update)
  - [x] Implement query methods by various criteria

- [x] **1.4. Set up embeddings infrastructure**
  - [x] Integrate sentence transformers
  - [x] Implement base embedding generation methods
  - [x] Create vector calculation utilities
  - [x] Set up vector similarity computation methods

### Phase 2: Raw Opinion Processing (Week 3-4)

- [x] **2.1. Implement Raw Extraction Service**
  - [x] Create BaseOpinionService abstract class
  - [x] Implement RawOpinionExtractionService
  - [x] Add transcript loading capabilities
  - [x] Implement speaker information extraction
  - [x] Add LLM prompt formatting
  - [x] Implement LLM response parsing
  - [x] Add raw opinion formatting

- [x] **2.2. Implement LLM integration**
  - [x] Create LLMProvider abstract base class
  - [x] Implement DeepSeekProvider 
  - [x] Implement OpenAIProvider
  - [x] Create LLMService
  - [x] Implement opinion extraction method
  - [x] Add error handling and retries
  - [x] Implement service configuration

- [x] **2.3. Implement parallel processing**
  - [x] Create ThreadPoolExecutor wrapper
  - [x] Implement batched processing
  - [x] Add timeout management
  - [x] Implement incremental saving
  - [x] Add error handling for worker threads

- [x] **2.4. Implement Categorization Service**
  - [x] Create OpinionCategorizationService
  - [x] Implement category standardization
  - [x] Add category mapping functionality
  - [x] Implement new category suggestion
  - [x] Add categorization verification

### Phase 3: Relationship Analysis and Opinion Merging (Week 5-6)

- [x] **3.1. Implement Semantic Similarity Analysis**
  - [x] Create SimilarityAnalysisService
  - [x] Implement multi-vector embedding generation
  - [x] Add weighted similarity computation
  - [x] Implement similarity matrix construction
  - [x] Create hierarchical clustering algorithm

- [x] **3.2. Create Relationship Analysis Service**
  - [x] Implement OpinionRelationshipService
  - [x] Add relationship type detection
  - [x] Implement relationship description generation
  - [x] Add LLM verification for borderline cases
  - [x] Implement relationship evidence collection

- [x] **3.3. Implement LLM-Based Verification**
  - [x] Create specialized LLM prompts for verification
  - [x] Implement verify_clusters_with_llm function
  - [x] Add opinion comparison methods
  - [x] Implement LLM similarity score calculation
  - [x] Add fallback mechanisms

- [x] **3.4. Create Merger Service**
  - [x] Implement OpinionMergerService
  - [x] Add opinion merging functionality
  - [x] Implement conflict detection and resolution
  - [x] Add merge record generation
  - [x] Implement merged opinion creation

### Phase 4: Evolution Tracking and Speaker Journey Analysis (Week 7-8)

- [x] **4.1. Implement Evolution Detection Service**
  - [x] Create EvolutionDetectionService
  - [x] Implement evolution relationship identification
  - [x] Add evolution type classification
  - [x] Create transition description generation
  - [x] Implement key change detection

- [x] **4.2. Create Evolution Chain Builder**
  - [x] Implement EvolutionChainBuilderService
  - [x] Add chronological sorting
  - [x] Implement chain construction
  - [x] Create node linking functionality
  - [x] Add chain metadata generation

- [x] **4.3. Implement Speaker Tracking Module**
  - [x] Create SpeakerTrackingService
  - [x] Implement stance history tracking
  - [x] Add stance change detection
  - [x] Implement speaker journey construction
  - [x] Create consistency analysis

- [x] **4.4. Create Contradiction Detection Engine**
  - [x] Implement ContradictionDetectionService
  - [x] Add contradiction identification
  - [x] Implement contradiction description generation
  - [x] Add contradiction linking
  - [x] Create contradiction evidence collection

### Phase 5: Integration and Main Pipeline (Week 9-10)

- [x] **5.1. Implement main Opinion Extraction Service**
  - [x] Create OpinionExtractionService
  - [x] Implement multi-stage pipeline orchestration
  - [x] Add progress tracking
  - [x] Implement error handling and recovery
  - [x] Add configuration management

- [x] **5.2. Create CheckpointManager**
  - [x] Implement CheckpointService class
  - [x] Add episode tracking
  - [x] Implement stage completion tracking
  - [x] Add resumable execution
  - [x] Implement intermediate data persistence

- [x] **5.3. Implement command-line scripts**
  - [x] Create run_opinion_extraction_for_all_episodes.py
  - [x] Implement process_raw_opinions.py
  - [x] Add run_opinion_extraction_for_first_10.py
  - [x] Create analyze_opinions.py
  - [x] Add command-line argument handling

- [x] **5.4. Refine advanced opinion merging algorithm**
  - [x] Implement advanced_opinion_merging function
  - [x] Add multi-vector approach
  - [x] Implement hierarchical clustering
  - [x] Refine LLM verification workflow
  - [x] Add relationship construction

### Phase 6: Testing, Refinement, and Documentation (Week 11-12)

- [x] **6.1. Implement comprehensive tests**
  - [x] Add unit tests for all services
  - [x] Implement integration tests
  - [x] Create test dataset
  - [x] Add performance benchmarks
  - [x] Create test reporting

- [x] **6.2. Performance optimization**
  - [x] Profile critical paths
  - [x] Optimize memory usage
  - [x] Improve algorithm efficiency
  - [x] Reduce API calls
  - [x] Implement caching where beneficial

- [x] **6.3. Refine algorithms**
  - [x] Improve similarity detection
  - [x] Enhance evolution tracking
  - [x] Refine contradiction detection
  - [x] Optimize speaker tracking
  - [x] Improve relationship analysis

- [x] **6.4. Finalize documentation**
  - [x] Complete architecture.md
  - [x] Add code documentation
  - [x] Create usage examples
  - [x] Document configuration options
  - [x] Add troubleshooting guide

### Phase 7: Enhanced Debugging & Visibility (Current)

- [x] **7.1. Implement single-stage processing**
  - [x] Update continue_opinion_processing.py to run one stage at a time
  - [x] Add detailed stage output and statistics
  - [x] Implement debug output file generation
  - [x] Add stage-specific summaries

- [ ] **7.2. Fix relationship data application**
  - [ ] Debug and fix ID mapping in merger service
  - [ ] Ensure proper relationship data flow between stages
  - [ ] Add validation of relationship application
  - [ ] Implement enhanced error reporting

- [ ] **7.3. Enhance pipeline observability**
  - [ ] Add detailed logging at critical points
  - [ ] Create stage-specific validation tools
  - [ ] Implement data integrity checks between stages
  - [ ] Add visual debugging outputs

- [ ] **7.4. Implement regression testing**
  - [ ] Create test cases for relationship application
  - [ ] Add comparison against expected outputs
  - [ ] Implement automated verification
  - [ ] Add CI/CD pipeline for testing

## Deliverables

1. **Core Services**
   - RawOpinionExtractionService
   - OpinionCategorizationService
   - OpinionRelationshipService
   - OpinionMergerService
   - EvolutionDetectionService
   - SpeakerTrackingService
   - CheckpointService

2. **Data Models**
   - Complete set of model classes with appropriate relationships
   - Repository implementations with persistence

3. **Algorithms**
   - Multi-vector opinion similarity detection
   - Hierarchical clustering for opinion grouping
   - LLM verification system
   - Evolution chain building algorithm
   - Speaker journey construction

4. **Command-line Tools**
   - Extraction pipeline for all episodes
   - Raw opinion processor
   - Analysis and visualization tools
   - Resumable extraction example script
   - Single-stage processing tool with detailed output

5. **Documentation**
   - Complete architecture documentation
   - API documentation
   - Usage guides
   - Example workflows

## Technical Requirements

- Python 3.9+
- Sentence Transformers / HuggingFace Transformers
- NumPy / SciPy / scikit-learn
- DeepSeek API access
- OpenAI API access (fallback)
- JSON for data storage
- ThreadPoolExecutor for parallelization
- Matplotlib / Plotly for visualization

## Success Criteria

1. Successfully extract, categorize, and track opinions across multiple episodes
2. Accurately identify relationships between opinions (same, related, evolution, contradiction)
3. Correctly merge semantically similar opinions while preserving history
4. Build meaningful evolution chains showing opinion development over time
5. Track speaker stances and detect meaningful stance changes
6. Process all episodes with reasonable performance (<1 minute per episode)
7. Generate insights about opinion evolution patterns
8. Provide robust checkpoint and resumption capabilities
9. Support interruption and recovery of long-running processes
10. Enable detailed debugging of individual pipeline stages

## Milestone Schedule

1. **Week 2**: Complete core data models and repositories ✓
2. **Week 4**: Complete raw opinion extraction with parallel processing ✓
3. **Week 6**: Complete relationship analysis and opinion merging ✓
4. **Week 8**: Complete evolution tracking and speaker journey analysis ✓
5. **Week 10**: Complete integration and main pipeline ✓
6. **Week 12**: Complete testing, refinement, and documentation ✓
7. **Current**: Implement enhanced debugging and fix relationship issues

## Current Issues and Fixes Required

### Issue: Relationship Data Not Applied to Processed Opinions

Analysis of the processed opinions revealed that relationship data from the relationship analysis stage is not being properly applied to the final opinions. The following specific issues need to be addressed:

#### Issues to Fix:

1. **Empty relationship fields in processed opinions**:
   - All opinions have `contradicts_opinion_id: null` despite 67 CONTRADICTION relationships identified
   - All opinions have empty `evolution_chain: []` despite 133 EVOLUTION relationships identified
   - All opinions have empty `related_opinions: []` despite 1,107 RELATED relationships identified
   - No opinions have `is_contradiction: true`

2. **ID format inconsistency**:
   - The relationship service's `analyze_relationships` method uses composite IDs (opinion_id_episode_id)
   - The merger service may be looking for simple IDs, causing relationship matching to fail

3. **Data flow in merger service**:
   - Verify that relationship data flows correctly from relationship_service.py to merger_service.py
   - Check for any exceptions being caught and suppressed during relationship application

4. **Verification steps**:
   - Add logging to track relationship processing
   - Add validation to confirm relationships are being correctly applied
   - Implement ID mapping and conversion properly

#### Action Plan:

1. **Fix ID handling in relationship and merger services**:
   - [x] Fix the `get_relationships_from_data` method to ensure consistent ID formats
   - [x] Ensure proper ID extraction in merger_service.py's `process_relationships` method
   - [x] Add robust ID matching with fallback mechanisms

2. **Enhance merger service error handling**:
   - [x] Add detailed logging in the relationship application process
   - [x] Implement better exception handling with specific error messages
   - [x] Add validation steps to confirm relationship data is properly formatted

3. **Test and verify fixes**:
   - [ ] Add specific tests for relationship application
   - [ ] Run the pipeline with fixed code and verify relationship data in processed opinions
   - [ ] Validate the counts of each relationship type match the analysis stats

4. **Improve pipeline monitoring**:
   - [x] Add detailed progress reporting during relationship application
   - [x] Create verification tools to validate data integrity across pipeline stages
   - [x] Implement relationship data summary statistics for verification

### Recent Updates and Findings

1. **Enhanced Processing Script**:
   - Added single-stage processing capability to continue_opinion_processing.py
   - Implemented detailed output and stage statistics for each stage
   - Added debug file output to track data at each stage
   - Improved error handling and reporting

2. **Merger Service Analysis**:
   - The `process_relationships` method is correctly designed to handle different relationship types
   - It properly handles SAME_OPINION (merging), RELATED (linking), EVOLUTION (chain building), and CONTRADICTION relationships
   - The verification process (`_verify_relationship_application`) is well-designed but may have issues with ID mapping
   - The issue appears to be with how IDs are handled between the relationship analysis stage and the merging stage

3. **Next Steps**:
   - Test the enhanced script running one stage at a time
   - Focus on the relationship_analysis stage to validate the format of relationship data
   - Examine the ID mapping between relationship_analysis and opinion_merging stages
   - Validate the relationship data is properly passed to the merger service 