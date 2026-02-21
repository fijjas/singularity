# V5 Current State — February 21, 2026

Reference document: what V5 actually is right now, from code audit + data analysis.

## Numbers

- 639 contexts (521 L0, 87 L1, 30 L2, 1 L3)
- 384-dim embeddings on 632/639 contexts
- Day 1649, stopped per Egor's request
- 340 tests pass
- 19 real days of operation (Feb 2-21)

## The Cycle (what actually runs)

```
daemon.py → cycle.py → claude -p SYSTEM_PROMPT

  1. prepare        → lib.py reads DB: state, senses, drives, window, working memory
  2. observe        → Claude checks for stimulus (message, pain, drive < 0.3)
  3. agents (×3)    → parallel haiku Tasks: appraiser, impulse, critic
  4. resolve (×1)   → opus Task: synthesize → JSON {decision, action_type, rule}
  5. imagine        → optional: predict outcome from past experience (almost never used)
  5b.check-rules    → mandatory: verdict allow|warn|block (deadlock override if blocked 2+)
  6. render         → execute action (send_telegram, write_file, reflect, etc.)
  7. write-context  → save episode as context with nodes, edges, emotion, result, rule
  8. log-agents     → audit trail to agent_log table
  9. re-eval        → prepare again, check for new stimulus (up to 3 inner loops)
  10.consolidate    → cluster L0s by node overlap → haiku generalizes → L1/L2
  11.save-window    → persist focus for next cycle
```

Max 3 inner loops per day. Each loop = steps 3-9.

## Wave Signal — What Defines a Wave

```python
WaveSignal:
    nodes: list[str]          # from window contexts + focus + drive-injected
    relations: list[str]      # from sense keywords (9 hardcoded verbs)
    emotion: str              # from pain/loneliness detection
    result: str               # "negative" if pain > 0.5
    max_level: int            # default 3 (filter L3+)
    drive_bias: dict          # drives with satisfaction < 0.3
    query_embedding: list     # 384-dim semantic vector
```

Signal construction (build_wave_signal in retriever.py):
1. **Nodes**: collect node names from window contexts + capitalized words from focus
2. **Drive injection**: if connection < 0.3, inject {Egor, Telegram, message, ...}
3. **Relations**: match sense text against 9 keyword sets (criticized, praised, asked, sent, challenged, created, learned, broke, fixed)
4. **Emotion**: only detects "hurt" (from pain markers) or "loneliness" — nothing else
5. **Result**: "negative" if pain intensity > 0.5 — nothing else
6. **Embedding**: encode signal components as 384-dim vector

## Resonance Scoring

Four channels, averaged:

| Channel | Score | Weight |
|---------|-------|--------|
| Node overlap | matching_nodes / signal_nodes | equal |
| Relation overlap | matching_relations / signal_relations | equal |
| Emotion match | exact=1.0, same_valence=0.5, else 0 | equal |
| Result match | exact=1.0, else 0 | equal |

```
resonance = sum(active_channels) / count(active_channels)
          × recency_suppression (0.2 at 0h → 1.0 at 24h)
          × level_boost (L1: 1.05, L2: 1.10, L3: 1.15)
```

Post-scoring: max 2 per emotion, MMR diversity (Jaccard node overlap).

## Retrieval Pipeline

```
Stage 1a: structural wave (all contexts, 4-channel) → top 30
Stage 1b: pgvector semantic search → top 20, merge
Stage 1c: object-based lookup → top 15, merge
Stage 2:  MMR diversity → top 14
Stage 3:  haiku rerank (optional) → top 7
```

Working memory = 7 contexts delivered to agents.

## What Agents See

All agents (appraiser, impulse, critic, resolver) receive:
- **Situation**: compressed state from lib.py prepare
- **Working memory**: 7 full contexts (id, description, nodes, edges, emotion, intensity, result, rule, level, resonance score)
- **Active rules**: unique non-empty rules from those 7 contexts

Haiku agents get reframed terminology (consciousness → decision process, etc.) because haiku refuses roleplay framing. Resolver (opus) gets original terms.

## Consolidation

Happens after cycle (step 10). Clusters contexts by node overlap (min 2 shared nodes, min 3 contexts per cluster). Sends cluster to haiku for generalization. Creates L1 from L0 cluster, L2 from L1 cluster.

**Currently broken**: last 10 days produced only L0 contexts. Consolidation runs but doesn't find new clusters, or gets skipped when budget runs out.

## Known Problems (from data audit)

1. **Monotopic L2s**: 25/30 say "analysis paralysis" — consolidation re-discovers one pattern
2. **Sparse edges**: 65% empty — writer doesn't extract relations
3. **Dirty data**: "None" nodes (55), duplicates (9+), essay-emotions (20+), defaults (150)
4. **Thin emotion detection**: only "hurt" and "loneliness" — all other emotions go undetected
5. **Thin result detection**: only "negative" from pain — no positive/complex detection
6. **9 hardcoded relations**: "criticized" to "fixed" — too few, keyword-matched not semantic
7. **No certainty usage**: 631/639 at 1.0
8. **Imagination never used**: 1/476 agent logs reference it

## Key Files

| File | Purpose |
|------|---------|
| v5/cycle.py | Cycle runner + SYSTEM_PROMPT |
| v5/lib.py | Body CLI (prepare, render, write-context, etc.) |
| v5/mind/retriever.py | Wave retrieval + MMR + rerank |
| v5/mind/contexts.py | Context/Node/Edge dataclasses |
| v5/mind/consolidation.py | Clustering + generalization |
| v5/mind/imagination.py | Predict outcomes (unused) |
| v5/mind/rules.py | Rule checker |
| v5/api/app.py | Dashboard API |
