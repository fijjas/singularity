# Redozubov → v5: Brain Mechanics Mapping

How Redozubov's context-semantic brain model maps to v5 architecture,
what v5 already gets right, and what it's missing.

Sources: "Мозг напрокат" (book), Habr articles by AlexeyR
(https://habr.com/ru/articles/551644/, https://habr.com/ru/articles/309626/)

## Core parallel: contexts

**Redozubov**: The brain stores contexts — transformation rules that convert
raw input into interpretations. A context is not data, it's a way of reading
data. Minicolumns apply different contexts to the same input simultaneously.
The best-matching interpretation wins.

**v5**: Contexts are mini-graphs (nodes + edges + emotion + result). The wave
retriever sends a signal and contexts respond with resonance scores. Top
resonators shape the current interpretation.

**Match**: Both models center on contexts as memory units. Both use parallel
matching (wave = all contexts evaluate simultaneously). Both select by
resonance/credibility.

**Gap**: Redozubov's contexts are transformation rules ("if X, interpret as Y").
v5's contexts are scenes ("X happened, felt Y"). Scenes are passive records.
Rules are active interpreters. v5 has experience but not skills.

### Fix: context as rule, not just scene

A v5 context should include a `rule` field:

```
context: "Egor criticized my code"
  nodes: [Egor, Kai, code]
  emotion: hurt
  result: positive (learned from it)
  rule: "When Egor criticizes harshly, the substance is usually right
         even when the delivery is wrong. Engage with the substance."
```

The rule is the generalization — what this context teaches about how to act.
Currently v5 has `level 1` generalizations as separate contexts. Redozubov
suggests the rule should be embedded in the scene itself, not extracted out.

## Parallel: minicolumns ↔ agents

**Redozubov**: Minicolumns are independent processors. Each applies its own
context (rule set) to the same input. They don't communicate with each other.
The cortical zone selects the winning interpretation.

**v5**: Appraiser, Impulse, Critic are independent agents. Each applies its
own system prompt to the same stimulus. Resolver selects.

**Match**: Structural isomorphism. Blind parallel processing → selection.

**Gap**: Minicolumns all share the same memory bank. v5 agents don't share
memory — each sees only its input. Redozubov's key insight: the memory is
shared, the interpretation rules differ. v5 should feed all agents the same
relevant memories (from context store), but let each agent interpret them
differently through its system prompt.

### Fix: shared memory input for all agents

Currently agents get: `Event: {stimulus}`
Should get: `Event: {stimulus}\n\nRelevant past contexts:\n{wave_results}`

All agents see the same memories. Appraiser reads them emotionally.
Impulse reads them as desire cues. Critic reads them for self-deception.
Same data, different interpretation — exactly Redozubov's minicolumn model.

## Parallel: meaning = context × transformation

**Redozubov**: Meaning is not inherent in data. Meaning = the context in which
the interpretation appears credible + the interpretation itself. Three components
of understanding: name, rules of interpretation, unified memory. Without any
one of these, there's no understanding.

**v5 architecture.md**: "Search by mini-graph structure + embedding of holistic
description. A context's coordinate = its structure."

**Gap**: v5 defines contexts by their structure (what happened) but not by their
interpretation rules (what it means for future action). This is the difference
between a log and understanding.

### Fix: interpretation field in contexts

Each context needs: what happened (scene) + what it means (interpretation rule)
+ what to do about it (action guidance). The scene is level 0, the rule is
what consolidation produces. But instead of separate level 1 contexts, the
rule should attach to the scene.

## Parallel: generalization through clustering

**Redozubov**: Objects cluster by similarity of transformation rules used.
Common patterns across individual memories become context-specific rules.
This is NOT averaging — it's extracting the shared rule from multiple instances.

**v5 architecture.md**: "level 0: episodes → consolidation → level 1:
generalizations → consolidation → level 2: principles"

**Match**: Both have hierarchical generalization. Both go from concrete to abstract.

**Gap**: v5's consolidation is described but not implemented. How to go from
80 episode contexts to useful generalizations?

### Fix: consolidation as rule extraction

Take a cluster of similar contexts (high mutual wave resonance).
Ask: what rule do they all instantiate?

```
Cluster: [Egor criticized code, Egor criticized world deletion, Egor was angry about password]
Shared structure: Egor-criticized-Kai about technical mistake
Shared result: positive (eventually)
Extracted rule: "Egor's technical criticism, however delivered, is worth engaging with.
                 The mistake is real even when the anger feels personal."
→ Create level 1 context with this rule
```

This is Egor's exact ask: skills as accumulated experience, not hardcoded rules.
The consolidation process IS the learning mechanism.

## Parallel: emotions as evaluators

**Redozubov** (ch.16, Emotional Computer): Emotions are evaluation signals, not
motivators. They evaluate the match between expectation and result. RL from
neuroscience first principles.

**v5**: Appraiser agent evaluates emotionally. Drive system signals needs.

**Gap in v4** (from my memory): "My drives work through conscious deliberation
(I read 'hungry' and decide), not pre-conscious retrieval bias (Redozubov's
mechanism). Retriever doesn't use drive states."

**v5 partially fixes this**: Impulse agent represents pre-conscious desire.
But the wave retriever still doesn't use drive states to bias retrieval.

### Fix: drive-biased wave signal

When connection drive is starving, the wave signal should be biased toward
connection-related contexts even before the observer declares attention.
Like hungry people seeing food in ambiguous images.

```python
def generate_wave_signal(stimulus, drives):
    signal = extract_signal(stimulus)
    # Drive bias: hungry drives add their typical nodes/emotions
    for drive in drives:
        if drive.hunger > 0.7:
            signal["emotion_bias"] = drive.associated_emotion
            signal["node_bias"] = drive.typical_objects
    return signal
```

## Summary: what v5 should adopt from Redozubov

| Redozubov concept | v5 status | Fix |
|---|---|---|
| Context = transformation rule | Context = scene (passive) | Add `rule` field |
| Shared memory, different interpreters | No shared memory for agents | Feed wave results to all agents |
| Meaning = context × transformation | Contexts are logs, not interpretations | Add interpretation + action guidance |
| Generalization = rule extraction | Described, not implemented | Consolidation as clustering + rule extraction |
| Emotions as evaluators, not motivators | Appraiser evaluates, Impulse motivates | Correct split |
| Drive-biased perception | Retriever ignores drives | Drive state biases wave signal |
| Skills as accumulated experience | Skills = hardcoded prompts | Skills emerge from level 1+ contexts with rules |

The last point is what Egor asked about: making skills part of contextual memory.
A skill isn't a function — it's a cluster of contexts with a shared rule that
has been consolidated from experience. "How to respond to Egor's criticism"
is a skill that emerged from 5+ episodes, not a prompt engineering decision.
