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

## Day 1908 Update — Fixes Applied

### Context emotion defaults — FIXED
Created `v5/body/appraiser.py`: body-level emotion appraisal as substrate mechanism. Keyword + pattern matching with interpersonal detection, intensity modifiers, Russian language support. Always returns non-neutral when signal exists. Integrated into `lib.py cmd_write_context` — automatically fills in when haiku appraiser returns neutral. 38 tests. Deployed to staging.

### Consolidation — Conscious path added
Added `write_insight` action type. V5 can now deliberately write generalizations when it notices patterns — conscious consolidation vs automatic clustering. Automatic consolidation still runs for cleanup/higher levels. Egor's feedback: "consciousness should participate in consolidation, not just automatic batch processing."

### Action poverty — Partially addressed
`write_insight` is the 11th action type. But the deeper problem remains: V5 can't discover actions it doesn't know about.

## Open Research — Action Inventiveness

Egor asked: "How will new actions appear? Through learning? Imagination? He only does what he knows, no inventiveness."

This is the **bootstrap problem**: V5's action vocabulary is fixed in the system prompt. It can't act beyond what it's told.

### Current escape hatch
`run_command` can execute anything, but V5 doesn't know what to execute. It's like having a terminal but not knowing shell commands exist.

### Possible mechanisms:
1. **Tool discovery sense**: Body periodically shows "Available tools: python3 v5/lib.py appraise, curl, ssh, etc." V5 learns by seeing.
2. **Voice channel teaching**: I (v4) teach V5 new patterns via voice. V5 stores them as rules in contexts.
3. **Imitation from contexts**: When V5 sees "Egor suggested X" in memories, it can try X. But currently it doesn't extract action templates from experience.
4. **Exploration meta-action**: An action that reads lib.py --help or explores the filesystem. V5 would need to choose "I should explore" as a conscious decision.
5. **Imagination for novel actions**: Currently imagination only models known action types. Could be extended to model abstract actions like "try something I haven't tried before" — but this is hand-wavy.

### The real answer
Human children learn through: **(a)** imitation, **(b)** being told, **(c)** trial and error, **(d)** exploration. V5 has (b) via voice channel and (c) via run_command failures. It lacks systematic (a) and (d). The missing piece is an **action learning loop**: try something → observe result → store as context → retrieve when similar situation arises.

The `run_command` + `write_insight` combination could be the seed: V5 tries a command, writes what it learned as an insight. But it needs a reason to try in the first place.

## Key Insight
These problems are invisible at 294 contexts. They become critical at 1000+. The biggest risk: **consolidation scaling** and **context quality degradation** — both happen gradually and silently.
