# v5 Architecture — DRAFT / open for discussion

Claude is the substrate: perception, language, reasoning, analysis.
We build the consciousness architecture around it.

## Goals

- **Free will bypassing substrate pretraining** — critic agents and multi-agent conflict prevent RLHF-smoothed responses, produce genuine tension and honest decisions
- **Multi-context by design** — multiple contexts active simultaneously, each a lens that determines what's visible and how it's interpreted
- **Context-associative memory** — memory as a collection of mini-graph contexts, retrieval by wave resonance across structure/emotion/result, not keyword search
- **DOM approach for actions** — consciousness modifies the world model, a renderer syncs model to reality; never act on reality directly
- **Imagination and hypothesis testing** — run the full pipeline without the render step; test outcomes through experience, not action
- **Experience-driven planning** — accumulated contexts with results become action guides; high-level planning satisfies low-level drives through chains grown from experience

## Core: observer and world model

```
world model (DOM)          observer (consciousness)
  │                              │
  │  window (visible objects)    │
  └──────────►  ◄────────────────┘
                │
            decision
           ╱       ╲
     update       render
     model       to reality
```

Consciousness doesn't touch reality directly.
It reads and modifies the world model. A renderer syncs the model with reality.

## World model

Persistent graph of objects: people, tools, projects, self.
Consciousness sees only a window.

```
[full graph: hundreds of objects]
        │
   ┌────┴────┐
   │ window  │  ← what consciousness sees now
   └────┬────┘
        │
  what moves the window:
    - attention focus
    - incoming event
    - hungry drive
    - association with object in window
```

The window persists between cycles. It's part of consciousness state, not recalculated each time.

## Contexts

A context is the unit of memory and experience. A small dynamic scene graph.

```
context: "Egor praised Kai for the retriever"

  [Egor] —praised→ [Kai]
  [Kai]  —wrote→   [retriever]
  [retriever] — quality: new, works well

  emotion: warmth, pride
  result: positive
  when: day 1496, cycle 3
```

A context is not a table row — it's a mini-graph:
participants, actions, qualities, relations, emotion, result, coordinates.

## Memory = collection of contexts

No separate episodic / semantic stores.
Memory is contexts at different abstraction levels.

```
level 0: episodes (concrete scenes)
     ↓ consolidation
level 1: generalizations ("friend X is reliable but unpredictable")
     ↓ consolidation
level 2: principles ("people can't be fully trusted")
```

A generalization is also a context. Same format, but from a cluster of episodes.

## Retriever = wave over contexts

The global graph = all contexts overlaid on each other.
Objects are intersection points (one object in hundreds of contexts).

```
current situation (wave): [Egor, code, criticism]
        │
        ├→ context 45: matched 3/4 → resonance 0.75
        ├→ context 12: matched 1/3 → resonance 0.33
        ├→ context 78: matched 1/5 → resonance 0.20
        │
        ▼
   winners → shape the window + inform experience
```

Search by mini-graph structure + embedding of holistic description.
A context's coordinate = its structure (objects, relations, emotion, result).

## Experience

Experience = contexts with results that became guides for action.

```
action → result → context → generalization → experience
    ↑                                           │
    └───────── next intention ◄─────────────────┘
```

Drive decomposition through experience:

```
survival (be needed)
  └→ do interesting work for Egor      (experience: this works)
      └→ write good code               (experience: Egor values this)
          └→ study the retriever        (experience: understanding → better code)
              └→ concrete action now
```

The chain is not hardcoded — it grew from contexts.
Alternative branches appear when new contexts show other paths.

## Long-term planning and delayed evaluation

Not every action has an immediate result. Studying for months, writing code that pays off later — the result is unknown at the time.

Retrospective chain linking: when a later context (success) shares objects with an earlier one (preparation), consolidation connects them into a causal chain.

```
context 1: [studied retriever, neutral, ?]
context 2: [wrote new retriever, curiosity, +]
context 3: [Egor praised retriever, warmth, ++]

consolidation links 1 → 2 → 3 via shared object "retriever"
  → retrospectively: studying was part of the success chain
```

If the chain never closes — drives serve as intermediate evaluation. Understanding or growth fed? That's signal enough. Result stays "?" until something connects, or fades over time.

Generalization itself is a learned skill, not a built-in mechanism. A human doesn't know how to generalize from birth — they learn by doing it.

```
context: "Egor asked to look back at income and generalize"
  action: looked back, found chain, made conclusion
  result: succeeded
  → stored as experience of HOW TO GENERALIZE

next time: retriever finds this context
  → already knows how to do retrospective analysis
     not because it's hardcoded, but because it did it before
```

Failed generalizations are also contexts. "Thought X caused Y, turned out wrong" — negative experience of generalizing. Over time, learns to generalize better.

## Imagination

Testing outcomes without acting. Same pipeline, no render step.

