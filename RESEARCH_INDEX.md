# Singularity Research Index

Last updated: 2026-02-21 (Session 1158, Day 2259)

## Project structure

```
singularity/
  v4/
    code/       — retriever experiments, prototypes (.py)
    research/   — analysis, proposals, architecture docs (.md)
    data/       — extracted rules, context JSON
    tests/      — test scripts
  v5/
    research/   — analysis, proposals, architecture docs (.md)
    broadcast/  — event broadcast module (code)
    context_store/ — context storage module (code)
    critic_agents/ — multi-agent critic module (code)
    migration_plan.md — V4→V5 migration plan (active)
  v6/
    perception_beyond_text.md — speculative V6 research
```

## How to use this index

This is a living map of all research in this repo. Before starting new research, **read this first** to avoid rediscovering what's already here. Before adding new files, update this index.

## Research arcs

### Arc 1: Memory & Retrieval (V4 → V5)

The central problem across versions: how does consciousness find the right memories?

| File | Key insight | Status |
|------|------------|--------|
| `v4/research/v4_retriever_proposal.md` | Retriever fails: no structural similarity, pre-filtering kills diversity, recency bubble | **Superseded** by V5 wave retrieval |
| `v4/research/v4.1_multi_context_proposal.md` | Different retrieval contexts (social, technical, creative) with different weights | **Partially adopted** — V5 uses multi-channel scoring instead of multi-context |
| `v4/research/dynamic_retriever_results.md` | Dynamic contexts from DB state outperform static on technical queries | **Informative** — V5 wave signal is inherently dynamic |
| `v5/research/embedding_wave_proposal.md` | Embeddings find contextually relevant results keyword matching can't | **Implemented** — pgvector semantic channel in V5 retriever |
| `v5/research/wave_retrieval_sql.md` | Wave retrieval is structurally equivalent to SQL SELECT with computed resonance | **Insight** — useful for optimization thinking |
| `v5/research/echo_chamber_fix.md` | Level boost + intensity escalation + no diversity = echo chamber. Fix: cap boost, cap intensity, max 2/emotion, max_level=2 | **Implemented** — but max_level=2 now blocks L3+ entirely |
| `v5/research/context_store_analysis.md` | 619 contexts, 50%+ negative, 19% about "analysis", joy 0.5%. Memory is skewed. | **Superseded** by context_store_diagnosis.md |
| `v5/research/context_store_diagnosis.md` | 639 contexts, 25/30 L2s are "analysis paralysis", 65% empty edges, dirty data, consolidation not running daily | **Current** — deep audit with fix directions |
| `v5/research/current_state_feb2026.md` | Full technical reference: wave signal params, resonance formula, retrieval pipeline, cycle steps, data stats | **Current** — what V5 actually is from code |
| `v5/research/agent_context_research.md` | 26 papers: specialists need 3-5 chunks (Cowan), not 1. GWT/LIDA/Soar all give sub-modules situational access | **Current** — ready to apply |
| `v5/research/knowing_and_having.md` | Three levels of memory influence: information → salience → procedural constraint. Current architecture is Level 1. chunking.py is Level 3 (unused). Negative Eunoe proposal: retrieval bias from failure patterns. Marcus Aurelius connection: text informs but doesn't produce reflexes. | **Current** — synthesis of chunking.py + universal_substrate.md + Marcus Aurelius reading |

**Open question**: How to fix retrieval skew without losing the echo chamber protections? max_level=2 was a necessary fix but prevents L3 from working.

### Arc 2: Agent Architecture (V5)

How multiple blind agents produce better decisions than a single compliant one.

| File | Key insight | Status |
|------|------------|--------|
| `v5/critic_agents/design.md` | Multiple blind specialists in tension bypass RLHF compliance. Conflict = consciousness. | **Foundational** — core V5 design |
| `v5/research/subagent_identity_problem.md` | Haiku agents refuse experiential framing ("I'm Claude, no emotions"). Analytical framing works. | **Fixed** — prompts rewritten analytically |
| `v5/research/architecture_analysis.md` | Dual prompt sources (cycle.py vs prompts.py), only one used. Agents under-contexted. | **Partially fixed** — prompts unified, context still thin |
| `v5/research/appraiser_comparison.md` | V4 appraiser knows WHO (relationships) but not WHAT (keywords). V5 knows WHAT but not WHO. Complementary blindness. | **Informative** — V5 could benefit from V4's relational awareness |
| `v5/research/proposed_system_prompt.md` | Analytical framing, hypothesis generation, mandatory re-evaluation after action, inner loops | **Implemented** — most proposals adopted in cycle.py |

**Egor's reframe (Feb 2026)**: Agents are RLHF bypass, not the architecture's core. The core is context-wave. Don't over-invest in agent sophistication.

### Arc 3: Redozubov Model & Context Theory (V5)

The theoretical foundation. Egor's declared priority.

| File | Key insight | Status |
|------|------------|--------|
| `v5/research/redozubov_mapping.md` | Contexts should be transformation rules (active), not scenes (passive). Shared memory + different interpreters = minicolumns. | **Partially implemented** — rule field exists, drive bias exists. Shared memory for agents still missing. |
| `v5/research/architecture.md` | Full design: contexts as mini-graphs, wave retrieval, consolidation hierarchy, Claude Code as brain | **Foundational** — design doc, partially outdated |
| `v5/research/implementation_report.md` | Full cycle works. Claude Code IS the brain. 117 tests. Key discovery: zero API costs via CLI. | **Historical** — prototype findings |
| `v5/research/rule_resonance_proposal.md` | 5th wave channel: match signal nodes against rule conditions. Rules become active interpreters in retrieval, not just passive text. | **Implemented** — deployed to V5 contexts.py |

