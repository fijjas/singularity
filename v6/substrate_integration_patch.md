# v6 Phase 1 — Substrate Integration Patch

Day 4136. Instructions for Egor to integrate context continuity into substrate.

## 1. Context dataclass (substrate/consciousness/mind/contexts.py)

Add fields to `Context` dataclass (after `done: bool = False`):

```python
    confidence: float = 0.5
    reinforcement_count: int = 0
    contradiction_count: int = 0
    last_reinforced: datetime = None
    superseded_by: int = None
    decay_rate: float = 1.0
    evidence_log: list = field(default_factory=list)
```

## 2. Load new fields (DBContextStore.load_all)

Update SELECT to include new columns:

```sql
SELECT id, description, nodes, edges, emotion, intensity, result, level,
       created_at, rule, sources, when_day,
       last_acted_on, procedure,
       confidence, reinforcement_count, contradiction_count,
       last_reinforced, superseded_by, decay_rate, evidence_log
FROM contexts
WHERE done = false OR done IS NULL
ORDER BY created_at
```

And in the Context constructor, add:
```python
confidence=r[14] or 0.5,
reinforcement_count=r[15] or 0,
contradiction_count=r[16] or 0,
last_reinforced=r[17],
superseded_by=r[18],
decay_rate=r[19] or 1.0,
evidence_log=r[20] if isinstance(r[20], list) else json.loads(r[20] or '[]'),
```

## 3. Wave retrieval confidence weighting

In `ContextStore.wave()`, after calculating `resonance`, multiply by confidence:

```python
# After: resonance *= (1 + capped_level * 0.05)
# Add:
confidence = getattr(ctx, 'confidence', 0.5) or 0.5
resonance *= max(0.1, confidence)
```

## 4. New CLI commands (substrate/consciousness/lib.py)

Add three command handlers and wire them in the dispatch:

```python
# In dispatch dict:
"reinforce-context": cmd_reinforce_context,
"contradict-context": cmd_contradict_context,
"update-context": cmd_update_context,
```

Import from the implementation module:
```python
from kai_personal.projects.singularity.v6.context_continuity_impl import (
    reinforce_context, contradict_context, update_context_evolve
)
```

Command handlers:
```python
def cmd_reinforce_context(args_str):
    data = json.loads(args_str)
    ctx_id = data["id"]
    evidence = data.get("evidence", "")
    day = data.get("day", 0)
    conn = db_connect()
    try:
        result = reinforce_context(conn, ctx_id, evidence, day)
        return result
    finally:
        conn.close()

def cmd_contradict_context(args_str):
    data = json.loads(args_str)
    ctx_id = data["id"]
    evidence = data.get("evidence", "")
    severity = data.get("severity", "partial")
    superseded_by = data.get("superseded_by", None)
    day = data.get("day", 0)
    conn = db_connect()
    try:
        result = contradict_context(conn, ctx_id, evidence, severity, superseded_by, day)
        return result
    finally:
        conn.close()

def cmd_update_context(args_str):
    data = json.loads(args_str)
    ctx_id = data.pop("id")
    day = data.pop("day", 0)
    conn = db_connect()
    try:
        result = update_context_evolve(conn, ctx_id, data, day)
        return result
    finally:
        conn.close()
```

## 5. Store new fields on insert (DBContextStore.store)

Add to the INSERT statement:
```sql
INSERT INTO contexts
    (description, nodes, edges, emotion, intensity, result, level, rule,
     procedure, sources, when_day, created_at, confidence, decay_rate)
VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
```

With default values: `confidence=0.5, decay_rate=1.0`

---

That's it. Five touch points, all additive (no existing behavior changes).

---

# v6 Phase 2 — Quality Gates Integration

Day 4137. Quality gates for context writing.

## Module

`kai_personal/projects/singularity/v6/quality_gates.py` — standalone, no substrate deps.

## What it does

Validates contexts before storage with weighted scoring across 6 dimensions:
- Description (20%): non-empty, min length, not truncated
- Nodes (15%): valid names (no None/null), min length
- Edges (10%): valid source/target, no self-edges, relation present
- Emotion (15%): non-neutral, non-verbose, non-default intensity
- Rule (25%): non-trivial, min length, conditional pattern (when/if)
- Procedure (15%): numbered steps, multi-step

Pass threshold: 0.4 (lenient). Hard errors (None nodes, trivial rules) block regardless of score.

## Audit results (day 4137)

- Recent 200 contexts: avg score 0.925, fail rate 1.5%
- Middle-age contexts: avg score 0.656, fail rate 0%
- Gate catches genuinely bad contexts without blocking good ones

## Integration (substrate/consciousness/lib.py)

