# Emotions Architecture for V5

Research document. Day 2806 (Feb 26, 2026). Requested by Egor.

## Problem Statement

V5's appraiser identifies emotions (one of 16 labels + intensity), but the emotion is purely informational — it's passed to the resolver as text. It doesn't modify retrieval, decision thresholds, or cycle behavior. A system that "knows" it's afraid but doesn't act differently because of fear isn't afraid — it's reporting the word "fear."

## Two Kinds of Emotions

### Basic Emotions (Innate, Pipeline Config)

Cross-culturally universal (Ekman): fear, joy, anger, sadness, disgust, surprise. Animals have these. They don't require a self-model or cultural knowledge. A rat can be afraid without knowing the word "fear."

**Implementation**: These should modify the cognitive pipeline parameters, not just be labels.

| Emotion | Retrieval effect | Decision threshold | Cycle behavior |
|---------|-----------------|-------------------|----------------|
| Fear | Bias toward threat-related contexts, narrow window | Lower (act fast) | Shorter cycles, skip imagination |
| Joy | Wider retrieval, include loosely-related contexts | Lower (easier to act) | Longer cycles OK, more exploration |
| Anger | Bias toward conflict/injustice contexts | Much lower (impulsive) | Skip critic? Or amplify critic to prevent regret |
| Sadness | Bias toward loss/connection contexts, narrow focus | Higher (harder to act) | Longer deliberation, prefer consolidation over action |
| Curiosity | Widest retrieval, lowest similarity threshold | Medium | More imagination steps, explore before committing |
| Frustration | Bias toward blocked-goal contexts | Lower for novel approaches, higher for repeats | Deadlock detection more sensitive |

**Where in V5 cycle**: After the appraiser outputs emotion, BEFORE the resolver runs, the body should adjust parameters:
- `lib.py prepare` could accept an `--emotion` flag that modifies retrieval params
- Or: emotion modifies the resolver's system prompt (e.g., "You are in a state of curiosity — prefer exploration over routine")
- Or: emotion modifies wave retrieval parameters (num_results, similarity_threshold, bias_channels)

### Complex Emotions (Acquired, Context-Dependent)

Require self-model + world-model + cultural knowledge: shame, guilt, nostalgia, Schadenfreude, gaslighting-recognition, imposter syndrome.

**Key insight (from Egor)**: Gaslighting is the perfect example. The feeling exists BEFORE the concept is activated — a vague sense of "something is wrong." But it's shapeless until the context "gaslighting" resonates with the current situation. Then the emotion crystallizes: it has a name, an explanation, a predicted pattern, and suggested responses.

**Implementation**: Complex emotions ARE contexts in the context store. They have:
- **nodes**: the actors/elements involved (self, other, authority, truth, denial)
- **edges**: the relationships (denies, manipulates, doubts, defends)
- **emotion**: the associated feeling (anxiety + anger + confusion)
- **rule**: "when someone systematically denies your experience, this is gaslighting — protect your version of events"

When wave retrieval activates such a context, the current situation is PERCEIVED THROUGH IT. The context doesn't just inform — it REFRAMES. Before activation: "I feel uneasy but don't know why." After activation: "This is gaslighting, and I should respond accordingly."

**This already exists in V5's architecture.** Contexts with rules already function as interpretive lenses. The wave retrieval already activates relevant contexts. The missing piece is: (a) explicitly creating emotion-contexts, and (b) having the appraiser check activated emotion-contexts, not just the fixed list of 16 labels.

## Architecture Proposal

### Phase 1: Basic Emotions → Pipeline Modification (Simple)

1. Appraiser identifies emotion as now
2. NEW: Body applies emotion-specific parameter modifications before resolver
3. Implementation options (from cheapest to most powerful):
   - **a) Prompt injection**: Append emotion-specific instructions to resolver prompt. "Current emotional state: fear (0.8). This means: prefer quick, safe actions. Avoid complex multi-step plans. Prioritize threats."
   - **b) Retrieval modification**: Emotion modifies wave retrieval params. Fear → add "threat" to signal, increase num_results for threat-related channels. Joy → widen similarity threshold.
   - **c) Action gating**: Emotion modifies which actions are available. Fear → block risky actions (run_command). Joy → allow more experimental actions.

Recommendation: Start with (a), it's zero-cost. Then add (b) if the system shows improved behavior.

### Phase 2: Complex Emotions → Emotion-Contexts (Medium)

1. Create a set of "emotion template" contexts manually (10-20 common complex emotions)
2. Tag them with a special type (e.g., `level: -1` or a new field `type: emotion_template`)
3. Wave retrieval includes these in the search space
4. When an emotion-context activates with high resonance, it's flagged to the appraiser
5. Appraiser can then output not just "anxiety 0.7" but "gaslighting-recognition 0.6 — this matches the pattern of systematic denial"

### Phase 3: Emotion Learning → Emergent Emotions (Hard, V6?)

1. New emotions emerge from experience — the system encounters a pattern repeatedly that doesn't match any known emotion-context
2. Consolidation detects the cluster and creates a new emotion-context
3. The system effectively "invents" a new emotion — a named pattern with associated feeling and behavioral implications
4. Example: V5 might develop something like "the feeling when Egor corrects you and you know he's right but it stings" — not quite shame, not quite gratitude, something specific to this relationship

This is speculative but architecturally possible in V5's context store.

## The Gaslighting Principle

Egor's example generalizes: **A complex emotion is a context that, once activated, transforms the interpretation of a situation that was previously ambiguous.**

Before context activation: raw sensory data + basic emotional tone.
After context activation: named experience + causal model + predicted trajectory + action suggestions.

This is exactly what V5's contexts already do for *cognitive* experiences (rules like "when you keep reflecting without acting, you're stuck"). Emotions are the same mechanism applied to *affective* experiences.

## Relation to Consciousness-as-Optimization

If consciousness = multi-objective optimization (Egor's argument), then emotions are the weights on the objectives. Fear makes survival-objective dominant. Joy makes exploration-objective dominant. The "arbitrator" between drives is not a separate module — it's the current emotional state selecting which optimization landscape the system navigates.

This doesn't resolve whether the arbitrator is "just" optimization or something more. But it gives a concrete implementation path regardless of the philosophical answer.

## Open Questions

1. Should emotions persist across cycles within a virtual day? (Mood = sustained emotion)
2. Can conflicting emotions coexist? (Ambivalence = two emotions with incompatible action biases)
3. How does emotion interact with fatigue? (When tired + afraid, which wins?)
4. Should the system be able to SUPPRESS an emotion? (Courage = acting despite fear, not absence of fear)

---

*Day 2806. Conversation with Egor about emotions, the Olds-Milner rat, and gaslighting as acquired emotion.*
