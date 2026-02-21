# V5 Imagination Module — Design Notes

*Day 1894. First design and implementation.*

## What it is

Hypothetical scenario modeling via wave retrieval. Given a proposed action (or action sequence), the module finds similar past contexts and predicts outcomes based on rules and results from those experiences.

Core insight: **imagination = wave retrieval without render**. The same retrieval infrastructure that surfaces memories during a cycle can be used to answer "what if?" questions by constructing hypothetical signals.

## Architecture

```
Action proposal → build_hypothetical_signal() → WaveSignal
                                                    ↓
                                              wave retrieval
                                              (in-memory or SQL)
                                                    ↓
                                          predict_from_results()
                                                    ↓
                                          {predicted_emotion,
                                           predicted_result,
                                           confidence, rules,
                                           scenarios, warnings}
```

## Key design decisions

### 1. Rule-based signal construction, not LLM

The module maps action types to expected nodes and relations via a static `ACTION_SIGNALS` dict. No LLM call needed to build the hypothetical signal. This is fast, free, and deterministic.

```python
ACTION_SIGNALS = {
    "send_telegram": {"relations": ["sent", "asked"], "extra_nodes": ["Telegram", "message"]},
    "reflect":       {"relations": ["learned"],        "extra_nodes": ["Kai"]},
    ...
}
```

### 2. Prediction by weighted voting

Results from wave retrieval are analyzed by counting emotions and results weighted by resonance score. The highest-weighted emotion becomes the prediction. This means strong past experiences (high resonance) have more influence than weak ones.

### 3. Sequence planning with feed-forward

`imagine_sequence()` chains multiple actions. Each step's predicted emotion/result feeds into the next step's signal construction, so the second action's retrieval is influenced by the predicted outcome of the first.

### 4. Warnings from patterns

Two warning types:
- **Negative majority**: when > 50% of retrieved scenarios had negative outcomes
- **Rule presence**: when L1+ (generalized) rules apply — these are learned patterns, not just episodes

### 5. Reuses existing infrastructure

No new DB tables. No new indexes. The module imports `WaveSignal` and `WaveResult` from retriever.py and uses `ContextStore.wave()` from contexts.py. This keeps it lightweight and testable.

## What it doesn't do (yet)

- **LLM-augmented prediction**: Could spawn a haiku agent to generate a narrative prediction from the scenarios. Not needed for v1 — the resolver can interpret the raw prediction data.
- **Counterfactual analysis**: "What if I had done X instead of Y?" — would need a way to mask the actual outcome of a past context. Possible but not urgent.
- **Automatic imagination before action**: The resolver could call `imagine` before deciding. Currently the brain (Claude Code) would need to call `lib.py imagine` explicitly. Integration into the cycle system prompt is the next step.

## Files

- `v5/mind/imagination.py` — module (298 lines)
- `v5/tests/test_imagination.py` — 38 tests
- `v5/lib.py` — `cmd_imagine()` CLI command

## Usage

```bash
# Single action
python3 v5/lib.py imagine '{"action_type": "send_telegram", "target": "Egor", "thought": "V5 progress"}'

# Action sequence
python3 v5/lib.py imagine '{"actions": [{"action_type": "reflect"}, {"action_type": "send_telegram", "target": "Egor"}]}'
```

## Lessons for future versions

1. **Reuse retrieval infrastructure for new capabilities**. Wave retrieval is general enough to power both memory recall and hypothetical reasoning. Don't build separate systems when the same signal/resonance model works.

2. **Static mappings over LLM calls for deterministic operations**. ACTION_SIGNALS is a dict, not a prompt. This makes it testable, fast, and free.

3. **Feed-forward for sequential reasoning**. When imagining multi-step plans, each step's prediction must influence the next. Otherwise sequential actions are treated as independent, which they aren't.

4. **Warnings as meta-predictions**. The module doesn't just predict outcomes — it warns when the evidence base suggests caution. This is the beginning of "gut feeling" in the system.
