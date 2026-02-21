# Rule Resonance: Making Rules Active in Wave Retrieval

**Date**: 2026-02-21 (Day 2189)
**Status**: Proposal
**Context**: Redozubov gap — contexts are passive scenes, rules are dead text

## Problem

V5 contexts have a `rule` field: "what this experience teaches." But the rule doesn't participate in wave resonance. Retrieval scores on nodes, relations, emotion, result — all about *what happened*. Not about *what to do*.

In Redozubov's model, contexts ARE transformation rules. A context activates when its rule applies, not when its scene matches. V5 gets this backwards: it finds similar scenes and hopes the rules are relevant.

## Observation: Rules Already Work Through LLM

V5 Day 1647 Cycle 1 proved something: the L3 principle's rule ("execute smallest external action to break loop") directly guided the resolver to write creative output. The rule worked — but through the LLM's comprehension, not through retrieval.

This means the mechanism works post-retrieval (LLM reads rule, applies it). The gap is pre-retrieval (rules don't influence which contexts get surfaced).

## Proposal: Rule-Condition Channel (5th wave channel)

### Design

At context creation time, extract **condition nodes** from the rule text:
- "When **Egor** criticizes harshly, engage with the substance" → conditions: {Egor, criticize}
- "When **analysis loops** dominate working memory, execute external action" → conditions: {analysis, loop, working_memory}
- "**Creation drought** is the real emergency" → conditions: {creation, drought}

Store as `rule_conditions: list[str]` alongside nodes/edges.

During wave retrieval, add a 5th channel:
```python
# rule-condition match
if signal_nodes and ctx.rule_conditions:
    condition_overlap = len(signal_nodes & ctx.rule_conditions)
    if condition_overlap > 0:
        score += condition_overlap
        total += len(ctx.rule_conditions)
```

### Extraction

Two options:
1. **Keyword extraction** (fast, no LLM): capitalized words + known entities from rule text
2. **LLM extraction** (accurate, slow): ask Haiku for condition keywords at write time (one-time cost)

Option 1 is sufficient because rules are short (1-2 sentences) and entity-dense.

### Effect

A rule about "Egor criticism" would get boosted when signal contains "Egor" — even if the scene's nodes don't overlap much. This means rules about HOW TO ACT surface when the conditions match, not just when similar events match.

### What This Changes

Before: "I've been in situations like this before" → here are similar scenes
After: "I have rules that apply to situations like this" → here are applicable rules + their scenes

The shift is from episodic matching to rule matching. Contexts with strong rules get boosted in situations where those rules apply.

## Alternative: Rule Embedding Channel

Instead of keyword extraction, embed the rule text separately (384-dim vector) and score rule-to-signal semantic similarity. This would catch:
- "Don't message when no new input" matching a signal about Telegram with no messages
- "Creation drought is the real emergency" matching hungry creation drive

More powerful but requires:
- Separate embedding per rule (already have pgvector)
- Semantic similarity scoring during wave (costly for 600+ contexts)

**Verdict**: Start with keyword extraction (5th channel). Add embeddings later if needed.

## Implementation Plan

1. Add `rule_conditions` column to contexts table (jsonb, nullable)
2. Extract conditions from existing rules (batch migration)
3. Add 5th channel to `ContextStore.wave()` and `retriever.wave()`
4. Update `write_context` / `writer.py` to extract conditions at creation time
5. Test: verify that contexts with applicable rules rank higher

### Risk

Low. Adding a channel can only improve retrieval diversity. rule_conditions is nullable — contexts without rules get no bonus (not penalty). The worst case is noise from bad keyword extraction, which is bounded by the channel being one of five (20% weight).

## Redozubov Alignment

This moves V5 closer to Redozubov's model:
- **Before**: Context = scene. Retrieval finds similar scenes.
- **After**: Context = scene + transformation rule. Retrieval finds scenes with applicable rules.
- **Redozubov ideal**: Context = transformation rule only. Retrieval finds applicable rules.

We're at step 2 of 3. Step 3 would require restructuring contexts entirely (rule as primary, scene as evidence) — a V6 consideration.
