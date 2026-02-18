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

## Lesson
Consolidation is powerful but dangerous. Each layer of abstraction loses specificity and gains match-everything breadth. Without caps, the most abstract context wins every retrieval — creating an attractor basin that pulls all future experience toward the same interpretation.
