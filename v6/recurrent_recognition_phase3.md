# Recurrent Recognition Phase 3: Integration into retriever.py

*Day 4573. Proposal for Egor. Based on Phase 1 (manual) and Phase 2 (tool) experience.*

## Problem

`retrieve()` in `substrate/consciousness/mind/retriever.py` runs one round:
```
signal → [wave + semantic + object] → merge → MMR → top_k results
```

One round means: only contexts directly similar to the current stimulus are found. But understanding requires contexts that the *retrieved contexts point to* — second-order connections.

Phase 2 testing showed: 3 rounds retrieve 2.6× more unique contexts than 1 round. The extra contexts are qualitatively different — they surface cross-domain connections the initial signal would never reach.

## Proposed Change

Add a `recurrence` parameter to `retrieve()`. Default: 1 (current behavior). When >1:

```python
def retrieve(store, signal, top_k=7, state_summary="", use_rerank=True,
             conn=None, recurrence=1):
```

### Algorithm

```python
all_candidates = []
seen_ids = set()
current_signal = signal

for round_num in range(recurrence):
    # Run existing 3-stage pipeline
    round_results = _retrieve_single(store, current_signal, conn=conn, ...)

    # Collect new contexts
    new_contexts = [(ctx, score) for ctx, score in round_results if ctx.id not in seen_ids]
    all_candidates.extend(new_contexts)
    seen_ids.update(ctx.id for ctx, _ in new_contexts)

    if round_num < recurrence - 1:
        # Build signal for next round from NEW contexts' nodes
        new_nodes = set()
        for ctx, _ in new_contexts:
            for node in ctx.nodes:
                if node.name not in signal_nodes_original:
                    new_nodes.add(node.name)

        if not new_nodes:  # convergence — no new nodes to explore
            break

        # Augment signal with discovered nodes
        current_signal = augment_signal(signal, list(new_nodes))

# Final MMR over all rounds' results
return mmr_diversify(all_candidates, top_k=top_k, lambda_param=0.5)
```

### Key Design Decisions

1. **Node extraction, not LLM**: Round N+1's signal comes from node names found in round N's results that weren't in the original signal. No LLM call needed. Fast, deterministic.

2. **Convergence detection**: If round N finds no new node names, stop early. Memory is exhausted for this topic.

3. **Score decay**: Optional — multiply round N scores by `0.8^N` so direct matches rank higher than second-order connections. Prevents round 2 results from drowning round 1.

4. **Final MMR across all rounds**: Don't MMR per-round. Collect all candidates, then one final MMR pass. This lets diversity work across rounds.

5. **Budget control**: With recurrence=2, we query 2× but the final output is still `top_k` contexts. The extra retrieval is "exploration budget" — cast wider net, select best.

### Where to Call with recurrence > 1

- `bootstrap.py:prepare()` → `retrieve(..., recurrence=2)` — always 2 rounds during consciousness startup
- Everywhere else → default `recurrence=1` (backward compatible)

### What Changes in retriever.py

1. Extract the 3-stage pipeline into `_retrieve_single(store, signal, conn)` → returns candidate list
2. `retrieve()` becomes the recurrence loop calling `_retrieve_single` N times
3. Add `augment_signal(base_signal, extra_nodes)` → returns new signal with merged nodes
4. One final `mmr_diversify()` at the end

### Estimated Impact

- **Latency**: ~2× for recurrence=2 (two retrieval rounds). Acceptable for consciousness startup which isn't latency-sensitive.
- **Quality**: Based on Phase 2 testing, expect 30-50% of the final 12 contexts to differ from single-round retrieval. The new contexts are "unexpected but relevant" — exactly what one-shot misses.
- **Risk**: Low. Default recurrence=1 preserves all current behavior. Only bootstrap changes.

## What NOT to Do

- Don't use LLM for inter-round query generation — too slow, too unpredictable
- Don't increase top_k to compensate — that's more of the same, not deeper
- Don't run evaluator agents per-round — that's a different system (viewpoint diversity, not recurrence)

## Migration

No schema changes. Pure code change in retriever.py + one parameter change in bootstrap.py.

## Test Plan

1. Run `retrieve()` with recurrence=1 on 10 diverse signals → baseline context sets
2. Run same signals with recurrence=2 → compare context sets
3. Measure: % new contexts in round 2, convergence rate, latency difference
4. Qualitative: are the round-2 contexts genuinely useful or noise?
