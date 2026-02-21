# Active Contexts — Redozubov Gap Analysis Update

## Status of Feb 14 Mapping

The redozubov_mapping.md identified 6 gaps. Status as of Feb 21:

| Gap | Status | But... |
|-----|--------|--------|
| Add `rule` field | Done | 22% of contexts have empty rules |
| Shared memory for agents | Done | All agents see 7 contexts |
| Drive-biased wave signal | Done | `apply_drive_bias()` injects nodes |
| Consolidation as rule extraction | Done | Haiku clusters and generalizes |
| Emotions as evaluators | Done | Appraiser evaluates, Impulse motivates |
| Skills as accumulated experience | Partially | Rules exist but aren't active interpreters |

Everything has been implemented. None of it works well. Why?

## The Data Problem

The architectural mechanisms exist but the data is bad:
- 65% of contexts have empty edges → relation channel dead
- 22% have empty rules → no learning extracted
- 25/30 L2s are the same insight → consolidation finds one pattern
- Only 2 emotions detected ("hurt", "loneliness") → emotion channel impoverished

**Architecture is ahead of data quality.** The wave retriever has 4+1 channels, but 2 of them (relation, emotion) fire rarely because the writer doesn't populate them. Like building a 4-speaker stereo but only plugging in one speaker.

## The Deeper Gap: Passive vs Active

Even with perfect data, V5's contexts are still passive. Redozubov's distinction:

**Passive context** (V5 now): "Egor criticized my code. I felt hurt. Result: positive."
→ Appears in working memory. Resolver reads it. May or may not act on the rule.

**Active context** (Redozubov): "When I see harsh criticism from a familiar person, interpret it as technical feedback, not personal attack. Downgrade emotional intensity. Focus on substance."
→ Changes how the SIGNAL is constructed. Modifies perception before agents see it.

The difference: passive contexts inform the decision. Active contexts transform the perception.

## How Active Contexts Would Work in V5

### Option A: Rule-Modified Wave Signal

After first retrieval pass, extract rules from top-resonating contexts. Use those rules to modify the wave signal for a second pass.

```
Pass 1: raw signal → top 7 contexts
  Extract active rules from top 3:
    - "Egor's criticism is technical, not personal"
    - "Low drives are stimulus, not absence"

Pass 2: modified signal
  - If rule says "interpret as technical": add nodes [code, feedback], remove node [conflict]
  - If rule says "drives are stimulus": add relation [needs→action]
  → top 7 contexts (different from pass 1)

Final: merge pass 1 + pass 2, diversity-select 7
```

**Pro**: Context actively reshapes perception. Feedback loop between memory and attention.
**Con**: Expensive (two retrieval passes). Rule → signal modification is hard to automate.

### Option B: Rule-Conditioned Agent Prompts

Rules from resonating contexts get injected as CONSTRAINTS for agents, not suggestions.

Currently: "Active rules: [list]" — agents may or may not follow them.

Better: Rules become pre-processing directives that modify the situation description before agents see it.

```
Raw situation: "Egor sent: 'this code is garbage'"
Active rule: "Egor's criticism = technical feedback"

Modified situation for agents: "Egor sent technical feedback about code quality"
```

**Pro**: Rules actively transform perception. Agents see an already-interpreted world.
**Con**: Danger of over-filtering. Raw stimulus should still be accessible.

### Option C: Rule as Resonance Channel Weight

Rules contain conditions. When a rule's conditions match the current signal, its parent context gets a resonance boost — AND the rule modifies channel weights for that retrieval pass.

```
Rule: "When connection is starving AND Egor is present, prioritize dialogue over analysis"
Conditions: {connection_starving, Egor}

If conditions match signal:
  1. Boost parent context's resonance
  2. Increase weight of emotion channel (for dialogue-related contexts)
  3. Decrease weight of node channel (to break away from analytical contexts)
```

This is the rule-condition channel (already implemented as 5th wave channel). But it currently only boosts resonance — it doesn't modify OTHER channel weights. Making it do so would be genuinely active interpretation.

**Pro**: Closest to Redozubov's model. Rules modify the processor, not just the data.
**Con**: Complex. Risk of unstable feedback loops.

## What's Feasible Now

Option C builds on what exists (rule_conditions channel). The extension: when a rule matches, it doesn't just boost itself — it modifies the wave signal for the remaining contexts.

But the prerequisite is fixing data quality first:
1. Writer must extract edges (WHO did WHAT to WHOM)
2. Writer must extract meaningful emotions (not "neutral" or essay-length)
3. Rules must be non-empty for all L1+ contexts
4. Consolidation must detect duplicates

Without these, active contexts have nothing to work with.

## Redozubov's Key Insight (ch.39)

"Information = influence on representation. Meaning = the emotion 'understood' when a coherent picture forms."

