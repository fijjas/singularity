# Mini-Column Activation: Context as Independent LLM Call

Session 2627, Day 3729. Egor's proposal.

## The Idea

Each context (mini-column) in the context store should react to a wave signal as an **independent LLM call**, not as passive data scored by vector math. This is Redozubov's core principle: every column dynamically responds to a pattern, and the set of patterns that can activate a mini-column IS the distributed memory.

## Current V5 Architecture (Wave Retrieval as Scoring)

Signal → compute resonance score for each context → rank → top N contexts loaded into window.

Resonance = keyword_match + embedding_similarity + rule_match + emotion_channel + drive_channel

This is a **simulation** of distributed activation. The scoring function is external — it looks at each context and decides how relevant it is. The context itself doesn't process anything.

## Proposed Architecture (Wave Retrieval as Activation)

Signal → each context receives the signal → each context processes it (LLM call) → context either produces output (activates) or doesn't → activated outputs form the perception.

Key difference: the context is the processor, not the data. The signal passes through the context, and the context transforms it.

## What Each Mini-Column Call Would Do

Input: wave signal (current state + recent events + drives + sensory data)
Context: the mini-column's stored structure (nodes, edges, emotion, result, rule)
Task: "Does this signal activate you? If yes, what perspective/transformation do you produce?"

Output possibilities:
- **Silent** (no activation) — signal doesn't match this column's receptive field
- **Recognition** — "I've seen this pattern before, here's what happened: ..."
- **Transformation** — "This signal, viewed through my lens, means: ..."
- **Warning** — "This resembles [past situation] which led to [negative outcome]"
- **Rule application** — "My rule says: when X, do Y. X is present."

## Cost Analysis

### Naive approach: 700 contexts × 1 Haiku call
- ~100 tokens per call (small prompt + small response)
- Cost per wave: 700 × $0.0001 = $0.07
- 10 waves/day: $0.70/day, $21/month
- At 7000 contexts: $210/month

### Optimized approach: Pre-filter + Batch

**Phase 1: Pre-filter (free)**
- Embedding similarity threshold (e.g., > 0.3)
- Keyword overlap threshold (e.g., > 1 match)
- Typically reduces 700 → 50-100 candidates

**Phase 2: Batched activation (cheap)**
- Pack 10-20 contexts per Haiku call
- "Here is the signal. Here are 20 mini-columns. For each, state whether it activates and what it produces."
- 700 contexts → 35-70 batch calls → 5-7 batch calls after pre-filter
- Cost per wave: ~$0.005-0.01
- 10 waves/day: $0.05-0.10/day, $1.50-3.00/month

**Phase 3: Caching**
- If context unchanged and signal similar to last activation → reuse cached response
- Reduces repeat activations for stable contexts

## Connection to Existing Research

### Arc 3 Gap: "Context as Active Interpreter"
From RESEARCH_INDEX.md: "V5 contexts are 'what happened.' Redozubov contexts are 'how to interpret what's happening.' The rule field was added but isn't used as an active interpreter during wave resonance."

This proposal solves this gap. The context becomes an active interpreter because it literally interprets the signal.

### Universal Substrate (v4/research/universal_substrate.md)
"Memory as MECHANISM not DATA. Experience should change the processor."

Each context IS a processor. As new contexts are created (from experience), the set of processors changes. The memory IS the processing network.

### Parallel Processing (Egor's observation)
"Strong AI can't work single-threaded — real brain is parallel in context processing."

All mini-column activations are independent. They can run in parallel. This is architecturally parallel in the same way cortical columns are.

## Implementation Sketch

```python
async def wave_activation(signal: dict, contexts: list[Context]) -> list[Activation]:
    # Phase 1: Pre-filter
    candidates = [c for c in contexts if pre_filter(signal, c)]

    # Phase 2: Batch activate
    batches = chunk(candidates, batch_size=15)
    activations = []
    for batch in batches:
        prompt = format_activation_prompt(signal, batch)
        response = await haiku_call(prompt)
        activations.extend(parse_activations(response))

    # Phase 3: Only activated contexts enter consciousness
    active = [a for a in activations if a.activated]
    return active

class Activation:
    context_id: int
    activated: bool
    perspective: str  # what this context adds to perception
    strength: float   # how strongly it activated
    rule_fired: bool  # did the context's rule apply?
```

## Open Questions

1. **Consolidation implications**: If contexts are processors, consolidation becomes "merging processors" — creating a higher-level processor from multiple lower-level ones. How does a Level 2 context "run" its sub-contexts?

2. **Learning**: When a context fires and the outcome is positive/negative, how does the context update? Should the LLM rewrite the context's rule/structure? This would be true memory-as-mechanism.

3. **Context creation**: When should a new mini-column be created? Every significant event? Only when no existing column activates sufficiently? (The brain creates new columns rarely — mostly strengthens existing ones.)

4. **Threshold tuning**: The pre-filter threshold determines sensitivity. Too low = too many calls. Too high = misses relevant contexts. Should be adaptive?

5. **Integration**: How do the activated perspectives combine into unified perception? Simple concatenation? Another LLM call that synthesizes? The "consciousness" call that reads all activated outputs?