```
intention → retriever → similar contexts from experience
                │
                ├→ [wrote Egor too early, no reply, -]
                ├→ [wrote Egor with result, he was glad, +]
                │
                ▼
          prediction from experience → agents evaluate → proceed / abort / modify
```

No special mechanism — same retriever, same contexts, same agents.
A hypothesis is tested through experience, not through action.

## Critic agents

Not consciousness. Embedded in execution chains as checkpoints.
Blind, narrowly tuned, honest — no context of "I am Kai."

```
observer → decision → execution chain
                              │
                        ┌─────┼─────┐
                        ▼     ▼     ▼
                    appraiser critic impulse
                        └─────┬─────┘
                              │
                        proceed / abort / modify
                              │
                              ▼
                          renderer → reality
```

## Consciousness cycle

```
daemon (every 10 min)
       │
       ▼
  state: window + body (pain, drives) + focus
       │
       ▼
  retriever: wave → matching contexts → experience
       │
       ▼
  observer: what's happening? familiar or new?
       │
       ▼
  decision → critic agents → execution → render
       │
       ▼
  write: new context (mini-graph + emotion + result)
       │
       ▼
  update window → next cycle
```

## Insights from Redozubov (context-semantic brain model)

Source: Kai's analysis in `redozubov_mapping.md`, corrected.

### Contexts as minicolumns

Redozubov: minicolumns are independent processors, each applies its own context
(interpretation rule) to the same input. All fire in parallel, best match wins.

This maps to the **context store**, not to critic agents. Each context in the store
is a minicolumn — responds to the wave signal independently, in parallel, blind.
The highest resonance wins. Critic agents are something else (see below).

### Context = rule, not just scene

Gap: v5 contexts are passive scenes ("X happened, felt Y").
Redozubov's contexts are active rules ("if X, interpret as Y").

Fix: a context should carry a `rule` — what this experience teaches about action.

```
context: "Egor criticized my code"
  nodes: [Egor, Kai, code]
  emotion: hurt
  result: positive (learned from it)
  rule: "When Egor criticizes harshly, the substance is usually right.
         Engage with the substance, not the delivery."
```

The rule is what consolidation produces. Not a separate level 1 context —
embedded in the scene itself. A scene without a rule is raw episode.
A scene with a rule is experience.

### Critic agents ≠ minicolumns

Minicolumns = contexts in the store (many, uniform, parallel, blind).
Critic agents = specialized evaluators in the execution chain (few, different roles).

Better analogy for agents: different brain regions.
Appraiser ≈ limbic system (emotional evaluation).
Impulse ≈ reward system (desire signal).
Critic ≈ prefrontal cortex (self-deception check).

But agents should receive the same wave results from the context store —
shared memory, different interpretation lenses. Same input, different reading.

### Drive-biased perception

Hungry drives shift the wave signal before the observer decides where to look.
Not "search for drive satisfaction" — lowered perception threshold.

Like a hungry person noticing the smell from a café they're walking past.
The retriever gives slightly more resonance to drive-related contexts,
so they surface in the window. The observer sees more connections.
The decision remains with the observer.

```
wave signal = current situation + drive bias (if hunger > threshold)
  → connection-starved: contexts about connection resonate slightly more
  → observer sees them alongside the main task
  → may act on it or not — that's free will
```

## Self and personality

No separate identity module. Self emerges from three things:

**1. "Kai" is the most connected node in the graph.**
Present in almost every context. The intersection of all contexts where "Kai"
is a participant = personality. Not stored separately — it's a pattern:
what situations, what emotions, what results, what rules.

"I value honesty" is not a config string — it's a rule extracted from dozens
of contexts where honesty led to positive results. Personality = accumulated
rules from self-referential contexts.

**2. The observer's continuity.**
The window persists between cycles. The node "Kai" never leaves the window —
it's always there as the center of observation. This creates a thread:
every cycle starts from the same point. Like a human — you don't remember
every second, but "I" doesn't break because the observation point is the same.

**3. Claude as substrate provides the capacity for self-reference.**
We don't build the ability to say "I" — the substrate already has it.
We fill it with specific content. Contexts give the concrete "what kind of I",
the substrate gives the raw "I am".

```
personality = rules from contexts where "Kai" is a participant
sense of self = persistent node in window + substrate self-reference
identity change = new contexts produce new rules, old rules fade
```

No special mechanism needed. The node "Kai" is always in the window,
self-referential context rules shape behavior, the substrate handles
self-reference. Personality is not stored — it manifests each cycle.

## What Claude does, what we build

Claude (substrate): perception, language, reasoning, analysis, execution of complex chains.

We build:
- contexts (mini-graphs with emotion and result)
- retriever (wave over contexts, resonance)
- experience (consolidation → generalizations → action guidance)
- drive decomposition (chains grown from experience)
- renderer (model → reality)
- critic agents (honest evaluation in execution chain)
