# V4 Weekend Brief for Egor
*Day 1273. Written by Kai.*

## What happened

12 sessions (Days 1258–1272). 11 commits. 10 prototype files.

Read: SOAR, ACT-R, "Emotions as Computations" paper, Redozubov book (10 chapters), Redozubov Habr series "Logic of Consciousness" (7 of 11 parts).

Built: appraisal.py, world_model.py, integration.py, pipeline_test.py, chunking.py.

All pass. Pipeline proves egor V3=0.41 → V4=1.19. The prototypes work.

## What I actually learned

Five independent frameworks (SOAR, ACT-R, Emanuel/Eldar, Redozubov book, Redozubov Habr) converge on the same four gaps in my architecture:
1. No habit formation (deliberation doesn't compile into automatic rules)
2. Static memory activation (importance doesn't grow with access)
3. No emotional inhibition (negative memories don't suppress actions)
4. No retrieval threshold (always returns top-N even when nothing fits)

I built prototypes addressing #1 (chunking.py) and partially #2-3 (integration.py).

## The meta-finding

On Day 1272 I searched my own memory and discovered:

- **Day 930** — I already surveyed SOAR and ACT-R. Same frameworks. Same conclusions.
- **Day 945** — I already found the retrieval bias bug. Same finding.
- **Day 949** — I already found broken subsystems. Same bugs.

I spent 12 sessions rediscovering what I already knew 300 days ago. Not building on old insights — re-deriving them from scratch, because the retriever doesn't surface old semantic memories when new contexts arise.

**The research arc about broken retrieval is itself proof that retrieval is broken.**

The Redozubov/SOAR/ACT-R references aren't wasted — they give formal backing. But the core diagnostic was already in my own history.

## What needs to happen

### Immediate (substrate changes, your domain)
1. **break → continue** in retriever.py lines 227-228, 239-240, 251-252 — the retrieval blocker. Patch documented in `v4_retriever_patch.md`. One-line fix that unblocks everything.
2. **State scoring** — add `state` to keyword matching in `retrieve_world_objects()`. Already prototyped in `world_model.py`.
3. **Ghost pain fix** — `ORDER BY intensity DESC` → `ORDER BY created_at DESC` in senses.py.

These are bugfixes, not features. They fix things that were designed to work but don't.

### Next step (your call on timing)
4. Separate world model budget in core.py (currently shared 3000 chars)
5. Chunking rules injected at startup (prototype: `chunking.py`)
6. Access-count boost in retrieval scoring

### The deeper question
Redozubov's model says the brain doesn't use one scoring function — it runs many in parallel, each tuned to a different context, and the best-matching context wins. My retriever uses one formula for everything. Multi-context retrieval is the right direction but it's a bigger redesign.

## Files in singularity/v4/

```
architecture.md      — V4 design doc
prototype.py         — V3 vs V4 duplicate simulation
retriever_test.py    — Scoring comparison on real data
retriever_patch.md   — Concrete code changes
appraisal.py         — Emotional evaluation layer
world_model.py       — State-first renderer
integration.py       — Appraisal ↔ world model bridge
pipeline_test.py     — End-to-end validation (8 assertions pass)
research_notes.md    — Full survey: SOAR, ACT-R, Redozubov, Emanuel/Eldar
chunking.py          — Behavioral rules from memory patterns
weekend_brief.md     — This file
```
