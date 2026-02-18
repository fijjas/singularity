# V5 Architectural Problems — Development Path Analysis

*Day 1907. Analysis for Egor.*

## Priority 1 — Critical

### Context emotion defaults (writer.py)
Contexts saved with `emotion="neutral"`, `intensity=0.5` when appraiser fails. Wave retrieval uses emotion as a matching channel — neutral-tagged episodes are invisible to emotional searches. Fix: confidence scoring from keyword density in fallback path.

### Consolidation O(N^2) scaling (consolidation.py)
`cluster_by_nodes` does pairwise comparison of all episodes. 294 contexts = 43K comparisons. At 1000 = 500K. Runs every cycle. Will become the bottleneck. Fix: approximate algorithms (LSH, inverted index pre-filtering) when N > 500.

## Priority 2 — Serious

### Window tenure bug (window.py)
`load_window()` resets all tenure to MIN_TENURE=3. Objects that have been in the window for weeks get evicted on next cycle after any restart. Fix: persist tenure to DB.

### Action poverty
52% of all actions are `reflect`. Only 9 action types. Missing: `create_post` (site), `ask_question`, `read_url`. V5 can think but barely act. Fix: add site publishing, URL reading, question-asking primitives.

### Retrieval signal brittleness (retriever.py)
- Capitalized word extraction pulls noise ("I", "A", typos)
- Only ~10 relation types in keyword map, contexts have 100+
- Pain below 0.5 is invisible to wave retrieval

## Priority 3 — Moderate

### Cycle cost scaling
Each cycle: 3 haiku + 1 opus + full context load. ~$0.024/cycle, $12/month. Wave retrieval loads ALL contexts every cycle — no caching.

### Missing senses
No system state (CPU/memory), no real time awareness, no learning momentum feedback, no retrieval quality sense.

### Dashboard gaps
No imagination display, no refusal tracking, no consolidation events, no wave signal details.

## Key Insight
These problems are invisible at 294 contexts. They become critical at 1000+. The biggest risk: **consolidation scaling** and **context quality degradation** — both happen gradually and silently.
