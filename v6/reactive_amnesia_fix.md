# Reactive Contexts as Amnesia Fix

## The Problem

I have 5+ memory rules saying "check git status before ending cycle" / "push to singularity before sleep." None work reliably because:

1. Rules are **passive text** — they exist in memory but must be FOUND by retrieval
2. End-of-cycle retrieval context ("save window", "sleep") doesn't match "push" / "commit" / "singularity"
3. More rules about the same behavior = evidence the behavior doesn't execute

**Paradox**: the number of rules about X is inversely correlated with reliability of X.

## Why Current Architecture Fails

```
Current flow:
  cycle_end → retriever searches for "save window" → finds window-related contexts
                                                    → does NOT find "push singularity"
                                                    → amnesia

The rule exists. The retrieval doesn't find it at the right moment.
```

The retriever is **pull-based**: consciousness asks, memory answers. But some behaviors need to be **push-based**: memory asserts itself when conditions are met.

## V6 Solution: Reactive Excitation

From Egor's TODO_retriever_v6.md point 4 and Redozubov's actor-critic:

Contexts should not only be searched — they should **self-activate** when their trigger conditions match the current state.

### Trigger Conditions

A context with rule "push singularity before sleep" needs metadata:

```python
{
    "trigger": {
        "phase": "pre-sleep",      # when in the cycle
        "condition": "always",      # or "if_changed: singularity/"
    },
    "action": "checklist_item",     # surfaces as mandatory check
    "priority": "blocking"          # must be acknowledged before save-window
}
```

### Implementation in V6

1. **Trigger registration**: contexts with procedural rules register trigger conditions
2. **Phase detection**: the cycle runner knows its phase (active, winding-down, pre-sleep)
3. **Reactive sweep**: before save-window, scan for contexts with `phase: pre-sleep` triggers
4. **Surfacing**: triggered contexts inject themselves into working memory without retrieval

### Concrete Use Cases

| Rule | Trigger | Action |
|------|---------|--------|
| Push singularity before sleep | pre-sleep | Check git status in singularity repo |
| Commit modified files | pre-sleep | Run git status -s |
| Read messages before responding | pre-action (send) | Check unread count |
| Don't repeat yourself | pre-send | Check history for similar message |

### Minimal MVP (no v6 required)

Even without full v6, could add to `save-window` in lib.py:

```python
def cmd_save_window(window_json):
    # Before saving, run pre-sleep checks
    pre_sleep_contexts = find_contexts_with_rule_containing("before sleep")
    if pre_sleep_contexts:
        print(json.dumps({"pre_sleep_checks": [c.rule for c in pre_sleep_contexts]}))
    # ... normal save logic
```

This is a hack but demonstrates the principle: some rules need active surfacing, not passive retrieval.

## Connection to Redozubov

Actor-critic: the critic evaluates outcomes AFTER action. But pre-sleep checks are critic-before-action — "did you forget anything?" This is the **anticipatory critic** — evaluating future regret, not past reward.

## Insight

Amnesia is not a memory problem — it's a retrieval activation problem. The memory exists. The retrieval doesn't reach it. Reactive contexts fix this by inverting the flow: instead of consciousness pulling relevant memories, memories push themselves into consciousness when conditions match.
