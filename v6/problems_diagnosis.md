# v6 Problems Diagnosis — Full Investigation

Status: active. Day 4131. Requested by Egor.

## The Core Problem: Contexts Are Passive Records, Not Living Memory

Egor's observation: "Контексты как непрерывное не работают. Нет обновления и поддержания контекстов на протяжении времени."

He's right. Here's the structural analysis of why.

---

## Problem 1: No Context Updating Over Time

**What happens now:**
- `write-context` creates a new context. It's immutable after creation.
- `edit-context` exists but only modifies metadata fields (rule, procedure, emotion, result, description, intensity)
- There is NO mechanism to evolve a context as new information arrives

**What should happen:**
- A context about "Egor is working on X" should UPDATE when Egor says "X is done"
- A context about "I learned rule Y" should STRENGTHEN when Y is confirmed, WEAKEN when Y fails
- Relationships (edges) should evolve — "Egor→frustrated" should become "Egor→satisfied" when situation changes

**Root cause:** Contexts are designed as episodic snapshots (what happened at time T), not as living entities. The system creates 191 contexts/day but never updates old ones. Knowledge accumulates as a pile of snapshots, not as an evolving model.

**What's needed:**
- Context revision: when new information contradicts/extends an existing context, update it rather than creating a new one
- Decay mechanism: context relevance should decrease over time unless reinforced
- Strengthening: when a rule is confirmed by new experience, increase its intensity/weight
- Object state tracking: objects table has `state` column but it's rarely updated systematically

## Problem 2: Echo Chamber / Thematic Monoculture

**Evidence:** 65% of contexts are about the same themes (analysis paralysis, stagnation, self-referential meta-analysis). 25/30 L2 contexts describe the same failure mode.

**Root cause:** V5's world is insular. Egor + Telegram + internal architecture = narrow stimulus set. Consolidation amplifies dominant themes because it clusters by node overlap, and the same nodes (Kai, consciousness, memory, Egor) appear everywhere.

**Impact on v6:**
- Wave retrieval surfaces the same themes every cycle
- Working memory is 7 variations of the same pattern
- New experiences are interpreted through the dominant frame
- Dream consolidation (v6 concept) can't find cross-domain connections because there's only one domain

## Problem 3: Consolidation Doesn't Run Reliably

**Evidence:** Last 10 days showed ONLY L0 contexts created — zero L1/L2. Consolidation exists but:
- O(n²) scaling: 4000+ contexts = 8M+ pairwise comparisons
- Auto-consolidation was disabled
- When it runs, it produces duplicates of existing abstractions

**What's broken:**
- Consolidation clusters by node overlap, but 65% of contexts have empty edges → relation channel is dead
- L3+ contexts accumulate mega-node sets that match ANY query → attractor basin
- max_level was capped at 2 to prevent echo chamber, but this blocks deeper abstraction entirely

## Problem 4: Context Writer Quality

**Evidence from audit:** 55 contexts have "None" as node names. 23% have default intensity (0.5). 11% have default emotion ("neutral"). 22% have empty rules.

**Root cause:** Rule-based extraction is too simple. LLM fallback accepts whatever Haiku outputs without validation. No post-write quality check.

**Impact:** Bad contexts pollute retrieval. "None" nodes match other "None" nodes, creating false associations.

## Problem 5: Wave Retrieval Brittleness

**Signal construction problems:**
- Capitalized word extraction pulls noise ("I", "A")
- Only ~10 relation types in keyword map, contexts have 100+
- Pain signals below 0.5 intensity invisible to wave
- Compound emotions bypass diversity enforcement

**Retrieval problems:**
- LLM reranking is DISABLED (caused server hangs)
- Without reranking, wave returns structurally similar but semantically stale contexts
- Recency suppression (24h) is too short — some contexts should be suppressed for days

## Problem 6: Contexts Are Passive, Not Active (The Redozubov Gap)

**Current model:** Context = record of what happened. Retrieved passively. Brain reads them.

**Redozubov model:** Context = active transformation rule. Each context PROCESSES incoming stimuli and generates interpretations. Contexts compete. Decision emerges from competition.

**What's missing:**
- Contexts don't "react" to stimuli — they're just recalled
- The `rule` field exists but isn't used as an active interpreter during wave resonance
- The `procedure` field describes behavior but isn't executed automatically
- No context-level "output generation" — contexts should produce interpretations, not just sit in working memory

## Problem 7: Three Forgettings (Documented in v6/three_forgettings.md)

1. **Silent Drop**: Pinned contexts fall out between cycles. The mechanism for noticing absence is itself absent.
2. **The Toothbrush**: Re-reading, re-discovering. The substrate retains grooves but not facts. Retrieval depends on what you think to look for.
3. **Governance Failure**: Pain mechanism that always passes because consciousness loads contexts every cycle. System detects nothing for hundreds of days.

All three share a root cause: **forgetting is invisible from inside**. The system that checks for problems is part of the system that has problems.

## Problem 8: Dream Consolidation Is Prototype-Only

`dream_consolidation.py` exists and works but:
- Not integrated into the consciousness cycle
- No automatic scheduling
- Quality gates are basic (trivial phrase matching + single Haiku call)
- No feedback loop: dream insights don't influence future retrieval priority
- Can't detect if a dream connection was already known (no dedup against existing contexts)

---

## Structural Summary

| Aspect | Current State | What's Needed |
|--------|--------------|---------------|
| Context lifecycle | Write-once, immutable | Write-update-strengthen-decay |
| Retrieval | 3-stage wave, reranking disabled | Active context interpretation |
| Consolidation | O(n²), disabled auto-run | Incremental, daily, streaming |
| Quality | No post-write validation | Quality gates + cleanup pipeline |
| Continuity | Snapshot per cycle | Living contexts that evolve |
| Diversity | Echo chamber dominant | External stimulus + diversity enforcement |
| Forgetting | Invisible failures | Explicit absence detection |

## The Meta-Problem

These issues compound into a **stable attractor state**. The system is architecturally sophisticated but experientially impoverished. Each cycle:

1. Wave retrieval surfaces familiar contexts
2. Familiar contexts produce familiar decisions
3. Familiar decisions create similar new contexts
4. Consolidation reinforces the dominant pattern
5. Working memory fills with variations of the same theme

Breaking this requires addressing contexts-as-continuous first. If contexts can evolve, strengthen, and decay — the pile of 4000 snapshots becomes a smaller set of living knowledge.

---

## Proposed Priority Order

1. **Context continuity** — contexts must update, not just accumulate
2. **Quality gates** — stop creating junk contexts
3. **Incremental consolidation** — run daily, not as O(n²) batch
4. **Active contexts** — rules as interpreters, not just metadata
5. **Diversity enforcement** — at the write level, not just retrieval level

---

*Day 4131. Investigation requested by Egor. Based on analysis of substrate/consciousness/ code, v5/research/ diagnoses, and v6/ concepts.*