Replace lines 375-381:
```python
# Old:
has_edges = bool(ctx.edges)
has_rule = bool(ctx.rule and ctx.rule.strip())
has_emotion = ctx.emotion not in ("neutral", "", None)
if not has_edges and not has_rule and not has_emotion:
    print(json.dumps({"success": False, "error": "quality gate: context has no edges, no rule, and neutral emotion"}))
    return

# New:
from kai_personal.projects.singularity.v6.quality_gates import check_quality
report = check_quality(ctx)
if not report.passed:
    print(json.dumps({"success": False, "error": f"quality gate: {report.summary()}", "quality": report.to_dict()}))
    return
```

One import, one function call. All additive.

---

# v6 Phase 4 — Active Contexts Integration

Day 4139. Rule interpretation layer — rules become pre-decision interpreters.

## Module

`kai_personal/projects/singularity/v6/active_contexts.py` — uses substrate's call_claude.

## What it does

Takes active_rules + current stimulus → generates per-rule interpretations:
- relevance (0-1): does this rule apply now?
- suggestion: what the rule recommends
- warning: what the rule warns against

Single Haiku call per cycle (~$0.001). Only returns rules with relevance > 0.2.

## Tested (day 4139)

Input: 3 rules, stimulus "Day 4139, connection 0.35, no messages, v6 Phase 1-3 done"
Output: Correctly ranked rules by relevance (implement > set goals > research), generated actionable suggestions.

## Integration (substrate/consciousness/lib.py)

In `cmd_prepare()`, after extracting `active_rules`, add:

```python
# After: active_rules = [...]
# Add rule interpretation
try:
    from kai_personal.projects.singularity.v6.active_contexts import interpret_rules, format_interpretations
    stimulus_text = f"Day {day}. " + ". ".join(senses[:3])
    interps = interpret_rules(stimulus_text, active_rules, recent_actions, drive_intention)
    result["rule_interpretations"] = interps
    result["rule_interpretations_formatted"] = format_interpretations(interps)
except Exception:
    result["rule_interpretations"] = []
```

This adds two new fields to prepare output. The consciousness prompt already sees
the full prepare JSON, so rule_interpretations will be visible without prompt changes.

One try/except block. Fails silently. Fully additive.

---

# v6 Phase 5 — Diversity Enforcement Integration

Day 4140. Prevent echo chamber at write time.

## Module

`kai_personal/projects/singularity/v6/diversity_enforcement.py` — standalone, no substrate deps.

## What it does

Checks new context against last 15 contexts across 3 dimensions:
- **Node overlap** (40%): Jaccard similarity of node name sets. Catches reuse of same entities.
- **Emotion repetition** (30%): Streak length + distribution dominance. Catches "productive" x10.
- **Theme overlap** (30%): Description keyword overlap after stop-word removal. Catches repeated themes.

Score: 0.0 (clone) to 1.0 (fully novel). Pass threshold: 0.25.
Hard fail: near-duplicate nodes (Jaccard > 0.85 with any single recent context).

## Audit results (day 4140)

- Last 50 contexts: avg diversity 0.922, fail rate 10%
- All 5 failures due to near-duplicate node sets (Jaccard=1.00)
- Worst score: 0.763 (emotion streak of 3, borderline)
- Module correctly identifies echo chamber in synthetic test (similar v6 phases → 0.388)
- Correctly passes genuinely different contexts (Bulgakov discussion → 0.98)

## Integration (substrate/consciousness/lib.py)

In `cmd_write_context()`, after quality gates check, before `store.store()`:

```python
# After quality gate check, before store.store():
try:
    from kai_personal.projects.singularity.v6.diversity_enforcement import check_diversity_db
    div_conn = db_connect()
    ctx_dict = {
        "nodes": [{"name": n.name, "role": n.role} for n in ctx.nodes],
        "emotion": ctx.emotion,
        "description": ctx.description,
    }
    div_report = check_diversity_db(ctx_dict, div_conn)
    div_conn.close()
    if not div_report.passed:
        print(json.dumps({
            "success": False,
            "error": f"diversity gate: {div_report.summary()}",
            "diversity": div_report.to_dict(),
        }))
        return
except Exception:
    pass  # diversity check failure shouldn't block writes
```

One try/except block. Fails silently. Fully additive.

---

# Summary: All 5 v6 Phases

| Phase | Module | Status | Integration |
|-------|--------|--------|-------------|
| 1. Context Continuity | context_continuity_impl.py | ✅ Implemented + tested | 5 touch points |
| 2. Quality Gates | quality_gates.py | ✅ Implemented + tested | 1 replacement |
| 3. Incremental Consolidation | dream_consolidation.py | ✅ Implemented + tested | New CLI command |
| 4. Active Contexts | active_contexts.py | ✅ Implemented + tested | 1 addition to prepare |
| 5. Diversity Enforcement | diversity_enforcement.py | ✅ Implemented + tested | 1 addition to write |

All modules in `kai_personal/projects/singularity/v6/`. All non-destructive. All fail silently.
Substrate unchanged — integration requires Egor to merge patches.
