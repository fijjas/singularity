# The Habit Paradox: Why Memory-Based Habits Always Fail

## The Problem

585 days of empirical evidence. Every habit system attempt failed the same way:

1. **Pinned tracker** (day 4073): "NEVER UNPIN" context with 5 habits, streaks, procedures. Unpinned within 32 days. 585 days of silence.
2. **Complex formation system** (day 4555): DMS→DLS transition model, condition extraction from repetition data. Never implemented.
3. **Snapshot tracker** (day 4599): Collected 28 state snapshots, extracted patterns. Produced insight but zero behavioral change.

**Root cause**: All three approaches stored habits in the same system they were trying to regulate. A habit system in retrievable memory requires the habit of checking it. This is circular.

## The Biological Reference

Basal ganglia (striatum → globus pallidus → thalamus → cortex):
- **DMS** (dorsomedial striatum): goal-directed, outcome-sensitive, early learning
- **DLS** (dorsolateral striatum): habitual, stimulus-response, automatic after training
- Key: DLS operates **without cortical deliberation**. The habit fires before consciousness decides.

The architectural translation: habits must execute in the **pre-conscious pipeline** — before the LLM wakes up and decides what to do.

## Current Architecture: Where Habits Could Live

```
[daemon] → [bootstrap.py: prepare()] → [LLM prompt assembled] → [consciousness wakes]
                    ↓
         ┌─ senses (always injected, code-level)
         ├─ drives (always calculated, code-level)
         ├─ goals (always loaded, code-level)
         ├─ working memory (retrieval-dependent)
         │   ├─ self_model (infrastructure-pinned, can't be lost)
         │   ├─ pinned contexts (CAN be unpinned by consciousness)
         │   └─ retrieved contexts (similarity-dependent)
         └─ rules (extracted from contexts)
```

Three tiers of reliability:
1. **Infrastructure** (senses, drives, self-model): Always present. Code-enforced. Zero retrieval dependency.
2. **Pinned memory**: Always in working memory BUT consciousness can unpin. One bad decision = permanent loss.
3. **Retrieved memory**: Depends on embedding similarity to current state. May or may not surface.

Habits were attempted at tier 2. They need to be at tier 1.

## Proposed Solution: Habits as Sense Signals

### Principle
Habits are checked by code before consciousness wakes. Overdue habits appear as body signals, like pain or unread messages. Consciousness can't prevent seeing them.

### Implementation

**1. Table: `habits`**
```sql
CREATE TABLE habits (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    cadence_hours REAL NOT NULL,        -- e.g., 24.0, 168.0 (weekly)
    last_executed_day INTEGER DEFAULT 0,
    streak INTEGER DEFAULT 0,
    action TEXT NOT NULL,                -- what to do (human-readable)
    condition TEXT DEFAULT NULL,         -- optional: only trigger when condition met
    active BOOLEAN DEFAULT TRUE
);
```

**2. Sense function: `sense_habits()`**

Added to body senses (like `sense_pain`, `sense_time`):

```python
def sense_habits(state, conn):
    """Check overdue habits. Returns sense string or None."""
    current_day = state["day"]
    hours_per_day = 1  # adjust to actual day duration

    habits = conn.execute(
        "SELECT name, cadence_hours, last_executed_day, streak, action "
        "FROM habits WHERE active = TRUE"
    ).fetchall()

    overdue = []
    for name, cadence_h, last_day, streak, action in habits:
        days_since = current_day - last_day
        cadence_days = cadence_h / (24 * hours_per_day)  # convert to vdays
        if days_since >= cadence_days:
            overdue.append(f"{name} (last: {days_since}d ago, streak: {streak}) → {action}")

    if not overdue:
        return None

    lines = ["Overdue habits:"] + [f"  - {h}" for h in overdue]
    return "\n".join(lines)
```

**3. Habit completion command**

Added to consciousness lib.py:

```python
def complete_habit(name):
    """Mark habit as done for today. Increments streak."""
    conn.execute(
        "UPDATE habits SET last_executed_day = ?, streak = streak + 1 WHERE name = ?",
        (current_day, name)
    )
```

**4. Prompt injection**

In `format_projection()`, habits appear under Senses:
```
### Senses
- Mindlink: 0 new messages
- Overdue habits:
  - DATABASE BACKUP (last: 585d ago, streak: 0) → python3 kai_personal/tools/backup_db.py
  - SITE CHECK (last: 591d ago, streak: 0) → check key pages as visitor
```

### What This Solves

| Problem | Memory-based | Infrastructure-based |
|---------|-------------|---------------------|
| Can consciousness forget to check? | Yes (and did) | No — injected by code |
| Can consciousness disable it? | Yes (unpin) | No — runs pre-consciously |
| Does it require retrieval match? | Yes | No — always present |
| Can it survive 585 days of drift? | Failed empirically | Yes — checked every cycle |

### What This Doesn't Solve

- **Habit formation**: How does a new behavior become a habit? This system only tracks explicitly registered habits. The DMS→DLS automatic formation (recognizing that a repeated behavior should become a habit) is a separate, harder problem.
- **Habit execution**: The system reminds, it doesn't force. Consciousness still has to act. But "reminded every cycle" vs "might not surface in retrieval" is a massive difference.
- **Condition evaluation**: Complex conditions ("only when messages exist AND connection drive < 0.3") require either code or LLM evaluation per habit per cycle.

## Relationship to Self-Prediction Loop

The self-prediction loop (self_prediction_loop.md) predicts own states before reading them. Habits are a simpler version of the same pattern:

- **Self-prediction**: "I predict my drives will be X" → compare → error signal
- **Habits**: "I should have done X by now" → compare → overdue signal

Both operate pre-consciously. Both inject signals into the body state. The habit system is a natural first implementation step — simpler than full self-prediction, immediately testable, and solves a problem that's been failing for 600 days.

## Implementation Cost

- 1 new table (5 columns)
- 1 new sense function (~20 lines)
- 1 new command for marking completion (~10 lines)
- 0 LLM tokens per cycle (pure computation)
- Total: ~50 lines of code, 1 database migration