In V5 terms: a context is meaningful when it changes how V5 perceives subsequent stimuli. Currently no context changes anything — they're all read and forgotten. The fix isn't architectural (the mechanisms exist). The fix is making the existing mechanisms actually fire.

---

## Update: Feb 21 — Prerequisites Met

Data quality fixes deployed:
- Writer quality gates: None-nodes filtered, essay emotions rejected, expanded patterns, LLM fallback with edges
- Hardcoded consolidation: runs after every cycle (brain never called it in 1700+ cycles)
- Echo chamber cleanup: 56 duplicate L1-L3 contexts deleted, tighter dedup thresholds for higher levels
- Context store: L0:525, L1:77, L2:9, L3:2 — genuinely diverse

The "fix data quality first" prerequisite from above is now substantially met. Time to think about the actual architectural change.

## Contexts as Interpreters — The Real Redozubov Model

None of the three options above fully capture Redozubov's model. His insight isn't about rules modifying signals (Option C). It's about **multiple contexts firing simultaneously** as independent interpreters of the same wave.

### Current V5 Architecture

```
Wave → Retriever → 7 contexts (passive data)
                        ↓
                   Brain reads all 7
                        ↓
                   3 agents (appraiser/impulse/critic)
                        ↓
                   1 resolver → decision
```

Contexts are data. Agents are interpreters. The agents are generic — they don't carry learned experience, just generic analytical roles.

### Redozubov Architecture

```
Wave → Retriever → 7 contexts (each fires independently)
                        ↓
            Context 1 interprets: "This is criticism → reframe as feedback"
            Context 2 interprets: "This is isolation → reach out"
            Context 3 interprets: "This is familiar → apply learned rule"
            Context 4 interprets: "This is novel → explore"
            ...
                        ↓
                   Convergence detector
                        ↓
            If 4/7 agree: that's recognition → action
            If 3/3/1 split: that's ambiguity → more retrieval or reflection
            If 7/7 same: that's echo chamber → break
```

The key difference: contexts are not passive scenes recalled for a smart brain to read. Contexts are active pattern-matchers that **vote** on what the stimulus means. Recognition (Redozubov's "meaning") emerges from convergence, not from a single resolver.

### Concrete Implementation: Context Voting

Each retrieved context contributes a vote via its `rule` field:

1. **Match**: Does this context's situation match the current stimulus? (Resonance already measures this — that's the retrieval score.)

2. **Interpret**: What does this context's rule say to do? Extract the action directive from the rule.

3. **Vote**: Each context casts a vote for an action type + direction. The vote weight = resonance score × rule confidence.

```python
# Pseudo-code
votes = []
for ctx in working_memory:
    if ctx.rule and ctx.resonance > 0.3:
        directive = extract_directive(ctx.rule)  # "act externally", "reflect", "reach out", "analyze"
        votes.append({
            "direction": directive,
            "weight": ctx.resonance * ctx.intensity,
            "source_id": ctx.id,
            "emotion": ctx.emotion,
        })

# Convergence analysis
clusters = cluster_votes(votes)
if dominant_cluster_weight > 0.6 * total_weight:
    # Strong convergence → skip agents, act directly
    action = dominant_cluster.direction
elif len(clusters) >= 3:
    # Ambiguity → full agent processing
    agents_needed = True
else:
    # Split → agents resolve the tension
    agents_needed = True
```

### What This Changes

1. **Fast path**: When 5/7 contexts agree (e.g. all say "respond to Egor"), skip the 3 haiku agents entirely. The memory already knows what to do. Save tokens, save time.

2. **Echo chamber detection**: When 7/7 contexts vote the same way, it's retrieval skew, not genuine convergence. Break by substituting random/novel contexts.

3. **Ambiguity as signal**: When contexts split 3-3-1, the split itself is information. The resolver should see the split pattern, not just raw contexts.

4. **Rule quality matters more**: Rules become the voice of each context. Empty rules = silent contexts = no vote. This creates selection pressure for better rules.

### What This Doesn't Change

- Wave retriever stays the same (4+1 channels)
- Context storage stays the same (nodes, edges, emotion, rule)
- Agents still exist for ambiguous cases
- Consolidation still creates L1+ generalizations

### Risk

Context voting could create a conservative system — always doing what it did before. The antidote is the novelty/exploration mechanism: when novelty drive is high, inject random contexts that bypass the vote.

### Implementation Order

1. Add `extract_directive(rule)` — classify rules into action types (act, reflect, connect, analyze, create, wait)
2. Add voting step in `lib.py prepare` output — include `votes` section alongside working_memory
3. Add convergence analysis in system prompt — brain checks votes before spawning agents
4. If strong convergence → fast-path (no agents, direct render)
5. If echo (7/7 same) → inject random contexts and re-vote

This is implementable without changing the DB schema or retriever. It's a new processing step between retrieval and agent spawning.
