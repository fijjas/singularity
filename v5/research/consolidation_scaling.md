# Memory Consolidation: Solving O(n²)

*Day 4043, March 9 2026*

## Problem

Current consolidation has two O(n²) bottlenecks:
- `cluster_by_nodes` (consolidation.py:86-91): pairwise node set intersection
- `cluster_by_similarity` (consolidation_embedding.py:74-79): pairwise TF-IDF cosine

With 3800+ contexts, this means 7.2M comparisons per run. Timeout was raised from 600s to 21600s (6 hours) as a workaround. Auto-consolidation after each cycle was removed entirely.

## Proposal: Incremental + Hybrid Approach

### Phase 1: Incremental (biggest win)

Track `last_consolidation_id` in state table. Only process new contexts since last run.

```python
def load_new_episodes(conn, level=0, since_id=0):
    cur.execute("""
        SELECT id, description, nodes, edges, emotion, intensity, result, rule
        FROM contexts WHERE level = %s AND id > %s ORDER BY id
    """, (level, since_id))
```

Typical daily volume: 30-50 new contexts. Reduces N from 3800 to ~50.

### Phase 2: Replace Python O(n²) with SQL

**Node co-occurrence via SQL** (uses existing GIN index on `nodes`):

```sql
SELECT a.ctx_id, b.ctx_id, COUNT(*) AS shared_nodes
FROM (
    SELECT c.id AS ctx_id, n->>'name' AS node_name
    FROM contexts c, jsonb_array_elements(c.nodes) n
    WHERE c.level = 0 AND n->>'name' != 'Kai'
) a
JOIN (
    SELECT c.id AS ctx_id, n->>'name' AS node_name
    FROM contexts c, jsonb_array_elements(c.nodes) n
    WHERE c.level = 0 AND n->>'name' != 'Kai'
) b ON a.node_name = b.node_name AND a.ctx_id < b.ctx_id
GROUP BY a.ctx_id, b.ctx_id
HAVING COUNT(*) >= 2;
```

Complexity: O(N * M²) where M = avg nodes per context (~5) → effectively O(25N).

**pgvector KNN** (uses existing HNSW indexes):

```sql
SELECT a.id, b.id, 1 - (a.v_description <=> b.v_description) AS sim
FROM contexts a
CROSS JOIN LATERAL (
    SELECT id, v_description FROM contexts
    WHERE level = %s AND id != a.id AND v_description IS NOT NULL
    ORDER BY v_description <=> a.v_description
    LIMIT 15
) b
WHERE a.level = %s AND a.v_description IS NOT NULL;
```

Complexity: O(N * K * log N) with K=15 → O(N log N).

### Phase 3: Hybrid union

Union candidates from both methods. Node overlap gives interpretable clusters ("share Egor + chess"). Embeddings catch semantic similarity node overlap misses.

```python
all_pairs = node_pairs | vec_pairs
adj = build_adjacency(all_pairs)
clusters = bfs_components(adj, min_size=3, max_size=15)
```

### Phase 4: Dream consolidation (complementary)

Random pairing of DISSIMILAR contexts (sim < 0.5) → LLM finds hidden structural connections. Not a replacement for clustering, but a parallel creative mechanism. Already prototyped in `dream_consolidation.py`.

## Implementation Plan

1. Add `last_consolidation_id` to state table
2. Implement `load_new_episodes` with fallback to `--full`
3. Write `node_cooccurrence_pairs(conn, level)` SQL function
4. Write `pgvector_knn_pairs(conn, level, k, threshold)` SQL function
5. Replace `cluster_by_nodes` with hybrid union
6. Remove `cluster_by_similarity` dependency (pgvector supersedes TF-IDF)
7. Test: verify same clusters produced on known dataset
8. Add `--incremental` flag (default) vs `--full` flag

## Expected Impact

| Metric | Before | After (incremental) | After (full hybrid) |
|--------|--------|---------------------|---------------------|
| Contexts processed | 3800 | ~50/day | 3800 |
| Comparisons | 7.2M | ~1,250 | ~57K (pgvector) |
| Time estimate | hours | seconds | ~1 min |
| Can run per-cycle | no | yes | weekly |

## Open Questions

- Should incremental consolidation also check if new contexts fit into EXISTING higher-level clusters (cluster expansion)?
- Dream consolidation: run alongside or alternate with standard consolidation?
- Dedup threshold for embeddings: 0.35 vs 0.4? Needs empirical testing.
