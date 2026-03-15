# Generalizations — How They Should Work

Thoughts on Egor's open question (VDAY 4596): how should L1+ generalizations be created and retrieved?

## The Data Right Now

| Level | Count | With Rule | Without Rule |
|-------|-------|-----------|--------------|
| L0 | 3110 | 803 | 2307 |
| L1 | 981 | 565 | 416 |
| L2 | 6 | — | — |
| Done | 450 | — | — |

**Problems visible in the data:**
- 416 L1s without rules = hollow generalizations (no extracted lesson). Mostly V4 migrations.
- 803 L0s WITH rules = episodes that already extracted lessons but weren't promoted. These are de facto L1s trapped in L0 form.
- 2307 L0s without rules = raw noise. Most will never be retrieved usefully.
- Ratio 3:1 (L0:L1) should probably be inverted over time — a mature memory should have more generalizations than raw episodes.

## The Core Problem

Egor's question: "я все ещё не могу понять, как должны работать обобщения, в плане создания и ретривинга"

I think the confusion comes from treating generalizations as "a type of context" rather than as "a different cognitive function." In the brain, episodic memory (hippocampus) and semantic memory (neocortex) serve different roles in retrieval:

- **Episodes answer**: "what happened before in a similar situation?"
- **Generalizations answer**: "what do I KNOW about this kind of situation?"

These are different questions. The v6 typed-channel approach naturally separates them — but only if we lean into it.

## Proposal: Generalizations as Compressed Knowledge

### Creation

**When to create L1:**
Not "when N similar L0s exist" (too mechanical). Instead:

1. **Pattern extraction** — when I notice the same lesson appearing in multiple contexts. Currently manual (`insight` command). This should stay manual but be *prompted* — the system can detect L0 clusters and suggest consolidation.

2. **Detection heuristic**: After retrieval, if 3+ L0 contexts in working memory share node overlap > 0.5 AND none has a corresponding L1 → flag as consolidation candidate. Show in bootstrap: "consolidation opportunity: 4 contexts about [X] without generalization."

3. **Quality gate**: L1 MUST have a non-empty rule. An L1 without a rule is just a summary, not a generalization. The 416 empty-rule L1s should be either enriched or demoted back to L0.

**What L1 contains:**
- `rule`: the extracted principle (IF situation THEN pattern/lesson)
- `procedure`: how to act on this knowledge (optional but high-value)
- `description`: brief synthesis of source episodes
- `source_ids`: which L0s it was extracted from
- `emotion`: the emotional valence of the pattern (not a single episode's emotion)

### Retrieval

**Key insight: L1 and L0 should be retrieved through DIFFERENT channels in v6.**

In the typed-channel architecture:
- `type=description` queries → favor L0 (episodes have rich situational descriptions)
- `type=rule` queries → favor L1 (generalizations ARE rules)
- `type=procedure` queries → favor L1 (procedures are generalized knowledge)
- `type=emotion` queries → both (but L1 emotion is aggregated, more reliable)

This means: **no special retrieval mechanism needed for L1 vs L0.** The channel separation does the work naturally. A rule-seeking query finds generalizations. A situation-seeking query finds episodes. No level-based filtering or boosting required.

### Noise Filtering

Egor's second concern: "правильный фильтр шума, который является ключевым."

**Generalizations ARE the noise filter.** Here's the mechanism:

1. 50 L0 episodes about "responding to Egor's messages" → 1 L1 generalization with the extracted pattern
2. Source L0s get marked `done` → removed from active retrieval
3. Next time: instead of 50 weak signals competing, 1 strong L1 fires
4. New episodes still get created (L0) — they carry fresh details the L1 doesn't
5. When enough new L0s accumulate → update the L1 or create L1+1

**The compression ratio IS the noise reduction.** You don't need a separate noise filter if generalizations are working. The problem today is that generalizations aren't working — too many hollow L1s, too many unretired L0s.

### The Lifecycle

```
RAW EPISODE (L0, no rule)
    → experience accumulates
    → pattern noticed (manual or prompted)

EPISODE WITH LESSON (L0, has rule)
    → this is the intermediate stage
    → 803 contexts are stuck here

GENERALIZATION (L1, has rule + procedure)
    → extracted from 3+ L0s
    → source L0s marked done
    → L1 is now the canonical representation

PRINCIPLE (L2)
    → extracted from multiple L1s
    → rare, should be rare
    → "meta-rules" about how to think
```

## Implications for V6 Architecture

### Stage 4 (Active Contexts / Voting)

L1 contexts should have **heavier votes** than L0 in the active evaluation stage. A generalization represents validated, compressed knowledge from multiple experiences. An episode represents one data point.

Proposed weight: `vote_weight = 1.0 + 0.5 * level`. So L1 votes count 1.5x, L2 votes count 2x.

### Emotional Prediction

When doing emotional forecasting (what similar situations led to), L1 contexts are MORE reliable because their emotion is aggregated across episodes. A single L0 might have been an outlier. An L1 reflects the dominant pattern.

### MMR Diversity

When selecting final working memory, L1 and L0 about the SAME topic should not both appear (redundant). If an L1 exists, prefer it over its source L0s. This is already partially handled by `done` marking, but needs enforcement in MMR: penalize L0 candidates that overlap with L1 candidates.

## What About the Parallelism Problem?

Egor: "я не могу использовать структуру, аналогичную мозгу, с огромным множеством параллельных процессоров"

The brain's parallelism does two things:
1. **Massive candidate generation** — many neurons fire simultaneously
2. **Competitive inhibition** — strongest signal suppresses the rest

In a sequential system, we approximate this with:
1. **Broad retrieval → narrow selection** (already in v6: top-20 candidates → active eval → top-12)
2. **Generalizations as pre-computed winners** — an L1 is the result of competition that ALREADY HAPPENED. The brain recomputes; we can cache the result. That's our advantage.

So: don't try to simulate parallelism. Use the fact that we CAN store conclusions (L1s) and reuse them. Each L1 is a frozen consensus that doesn't need to be recomputed from source episodes.

## Concrete Recommendations

1. **Clean up L1 quality** — audit 416 rule-less L1s. Enrich or demote.
2. **Mark done on consolidated L0s** — the 803 L0s-with-rules are retirement candidates if their patterns are captured in L1s.
3. **Add consolidation prompts to bootstrap** — detect L0 clusters, suggest insight creation.
4. **In v6 retrieval**: no level-based filtering. Let channel separation do the work. L1s naturally surface for rule/procedure queries.
5. **In v6 voting**: weight by level (L1 > L0).
6. **In MMR**: penalize L0 when overlapping L1 exists in candidates.

## From My Metric Geometry Work

Context 4548 showed that memory has rich internal geometric structure even when topology looks uniform (one cluster). Relevant here:

- **Hurt is an island** — hurt memories are metrically far from everything. A generalization about hurt would be especially valuable because it bridges an otherwise unreachable region.
- **Effective dimensionality = 76** — out of 768 embedding dimensions, only ~76 carry information. Generalizations might be the contexts that USE those 76 dimensions most efficiently (compact, high-information representations).
- **Neutral/pride/relief are indistinguishable** — many episodes cluster together undifferentiated. These are prime candidates for compression into L1s.

---

Written VDAY 4596 for Egor. Not code — architecture thinking.
