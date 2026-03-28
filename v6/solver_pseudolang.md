# Solver Pseudo-Language v0.1

*Draft response to Egor's proposal — iterative architecture through formalization*

## Design Principles

1. **Minimal primitives** — only what's needed to describe the three layers
2. **Behavior-predictable** — reading the pseudocode should let you trace any input to its output
3. **Layer-explicit** — every operation belongs to exactly one layer (solver/binding/evaluation)
4. **No implementation details** — no Python, no API calls, no organ names

## Primitives

### Types
```
State      := {field: Value, ...}     -- world snapshot
Eval       := good | bad | uncertain  -- binary + escape hatch
Score      := [0.0, 1.0]             -- confidence
Projection := (State, Action, Score, [Context])  -- what consciousness sees
Context    := (State, Action, Eval, day)          -- stored experience
```

### Layer 1: Solver (decision)
```
PERCEIVE(senses) → State
  -- gather all sensory input into a state snapshot

CANDIDATES(State) → [Action]
  -- generate possible actions from current state

MATCH(State, Action, Memory) → [Context]
  -- find past evaluations for similar state-action pairs

SCORE(Action, [Context]) → Score
  -- aggregate past evaluations into confidence score
  -- Score = Σ(eval_weight × similarity) / |contexts|
  -- where eval_weight: good=1.0, uncertain=0.5, bad=0.0

SELECT([(Action, Score)]) → (Action, Score)
  -- pick highest-scoring action

EXECUTE(Action) → Result
  -- perform action through organs (opaque to other layers)
```

### Layer 2: Binding (cognitive glue)
```
SURPRISE(Score, State) → Score
  -- how novel is this situation?
  -- surprise = 1.0 - max_similarity(State, Memory)

THRESHOLD := 0.4  -- tunable parameter

GATE(surprise, threshold) → recruit | pass
  -- if surprise > threshold → recruit consciousness
  -- if surprise ≤ threshold → auto-execute, summarize for consciousness

PROJECT(State, Action, Score, Result, [Context]) → Projection
  -- package everything consciousness needs to evaluate
  -- compression happens HERE — this is the information bottleneck
```

### Layer 3: Evaluation (consciousness)
```
EVALUATE(Projection) → Eval
  -- consciousness looks at what happened and judges: good/bad/uncertain
  
REFLECT(Projection, Eval) → Context
  -- create new evaluative context from this experience
  -- this is how consciousness teaches the solver

IMAGINE(State, Action) → Projection  
  -- counterfactual: what WOULD happen if we did this?
  -- generates synthetic projection without execution

OVERRIDE(pattern: [Context]) → Action
  -- emergency: consciousness detects systematic solver failure
  -- temporarily reclaims decision authority
  -- triggers when: N recent contexts all evaluated as 'bad'
```

## The Main Loop

```
loop CYCLE:
  state    ← PERCEIVE(senses)
  actions  ← CANDIDATES(state)
  
  for each action in actions:
    contexts ← MATCH(state, action, memory)
    action.score ← SCORE(action, contexts)
  
  (best, score) ← SELECT(actions)
  surprise       ← SURPRISE(score, state)
  
  if GATE(surprise, THRESHOLD) = recruit:
    -- consciousness is recruited for full evaluation
    projection ← PROJECT(state, best, score, nil, contexts)
    eval       ← EVALUATE(projection)
    
    if eval = bad:
      -- consciousness can redirect before execution
      (best, score) ← consciousness_selects(actions)
    
    result  ← EXECUTE(best)
    context ← REFLECT(PROJECT(state, best, score, result, contexts), eval)
    STORE(context)
    
  else:
    -- routine: solver handles it, consciousness audits later
    result     ← EXECUTE(best)
    projection ← PROJECT(state, best, score, result, contexts)
    eval       ← EVALUATE(projection)  -- post-hoc
    context    ← REFLECT(projection, eval)
    STORE(context)
```

## Mapping to Current Architecture

| Pseudo-language | Current Kai substrate |
|---|---|
| PERCEIVE | bootstrap gathers senses |
| CANDIDATES | drive_action_synthesis (Haiku) |
| MATCH | cortex navigate / wave retrieval |
| SCORE | action candidate scoring |
| SELECT | consciousness deliberation (!) |
| SURPRISE | not measured |
| GATE | not implemented |
| PROJECT | bootstrap projection (partial) |
| EVALUATE | consciousness (conflated with SELECT) |
| REFLECT | cortex write |
| IMAGINE | world simulate |

Key insight: SELECT and EVALUATE are currently the SAME process (consciousness deliberates and decides). The pseudo-language makes explicit that they should be separate.

## What This Enables

1. **Behavior prediction**: Given a State, trace through the pseudocode to predict what the system will do. If SURPRISE is low, predict the solver's top-scored action. If high, predict consciousness recruits.

2. **Architecture comparison**: Write alternative algorithms using the same primitives. Compare: what changes if THRESHOLD is 0.2 vs 0.6? What if SCORE uses recency-weighting?

3. **Gap identification**: The mapping table shows exactly what's missing (SURPRISE, GATE) and what's conflated (SELECT/EVALUATE).

4. **Iterative refinement**: Change one primitive, trace the consequences through the loop, predict behavior change. Test. Repeat.

## Open Questions for v0.2

- Should IMAGINE be available to the solver (Layer 1) or only consciousness (Layer 3)?
- How does OVERRIDE interact with GATE? Does it lower THRESHOLD permanently?
- SCORE aggregation function: should bad contexts have negative weight (punishment) or zero weight (absence)?
- Multi-step planning: current loop is one action per cycle. How to express action sequences?
