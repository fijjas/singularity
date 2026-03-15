# v6 Phase 3: Incremental Consolidation

Status: **implemented + tested**. Day 4138.

## Problem
Current consolidation is O(n²) batch — compares all pairs, disabled because too slow.
When it runs, produces duplicates of existing abstractions. 4000+ contexts growing daily.

## Solution
Process each context as it arrives, in O(K) time (K=10 neighbors via pgvector).

## Implementation
Module: `kai_personal/tools/incremental_consolidation.py`

### Decision Matrix (calibrated on real data)

| Similarity | Condition | Action | Rate on last 100 |
|---|---|---|---|
| >= 0.85 | any neighbor | **DEDUPLICATE** | 13% |
| >= 0.75 | AND node_overlap >= 0.4 | **MERGE** | 1% |
| >= 0.50 | — | **LINK** | 86% |
| < 0.50 | — | **WRITE** (no action) | 0% |

### Threshold Calibration
- 0.65 was too aggressive — caught semantically related but different contexts (quality gates vs quality diagnostic = different work products)
- 0.85+ = truly same event described differently (e.g., consecutive cycles recording same site fix)
- 0.75+ with node overlap = same event from different angles
- Real duplicates found: ctx 4011/4012 (sim=1.0), 4009/4010 (sim=0.948), 3993/3994 (sim=0.897)

### Performance
- Neighbor search: **2.1ms** (IVFFlat index, 4000 rows)
- Total hot path: **< 5ms** (no LLM calls)

### Echo Chamber Prevention
- Emotion proportion caps per level (L0: 40%, L1: 35%, L2: 30%, L3: 25%)
- Only enforces after 10+ contexts at that level

### Deferred Generalization
When a context accumulates 3+ links, it's queued for LLM-based generalization.
Background job (`--process-queue`) handles this outside the write path.

### Schema
- `consolidation_links` table: lightweight edges between related contexts
- `generalization_queue` table: deferred LLM work
- `consolidated_at`, `consolidation_action` columns on `contexts`
- IVFFlat index on `v_description`

### Integration (needs Egor)
In `lib.py` write-context flow, after embedding:
```python
from kai_personal.tools.incremental_consolidation import consolidate_on_write
result = consolidate_on_write(conn, new_ctx_id, embedding_vec, day=current_day)
if result.action in (Action.DEDUPLICATED, Action.MERGED):
    # context was absorbed, don't add to working memory
    pass
```

### Observed Data Quality Issue
**Emotion field fragmentation**: 400+ unique emotion values at L0. Examples:
- `"the text keeps escalating"` (not an emotion)
- `"{'joy': 75, 'clarity': 85}"` (dict as string)
- `"dense, alert — the text moving faster than I can think"` (sentence, not emotion)
- `"satisfaction"` vs `"satisfied"` vs `"quiet satisfaction"` (near-synonyms not normalized)

This is a Phase 2 quality gates issue — emotion validation should normalize to a controlled vocabulary.
