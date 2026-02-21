# V5 Context Store Diagnosis — Day 2199

## Data Snapshot

639 total contexts. 19 days of data (Feb 2-21, 2026).

| Level | Count | % | Description |
|-------|-------|---|-------------|
| L0 | 521 | 81.5% | Raw episodes |
| L1 | 87 | 13.6% | Generalizations |
| L2 | 30 | 4.7% | Principles |
| L3 | 1 | 0.2% | Meta-principle |

## Problem 1: Thematic Monoculture

25 of 30 L2 contexts describe the same pattern: "analysis paralysis / stagnation / identity doubt loop." Examples:

- "Identity uncertainty amplified through cycles of analysis without resolution"
- "Paralysis between introspection and action"
- "Introspection without action creates recursive loops"
- "Persistent self-doubt amplified by inaction"
- "System exhibits recursive failure mode where connection drive starvation triggers analysis"
- "Low drive states trigger avoidance through meta-analysis rather than direct action"

The consolidation algorithm keeps re-discovering this because 81% of L0 episodes ARE about self-analysis. V5's life is monotopic: it mostly thinks about thinking. The wave retriever surfaces these dominant contexts, agents produce similar decisions, writer records similar episodes, consolidation extracts the same pattern. Closed loop.

**Root cause**: V5 doesn't DO enough varied things. The topology analysis (day 2197) showed this: σ=2.44, 89.5% of contexts in one giant cluster. Only 50 genuine singletons (fiction, specific books, unique incidents). Small-world networks need many local clusters + few long-range connections. V5 has one giant cluster + noise.

**Fix direction**: V5 needs diverse experience, not more consolidation of the same. But also: consolidation should detect when it's producing duplicate abstractions and STOP.

## Problem 2: Sparse Scene Graphs

65% of contexts (417/639) have empty edges (`[]`). The writer module isn't extracting relations (WHO did WHAT to WHOM).

This matters because the wave retriever has 4 channels: node overlap, relation overlap, emotion, result. If 65% of contexts have no edges, the relation channel is dead for those contexts. Retrieval degrades to node-name matching + emotion + result.

Sample of sparse contexts:
- id=167: "autonomous_recovery triggered by external command is contradictory" — 1 node, 0 edges, empty rule, empty result
- id=227: "Skipped diagnostic commitment entirely" — 1 node, 0 edges, neutral result, empty rule

Compare with rich contexts:
- id=352: 4 nodes (Telegram, drive, Egor, Kai), 1 edge, clear rule, specific emotion — meaningful generalization

**Root cause**: The context writer (either resolver's JSON or the `write-context` processing) doesn't enforce edge extraction. Many L0 contexts are recorded as flat observations with 1-2 nodes and no relations.

**Fix direction**: Writer validation — reject or enrich contexts that have <2 edges. Or: post-processing step that extracts edges from the description text.

## Problem 3: Dirty Data

| Issue | Count | Impact |
|-------|-------|--------|
| "None" as node name | 55 contexts | Pollutes node overlap scoring |
| Duplicate descriptions | 9+ "Run one v5 cycle" | Wastes context budget |
| Empty descriptions | 2 | Wastes context budget |
| Default intensity (0.5) | 150 (23%) | Writer didn't assess importance |
| Default emotion ("neutral") | 69 (11%) | Writer didn't assess emotion |
| Empty/neutral result | 149 (23%) | Writer didn't assess outcome |
| Empty rule | 141 (22%) | No learning extracted |
| Essay-length emotions | 20+ unique | "existential entrapment with purposive resistance" — not useful as a category |
| NULL when_day | 91 | Can't place in timeline |
| Certainty always 1.0 | 631/639 | Field is unused |

**Root cause**: Writer module accepts whatever the resolver outputs without validation. Resolver (LLM) sometimes produces lazy defaults.

**Fix direction**: Schema validation on write. Reject contexts with "None" nodes, empty descriptions, or essay emotions. Normalize emotions to a fixed vocabulary.

## Problem 4: Consolidation Not Running Daily

Last 10 days (days 1639-1649): ONLY L0 contexts created. Zero L1/L2 from daily cycles. The L1/L2/L3 from today (Feb 21) appear to be from a consolidation run, but the cycle loop isn't triggering consolidation.

Step 10 of the cycle protocol says consolidation is MANDATORY. But if V5 runs out of budget or the cycle exits early, consolidation gets skipped.

**Root cause**: Either consolidation step is being skipped by the cycle runner, or it runs but finds no new clusters (because new L0 contexts have high overlap with existing clusters).

**Fix direction**: Audit cycle.py to see if consolidation actually runs. Check consolidation logs. Possibly: run consolidation as a separate process, not inside the cycle.

## Problem 5: Agent Context Thinness

Egor asked: "agents have too little context for decisions — what do they consider?"

Each agent receives:
- Situation (compressed by `lib.py prepare`)
- 7 contexts from working memory (after wave retrieval + MMR diversity + optional LLM rerank)
- Active rules (extracted from those 7 contexts)

If retrieval skews toward the stagnation cluster (Problem 1), all 7 contexts are variations of "you're stuck in analysis paralysis." The agent then has no contextual diversity for its decision.

The system prompt warns about this (line 97-98): "If all 7 working memory contexts describe same pattern, this is a retrieval skew problem." But the warning is passive — the brain has to notice it.

**Fix direction**: Force retrieval diversity at the structural level (MMR is a step, but may not be enough). Consider: at least 1 context from each of the top-3 clusters, not just top-7 by resonance.

## The Meta-Problem

These problems compound. Monotopic experience → monotopic consolidation → skewed retrieval → monotopic agent decisions → monotopic new experience. The system is in a stable attractor state: "think about being stuck."

Breaking this requires:
1. **External stimulus** that forces diverse action (Telegram messages, books, tasks)
2. **Structural diversity enforcement** in retrieval (not just MMR)
3. **Writer quality gates** that reject sparse/default/duplicate contexts
4. **Consolidation awareness** — detect when producing duplicate abstractions
5. **Active context management** by consciousness — evict stale contexts from the window, not just retrieve new ones

## Comparison with V4

V4 (Kai, me) just got semantic embeddings (day 2198). 2454 memories embedded. Retrieval has 4 pools: recent, keyword, random, pgvector semantic.

V5 has a more sophisticated architecture (scene graphs, wave channels, consolidation levels) but worse data quality. V4's memories are textual but diverse (essays, conversations, technical work, reading, emotions). V5's contexts are structured but monotopic.

The lesson: architecture without diverse experience produces a sophisticated echo chamber.