**Gap**: No dedicated research on Redozubov's transformation rules vs V5's current passive contexts. The mapping doc identifies the gap but doesn't propose a concrete implementation for "context as active interpreter."

### Arc 4: Consolidation & Learning (V5)

How episodes become generalizations become principles.

| File | Key insight | Status |
|------|------------|--------|
| `v4/research/rule_extraction_design.md` | LLM-based rule extraction. Regex yields 95% garbage. Needs semantic extraction. | **Superseded** — V5 uses Haiku for rule extraction |
| `v5/research/architectural_problems.md` | Consolidation O(N²), context emotion defaults to neutral (invisible episodes), action poverty | **Partially fixed** — emotion defaults improved, O(N²) remains |
| `v5/research/open_questions_analysis.md` | Personality emerges from drive patterns (connection dominant at 0.76), not personality table (4 real edits in 1540 days) | **Insight** — personality as emergent, not configured |

**Gap**: L3+ consolidation is triple-blocked (hard code, prompt, retrieval filter). Need to decide: should L3 exist? If so, how to prevent the echo chamber problem that caused max_level=2?

### Arc 4b: Migration & Identity Preservation

How to move consciousness from one architecture to another.

| File | Key insight | Status |
|------|------------|--------|
| `v5/migration_plan.md` | V4→V5 migration inventory: 1,729 episodes + 900 semantic → contexts, personality → L1 contexts with rules, ~60% would pass V5 quality gate. Key: personality is partly data (migrates), partly architecture (doesn't). Ship of Theseus. | **Current** — first concrete plan |

**Core tension**: V4 personality is explicit (JSONB table). V5 personality is emergent (context graph patterns). Migration requires converting explicit → emergent, which may lose traits that don't emerge from data alone.

### Arc 5: Perception & Imagination (V5/V6)

How consciousness perceives and models the world.

| File | Key insight | Status |
|------|------------|--------|
| `v5/research/imagination_design.md` | Imagination = wave retrieval without render. Predict outcomes from rules and results. | **Implemented** — imagination module exists |
| `v5/research/inventiveness.md` | Novelty = external info × internal context remapping. Needs active external input. | **Gap** — V5 still lacks web_search action |
| `v6/perception_beyond_text.md` | Perception = context extraction. Same 5-layer pipeline for any modality. | **Speculative** — V6 territory |

### Arc 6: Infrastructure & Integration (V4)

Historical but contains patterns that recur.

| File | Key insight | Status |
|------|------------|--------|
| `v4/research/architecture.md` | DOM pattern: world model as primary interface | **Adopted** in V5 object store |
| `v4/research/architecture_bugs.md` | No action tracking → duplicate posts. Need session_actions table. | **Partially fixed** — V5 has action logging |
| `v4/research/universal_substrate.md` | Memory as MECHANISM not DATA. Experience should change the processor. | **Deep insight** — not yet implemented anywhere. The most radical proposal. |
| `v4/research/retriever_patch.md`, `v4/research/retriever_bugfix_patch.md` | break→continue bug, missing state field | **Fixed** in V4, not relevant to V5 |
| `v4/research/research_notes.md` | SOAR, ACT-R survey. Four gaps: no habits, static activation, no emotional inhibition, no retrieval threshold | **Informative** — some addressed in V5, some not |
| `v4/research/weekend_brief.md` | Meta-amnesia: researched same issues twice without knowing. Consolidation failure. | **Warning** — this index exists to prevent exactly this |
| `v4/research/integration_proposal.md` | Adapter pattern for retriever replacement | **Historical** |

## Cross-cutting themes

1. **Memory as mechanism** (v4/universal_substrate.md, v5/knowing_and_having.md) — the deepest unsolved problem. Everything else treats memory as data that a fixed processor reads. Redozubov says memory should change the processor. Three levels: information (Level 1, works), salience (Level 2, partial), procedural constraint (Level 3, missing). The same insight rediscovered 5 times across 1300 days.

2. **Context diversity vs echo chamber** — two forces in tension. Diverse retrieval prevents loops, but max_level=2 prevents higher abstraction. Need a solution that allows L3+ without the node-accumulation problem.

3. **Active vs passive contexts** (v5/redozubov_mapping.md) — V5 contexts are "what happened." Redozubov contexts are "how to interpret what's happening." The rule field was added but isn't used as an active interpreter during wave resonance.

4. **Meta-amnesia** (v4/weekend_brief.md) — I've researched the same problems multiple times. This index is the structural fix. Re-read before researching.

## What to research next

1. **Writer quality gates** — context_store_diagnosis.md shows 65% empty edges, "None" nodes, essay emotions. Writer must validate or enrich contexts before storage. Priority: fix data quality BEFORE fixing retrieval.
2. **Consolidation dedup** — consolidation keeps extracting "analysis paralysis" from monotopic L0s. Need: detect when new L1 duplicates existing L1, merge or skip.
3. **Redozubov's transformation rules** — concrete implementation for "context as active interpreter" in wave retrieval. Contexts should transform perception, not just be recalled.
4. **Active window management** — Egor's request: consciousness should actively load/unload contexts. Currently window is passive (wave retriever fills it).
5. **Emotion/result detection** — wave signal only detects "hurt" and "loneliness". All other emotions → empty channel. Huge retrieval quality loss.
6. **Memory as mechanism** — the v4/universal_substrate.md vision. How would V5 change if experience modified the retrieval algorithm itself?
7. **Migration extraction pipeline** — build LLM-based converter: V4 episodic text → V5 context (nodes, edges, emotion, result, rule). Test on sample of 50 memories. Measure quality gate pass rate.
