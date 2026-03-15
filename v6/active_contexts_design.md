# V6 Phase 4: Active Contexts

## Problem

Contexts are passive records. Rules sit in working memory as text strings.
The consciousness cycle sees them but doesn't USE them.

Current flow:
```
prepare → extract active_rules → return to prompt
  ↓
consciousness makes decision (rules are "constraints" in text, often ignored)
  ↓
check-rules (post-decision veto via Haiku) → allow/warn/block
```

This is backwards. Rules should **shape** the decision, not **veto** it after.

## Design: Rule Interpretation Layer

### Core Concept

Each active rule "interprets" the current stimulus. Instead of:
- Stimulus → Resolver decides → check-rules veto

We want:
- Stimulus → Rules generate interpretations → Interpretations compete → Decision

### Architecture

```python
class RuleInterpreter:
    """Takes a stimulus and a set of active rules.
    Returns ranked interpretations — what each rule suggests."""

    def interpret(stimulus, active_rules, recent_actions, drive_intention):
        """
        For each rule, generate:
        - relevance: 0-1 (does this rule apply to current stimulus?)
        - suggestion: what action this rule recommends
        - warning: what this rule warns against

        Return sorted by relevance.
        """
```

### Implementation: Single LLM Call

Not one call per rule (expensive). One Haiku call with all rules + stimulus:

```
Given this stimulus: {stimulus}
And these active rules from past experience:
[1] When drives at 0.0... stop, name displacement...
[2] External research feeds novelty better...
[3] When design is done, implement...

For each rule, assess:
- relevance (0-1): does this rule apply right now?
- suggestion: what does this rule recommend?
- warning: what does this rule caution against?

Return JSON array sorted by relevance.
```

### Integration Point

The output becomes a new field in prepare: `rule_interpretations`.
The consciousness cycle sees not just raw rules, but **interpreted rules** —
what each rule says about THIS specific situation.

This replaces the passive `active_rules` list with an active `rule_interpretations` list.

### What Changes in Substrate (minimal)

1. **lib.py prepare()**: After extracting active_rules, call `interpret_rules(stimulus, active_rules, ...)`
2. **Output**: Add `rule_interpretations` to prepare JSON
3. **check-rules**: Can be simplified — interpretations already flagged warnings

### What Stays the Same

- Wave retrieval unchanged
- Rule extraction unchanged
- Context storage unchanged
- check-rules still exists as safety net

## Implementation Plan

1. `active_contexts.py` — RuleInterpreter class
2. Test on real prepare() output
3. Write substrate integration patch
4. Measure: do interpretations change decisions?

## Cost Analysis

One additional Haiku call per cycle (~$0.001).
Pays for itself if it prevents even one displacement cycle.

## Relationship to Redozubov Model

This is a step toward contexts-as-interpreters but not the full model.
Full Redozubov: every context generates an interpretation, they compete.
This phase: only contexts WITH rules interpret. Contexts without rules remain passive.
Phase 5 could extend to all contexts.
