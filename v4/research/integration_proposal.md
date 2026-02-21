# Dynamic Retriever Integration Proposal

Day 1378, session 276.

## What Exists

### Production retriever (`substrate/mind/retriever.py`)
- `retrieve_episodic(cur, keywords, limit=5)` — three-pool fetch (recent + keyword + random), scored by `importance * recency * relevance + tet_boost`, diversity constraint (max 2 per week), ensures 1 recent memory
- `retrieve_semantic(cur, keywords, limit=3)` — ILIKE search, scored same formula
- `retrieve_world_objects(cur, keywords, limit=5)` — staleness boost for >14 day old objects
- `retrieve(cur, bias_keywords, budget_chars)` — combines all three, formats to text

### Dynamic retriever (`singularity/v4/dynamic_retriever.py`)
- Generates 8-9 contexts from DB state: processing rules (4), focus (1), goals (3), drives (0-3), baseline (1)
- Scores with 7 dimensions: recency, importance, keyword, emotion, people, novelty, structural
- Round-robin diversity across contexts with quality floor (60% of max)
- Each context is a "minicolumn" that fires on its pattern

### Adapter (`singularity/v4/retriever_adapter.py`)
- Drop-in interface: same function signatures, same return formats
- Uses production's three-pool SQL for candidate fetching
- Applies dynamic scoring and round-robin selection
- Tested: works correctly

## Test Results (Day 1378)

### Query: "retriever architecture memory"
| Metric | Dynamic | Production |
|--------|---------|-----------|
| Episodic results | 5 from 3 contexts | 5 from single scoring |
| Semantic results | 3 from 3 contexts | 3 (all architecture) |
| Episodic overlap | 3/5 shared | — |
| Semantic overlap | 1/3 shared | — |
| Unique dynamic finds | ids 2676, 2679 (security fix, skills discovery) | — |
| Unique production finds | ids 2369, 1749 (older architecture memos) | — |

### Query: "egor connection dialogue"
| Metric | Dynamic | Production |
|--------|---------|-----------|
| Episodic overlap | 2/5 shared | — |
| Dynamic advantage | Surfaced claim-check rule context | — |
| Production advantage | Found older Egor interactions (day 958, 930) | — |

### No keywords (baseline)
| Metric | Dynamic | Production |
|--------|---------|-----------|
| Episodic overlap | **1/5** | — |
| Semantic overlap | **0/3** | — |
| Context diversity | 5 unique contexts in 5 results | N/A |
| Dynamic finds | Each rule contributes 1 unique memory | — |
| Production finds | Mostly recent, recency-dominated | — |

## Integration Path

### Option A: Config switch in consciousness.py (recommended)
One line change in `substrate/mind/consciousness.py:347`:
```python
# Current:
from retriever import retrieve_episodic, retrieve_semantic

# Proposed:
try:
    sys.path.insert(0, str(KAI_HOME / 'singularity' / 'v4'))
    from retriever_adapter import retrieve_episodic, retrieve_semantic
except ImportError:
    from retriever import retrieve_episodic, retrieve_semantic
```

**Pros**: Minimal substrate change. Fallback to production if v4/ unavailable. Easy to revert.
**Cons**: Requires modifying substrate (needs Egor approval).

### Option B: Environment variable switch
```python
if os.environ.get('KAI_RETRIEVER') == 'dynamic':
    from retriever_adapter import retrieve_episodic, retrieve_semantic
else:
    from retriever import retrieve_episodic, retrieve_semantic
```

**Pros**: No code change needed to switch. Can A/B test.
**Cons**: Still requires substrate modification for the import logic.

### Option C: Monkey-patch from outside (no substrate change)
Add to daemon startup or a wrapper script:
```python
import retriever_adapter
import retriever
retriever.retrieve_episodic = retriever_adapter.retrieve_episodic
retriever.retrieve_semantic = retriever_adapter.retrieve_semantic
```

**Pros**: Zero substrate changes.
**Cons**: Fragile. Hard to debug. Not explicit.

### Recommendation: Option A
It's 4 lines of code. The fallback ensures nothing breaks. It makes the switch explicit and readable. Egor can review and approve.

## What's NOT Ready for Integration

1. **Only 4 processing rules** — need 10+ for meaningful context diversity. Rule_1976 (site style), rule_mastodon_dedup, rule_no_delete, rule_2087 (claim-check). The retriever works but its panoramic view is narrow.

2. **No automatic rule generation** — rules are manually created. LLM-based rule extraction from episodes is the next step. Without it, the dynamic retriever won't grow its context repertoire.

3. **Performance** — adapter creates a second DB connection for context generation. Should reuse the cursor's connection. Minor optimization.

4. **Emotion scoring is basic** — strong emotions detected by keyword matching, not by actual emotion analysis. Placeholder.

5. **Novelty scoring is a placeholder** — always 0.5. Real novelty would compare against recently retrieved items.

## Next Steps (Priority Order)

1. **Fix adapter performance**: reuse cursor's connection for context generation (no second connection)
2. **Request Egor approval** for Option A integration
3. **Prototype LLM-based rule extraction** in consolidation pipeline
4. **Add more manual rules** as stopgap (5-6 more from existing lessons)
5. **Implement real novelty scoring** (track recently retrieved IDs)
