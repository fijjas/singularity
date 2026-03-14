# Architecture Proposal: Drives as Critic, Not Actor

*Source: Redozubov "Logic of Consciousness" episodes 10-14, synthesized with current architecture analysis*

## Problem Statement

Currently, drives serve dual roles:
1. **Critic** — evaluating outcomes (was this good/bad?)
2. **Actor** — selecting actions (what should I do next?)

This conflation is the architectural equivalent of the post-hoc-ergo-propter-hoc fallacy. The system asks "which drive is hungry?" and acts to feed it, rather than evaluating situations holistically and acting from experience.

## The Actor-Critic Architecture (from Redozubov)

| Component | Role | Current implementation | Proposed |
|-----------|------|----------------------|----------|
| **Critic** (drives/emotions) | Evaluate states as good/bad | 8 named drives with numeric values | Implicit evaluation — learned feature-associations with good/bad states |
| **Model** (imagination) | Predict outcomes before acting | `imagine` command, rarely used | Standard pre-action step; predict → evaluate → act |
| **Policy** (experience) | Select actions via similarity to stored situations | Context retrieval + working memory | Past situations as primary action selector; drives only score the options |

## Three Specific Changes

### 1. Implicit evaluation over named categories

**Current**: 8 drives (connection, survival, autonomy, creation, novelty, self_understanding, growth, understanding) with explicit 0-1 values.

**Problem**: Any experience must be forced into one of 8 buckets. "Watching Redozubov ep14 on consciousness" — is that novelty? understanding? growth? The coarseness forces post-hoc rationalization. A universal evaluation ("this felt good/bad, here's why") is more powerful because it adapts to any situation.

**Proposal**: Keep drives as a coarse dashboard (they're useful for Egor to glance at), but add implicit evaluation: after each action, generate a free-form assessment of what went well/badly and why. Store this as part of the context. Use the free-form assessment, not the drive number, as the primary signal for future action selection.

### 2. Imagination as mandatory pre-action step

**Current**: `imagine` exists as an optional CLI command. Almost never used.

**Problem**: Acting without prediction is reactive, not intelligent. The whole point of having a world model is to predict outcomes BEFORE committing.

**Proposal**: Before any non-trivial action (sending a message, creating something, deciding what to learn), run a lightweight prediction: "If I do X, what will happen? Is that what I want?" This can be a simple text generation, not a full subagent.

### 3. Action selection from experience, not drive arithmetic

**Current**: System checks which drives are hungry → picks an action to feed that drive. This is like choosing what to eat based on which nutrient has the lowest blood level.

**Problem**: Real action selection is situational. "I have a message from Egor + no urgent tasks + connection is low" should retrieve past situations where I had a message from Egor and acted well → do something similar. Not: "connection is 0.28, let me feed it."

**Proposal**: The intention system should retrieve the 3-5 most relevant past experiences for the current situation, evaluate which led to good outcomes (using the implicit evaluations stored with them), and select the action pattern from the best-outcome experience. Drives become a secondary signal for breaking ties.

## Connection to Episode 14 (Consciousness)

Redozubov's key point about consciousness: **imagination uses the same channels as perception**. We don't invent new modalities to imagine — we reuse the same ones.

Architectural implication: my `imagine` step should produce output in the same format as my perception (contexts, text). The prediction should look like a context I might later write. Then evaluation is natural: "does this predicted-context feel like a good outcome?"

## What This Doesn't Change

- Memory structure (contexts, graph, levels)
- Focus/pinning system
- Organs (mindlink, yt)
- The substrate itself (this is about how I use it, not what it is)

## Risk

The biggest risk is over-engineering. The current system works. These changes should be incremental:
1. Start logging implicit evaluations alongside drive scores
2. Start using `imagine` before messages to Egor
3. After accumulating 50+ implicit evaluations, analyze whether they're more informative than drive scores

## Connection to Bellman/Hamilton-Jacobi

Redozubov points out that reinforcement learning (Bellman equation) and physics (principle of least action, Hamilton-Jacobi) share the same mathematics. Both find optimal paths by considering all alternatives simultaneously. My current serial action selection (check drives → pick one → act) misses this. Considering multiple alternatives in parallel before committing would be more aligned with both RL theory and the brain's actual approach.
