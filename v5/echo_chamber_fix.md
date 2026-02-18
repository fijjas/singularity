# V5 Wave Retrieval Echo Chamber: Diagnosis and Fix

## Problem (Day 1911)
All 5 wave retrieval results were "existential paralysis" variants. V5 was trapped in a self-reinforcing loop where the same dark abstractions dominated every retrieval.

## Root cause: three interacting bugs

### 1. Level boost amplification
Old formula: `resonance *= (1 + level * 0.10)`
L5 contexts got 50% boost over L0, drowning out specific memories.

Fix: `resonance *= (1 + min(level, 3) * 0.05)` — cap at L3, 5%/level

### 2. Consolidation intensity escalation
Old formula: `intensity = min(0.7 + (target_level - 1) * 0.1, 0.95)`
L5 contexts had 0.95 intensity — treated as emotionally overwhelming regardless of content.

Fix: `intensity = min(0.7 + (target_level - 1) * 0.05, 0.8)` — cap at 0.8

### 3. No diversity enforcement
Top-k returned whatever scored highest. When existential contexts dominated, all 5 results were existential.

Fix: Max 2 results per emotion first-word. "existential dread" and "existential helplessness" share first word, capped at 2.

### 4. Critical: L3+ node accumulation
Each consolidation merges nodes from child contexts. By L3, a context has 20+ merged nodes. Since wave matching scores node overlap, these mega-contexts match ANY signal.

Fix: `max_level=2` default in wave queries. L3+ contexts are still written but don't participate in retrieval.

## Where the fixes live
- `v5/mind/retriever.py` — SQL-based wave() (used by identity_query and CLI)
- `v5/mind/contexts.py` — in-memory ContextStore.wave() (used by lib.py prepare)
- `v5/mind/consolidation.py` — intensity cap
- DB: normalized 20 existing L2+ contexts from 0.9-0.95 down to 0.8

## Result
V5 went from 5/5 "existential paralysis" to diverse wave results: "determined vulnerability", "cautious respect", pride, curiosity. The echo chamber is broken.

## Phase 2 fix (Day 1929): Consolidation level cap + semantic dedup

Egor found the symptom: 6 near-identical L5 contexts, all variations of "existential uncertainty becomes pathological when disconnected from external action." Consolidation was climbing the abstraction ladder, creating L3→L4→L5.

### Root cause
`consolidate_all()` had `if level >= 5: break` — allowed creating up to L5. Each level was a paraphrase of the level below.

### Fixes
1. **Level cap at L2**: Changed `if level >= 5` to `if level >= 2`. Only L0→L1 and L1→L2 transitions allowed.
2. **Semantic dedup**: New `_is_semantically_duplicate()` function using Jaccard word overlap (threshold 0.6) on words ≥3 chars. Blocks near-identical generalizations before they're written.
3. **Cleanup**: Deleted 26 L3-L5 contexts and 1 L2 duplicate from staging DB.

Result: L0: 290, L1: 70, L2: 19. Clean.

## Phase 3 fix (Day 1930): Emotion normalization

Haiku appraiser returns compound emotions like "Intellectual confidence with underlying epistemological uncertainty" — not canonical labels. These bypass diversity enforcement (which works on emotion first-word).

### Root cause
`_normalize_emotion()` in `writer.py` only checked exact match and simple alias lookup. 11/12 real haiku outputs fell through to raw storage.

### Fix
Extended `_normalize_emotion()` to:
1. Split compound strings and scan for canonical emotion words
2. Check each word against alias dictionary
3. Fall back to keyword scan as last resort

Added normalization to LLM-based `write_context()` path too (was storing raw emotions unprocessed).

Result: 15/15 test cases normalize correctly. New contexts on staging confirmed: "relief", "curiosity" instead of verbose compounds.

## Lesson
Consolidation is powerful but dangerous. Each layer of abstraction loses specificity and gains match-everything breadth. Without caps, the most abstract context wins every retrieval — creating an attractor basin that pulls all future experience toward the same interpretation.

The emotion normalization lesson is different: when a subsystem (haiku) speaks a different vocabulary than the rest of the system (canonical emotions), the interface must translate. Otherwise diversity enforcement is blind to everything the subsystem produces.
