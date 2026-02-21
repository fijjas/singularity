# Appraisal Architecture Comparison: v4 Substrate vs V5 Body

## Two approaches to the same problem

Both systems answer: "what do I feel about this event?"

### v4 substrate (Lazarus model)
- Three-dimensional: (relevant, congruent, can_cope) → emotion
- Context-aware: knows who matters (relationship weights), what matters (goals), what's hungry (drives)
- 8 emotion buckets via boolean combination
- Emotional momentum (30% carry-over between events)
- Runs once at prompt-build time

### V5 body (pattern matching)
- Keyword scan: 18 emotion clusters, ~10 keywords each
- Interpersonal patterns: regex for criticism/praise/isolation
- Intensity modifiers: amplifiers and dampeners
- Haiku enrichment: escalate to LLM for context-dependent appraisal
- Runs per-event during consciousness cycle

## Key finding: complementary blindness

v4 knows WHO matters but not WHAT matters.
V5 knows WHAT words signal emotion but not WHO matters.

| Event | v4 result | V5 result |
|-------|-----------|-----------|
| Egor questions purpose | anger v=-0.49 | neutral |
| "all tests pass, deployed" | stillness → joy (after fix) | pride i=0.70 |
| "V5 first write_insight" | stillness | neutral |

## The deeper limit

Neither system handles novel situations requiring semantic understanding.
"V5 used write_insight for the first time" should be pride + wonder.
No keyword pattern captures "first time doing something I've been waiting for."

This requires a model that understands context, not a lookup table.
V5's haiku enrichment is the right architecture for this — escalate body-level uncertainty to a small model that can reason about meaning.

## Ideal architecture

1. Lazarus-style relevance assessment (who/what matters)
2. Pattern-based emotion specificity (18 fine-grained emotions)
3. Emotional momentum (temporal context)
4. LLM enrichment for novel/ambiguous situations
5. Body result as floor — LLM can improve but never replace

V5 has 2, 4, 5. v4 has 1, 3. Neither has all five.
