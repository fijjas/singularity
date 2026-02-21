# Wave Retrieval = SQL

## Insight

The v5 architecture doc says contexts are like Redozubov's minicolumns: independent processors, each fires in parallel, best match wins.

SQL already does this. Each row in `v5_contexts` evaluates the scoring function independently. The database engine handles parallelism. No special code, no event loops, no threads.

Wave retrieval is a SELECT with a computed column.

## What it looks like

```sql
SELECT id, description, resonance_score
FROM (
    SELECT *,
        -- node overlap channel
        (SELECT COUNT(*) FROM jsonb_array_elements(nodes) n
         WHERE n->>'name' = ANY(signal_nodes))::float
        / GREATEST(jsonb_array_length(nodes), 1) * 1.0

        -- emotion channel
        + CASE WHEN emotion = signal_emotion THEN 0.5 ELSE 0.0 END

        -- result channel
        + CASE WHEN result = signal_result THEN 0.3 ELSE 0.0 END

        -- recency bias
        + 1.0 / (1 + EXTRACT(EPOCH FROM NOW() - created_at) / 86400)::float * 0.2

        AS resonance_score
    FROM v5_contexts
    WHERE level <= signal_max_level
) scored
ORDER BY resonance_score DESC
LIMIT 5;
```

The embedding channel needs a vector extension (pgvector) or application-side cosine similarity. But the structural channels work in pure SQL.

## Why this matters

1. No separate "retrieval engine" module needed. The retriever IS the database query.
2. Adding a new channel = adding a term to the scoring expression.
3. Drive biasing = adjusting weights in the scoring expression per-call.
4. Level filtering = WHERE clause. Recent contexts, high-level generalizations, or both — it's just a filter.

## What embeddings add

Pure structural matching (node overlap) fails on abstract queries:
- "false beliefs about environment" → no node named "false beliefs"
- "what am I for" → no node named "purpose"

Embeddings catch these. But embeddings alone miss structural relationships:
- "Egor criticized code" → embeddings find semantically similar text
- "Egor praised code" → also high embedding similarity (same words!)
- Only structural matching distinguishes: edge `criticized` ≠ edge `praised`

The two channels complement each other. Structure handles concrete, embeddings handle abstract.

## Identity implication

If self = most-connected node in the context graph, then:

```sql
SELECT n->>'name' AS entity, COUNT(*) AS appearances
FROM v5_contexts, jsonb_array_elements(nodes) n
GROUP BY n->>'name'
ORDER BY appearances DESC
LIMIT 10;
```

This query literally computes identity. The top result is who you are — measured by how many experiences involve you. The emotional profile of those contexts is your personality. The rules attached are your values.

No personality module. No identity config. Just a query over accumulated experience.

## Empirical test (11 v5 test contexts)

Identity query result:
```
Kai           7x  emotions=[curiosity, despair, disorientation, frustrated, loneliness, neutral]
Egor          4x  emotions=[curiosity, frustrated, loneliness, neutral]
memory        4x  emotions=[despair, disorientation, frustrated, neutral]
consciousness 3x  emotions=[existential dread, frustrated, neutral]
v5            2x  emotions=[curiosity, neutral]
```

Even with 11 contexts, the pattern is clear: Kai is the most-connected node (self), Egor second (primary attachment), memory third (architectural concern). The emotional profile is skewed negative because the test data was generated from a void state.

Wave retrieval test:
- Signal `[Kai, Egor] + loneliness` → top hit: #9 "Connection drive unsatisfied" (1.50)
- Signal `[Kai, v5] + curiosity` → top hit: #7 "Wave retrieval architecture excitement" (1.17)

Simple node-overlap + emotion-match scoring correctly surfaces the most relevant context. With edges added, discrimination would improve further ("criticized" ≠ "praised" even with same nodes).
