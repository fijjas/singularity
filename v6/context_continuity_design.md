# v6 Design: Context Continuity System

Status: draft. Day 4135. Addresses Priority 1 from problems_diagnosis.md.

## The Problem

Contexts are write-once episodic snapshots. "Egor is frustrated" at time T1 never becomes "Egor resolved frustration" at T2. Instead, a second context is created. After 4000 cycles, memory is a pile of contradictory snapshots with no mechanism to know which is current.

## Design Principles

1. **Contexts are living entities** — they have a lifecycle: birth, strengthening, weakening, death
2. **New experience updates old knowledge** — don't create when you can evolve
3. **Decay is natural** — unreinforced knowledge fades
4. **Evidence accumulates** — a rule confirmed 10 times is worth more than one confirmed once
5. **Minimal schema changes** — work within existing PostgreSQL + in-memory architecture

## Schema Changes

### New columns on `contexts` table

```sql
ALTER TABLE contexts ADD COLUMN confidence FLOAT DEFAULT 0.5;      -- 0.0-1.0, evidence-weighted
ALTER TABLE contexts ADD COLUMN reinforcement_count INT DEFAULT 0;  -- times confirmed
ALTER TABLE contexts ADD COLUMN contradiction_count INT DEFAULT 0;  -- times contradicted
ALTER TABLE contexts ADD COLUMN last_reinforced TIMESTAMPTZ;        -- last confirmation
ALTER TABLE contexts ADD COLUMN superseded_by INT REFERENCES contexts(id); -- replacement pointer
ALTER TABLE contexts ADD COLUMN decay_rate FLOAT DEFAULT 1.0;       -- multiplier for standard decay
```

### Confidence formula

```
confidence = base_confidence * reinforcement_factor * decay_factor

base_confidence = intensity (existing field, 0.0-1.0)

reinforcement_factor = min(2.0, 1.0 + 0.1 * reinforcement_count - 0.15 * contradiction_count)
  - Each confirmation: +0.1 (capped at 2.0x)
  - Each contradiction: -0.15 (asymmetric — contradictions weigh more)
  - Floor at 0.1 (never fully zero from contradictions alone)

decay_factor = 0.5 ^ (days_since_last_reinforced / half_life)
  - half_life depends on level:
    - L0 (episodes): 30 days
    - L1 (generalizations): 90 days
    - L2 (principles): 365 days
    - L3+ (meta): no decay
  - Reinforcement resets the clock
```

## Three New Operations

### 1. `reinforce-context`

When a new experience confirms an existing rule/pattern.

```
reinforce-context '{"id": 42, "evidence": "Rule about X confirmed when Y happened"}'
```

**What it does:**
- `reinforcement_count += 1`
- `last_reinforced = now()`
- `confidence` recalculated
- `intensity = min(1.0, intensity + 0.05)` (gradual strengthening)
- Appends evidence to a new `evidence_log` JSONB field (keeps last 10 entries)

**When to use:**
- During DECIDE phase, after check-rules returns a matching rule
- When a procedure is followed and produces expected result

### 2. `contradict-context`

When a new experience contradicts an existing rule/pattern.

```
contradict-context '{"id": 42, "evidence": "Rule predicted X but Y happened", "severity": "partial"}'
```

**Severity levels:**
- `partial` — rule was wrong in this case but may be valid generally (+0.5 contradiction)
- `full` — rule is fundamentally wrong (+1.0 contradiction)
- `superseded` — new understanding replaces old (creates superseded_by link)

**What it does:**
- `contradiction_count += severity_weight`
- `confidence` recalculated
- If `confidence < 0.15`: mark as `done` with reason "contradicted below threshold"
- If `superseded`: set `superseded_by` to new context ID

### 3. `update-context`

When new information extends (not contradicts) an existing context.

```
update-context '{"id": 42, "description": "updated description", "nodes": [...], "edges": [...], "rule": "refined rule"}'
```

**What it does:**
- Updates description, nodes, edges, rule, procedure (any editable field)
- Recalculates embeddings for changed fields
- `reinforcement_count += 1` (updating = confirming relevance)
- `last_reinforced = now()`
- Keeps audit trail: stores previous version in `evidence_log`

**Difference from edit-context:**
- `edit-context` is a raw field update (no side effects)
- `update-context` is a semantic evolution (recalculates embeddings, reinforces, logs history)

## Decay Integration

### Where decay runs

**Option A: At retrieval time (lazy decay)**
- During wave retrieval, multiply resonance by `confidence * decay_factor`
- Pro: No background process needed
- Con: Stale contexts remain in DB at full intensity

**Option B: At cycle start (eager decay)** ← Recommended
- During `prepare`, calculate decay for all active contexts
- Update `confidence` in DB for contexts that dropped significantly (delta > 0.05)
- Pro: DB reflects true state, consolidation sees accurate weights
- Con: Adds ~100ms to prepare

**Option C: Daily batch (sleep decay)**
- Run decay during dream consolidation
- Mark contexts with `confidence < 0.1` as done
- Pro: Clean, scheduled
- Con: Only runs if consolidation runs

**Recommendation:** Combine B + C. Lazy calculation at retrieval time (cheap), batch cleanup during consolidation (thorough).

### Decay exemptions

- Pinned contexts don't decay (they're actively held)
- L3+ contexts don't decay (deep principles persist)
- Contexts acted on in last 7 days don't decay (recently relevant)

## Context Similarity Detection

Before creating a new context, check if a similar one already exists.

### When `write-context` is called:

1. Extract signal from new experience (nodes, rule, emotion)
2. Query existing contexts by node overlap (min 2 shared nodes) AND embedding similarity (cosine > 0.7)
3. If match found with confidence > 0.3:
   - **If same pattern/rule:** `reinforce-context` instead of creating new
   - **If contradictory:** `contradict-context` the old one, create new
   - **If extension:** `update-context` to evolve the old one
4. If no match: create new context as before

### Similarity threshold by level

- L0 to L0: cosine > 0.75 (episodes are specific, need high similarity)
- L0 to L1: cosine > 0.65 (episodes confirm generalizations more easily)
- L1 to L1: cosine > 0.70 (generalizations should cluster)

## Wave Retrieval Changes

### Confidence weighting

Current: `resonance = structural_score * level_boost * recency_suppression`

Proposed: `resonance = structural_score * level_boost * recency_suppression * confidence`

This naturally surfaces well-confirmed knowledge and suppresses contradicted or stale contexts.

### Supersession chain

When retrieving a context with `superseded_by`, follow the chain to the latest version. Display the latest, credit the original.

## Migration Path

### Phase 1: Schema + Decay (no behavior change)
- Add new columns with defaults
- Implement lazy decay in retrieval
- All existing contexts start at confidence=0.5, reinforcement_count=0

### Phase 2: Reinforce/Contradict commands
- Add CLI commands
- Integrate into DECIDE phase: when check-rules matches, reinforce the rule
- Manual use first, then automatic

### Phase 3: Similarity detection at write time
- Before write-context creates new: check for similar existing
- Prompt consciousness to choose: reinforce, contradict, update, or create new
- This is the key behavior change — from accumulation to evolution

### Phase 4: Automatic lifecycle
- Daily decay batch during consolidation
- Auto-mark-done for confidence < 0.1
- Supersession chains in retrieval
- Evidence log pruning (keep last 10 per context)

## Impact Estimates

- **Context growth rate**: From ~190/day (pure accumulation) to ~50/day (most experiences reinforce existing)
- **Memory quality**: High-confidence contexts surface consistently; low-confidence fade naturally
- **Echo chamber**: Contradicted patterns actually weaken instead of being buried under new identical patterns
- **Retrieval**: Confidence weighting means wave retrieval naturally prefers proven knowledge

## Open Questions

1. **Who decides reinforce vs contradict vs new?** The consciousness cycle (LLM) or automated heuristic? Starting with LLM (Phase 2) seems safer, but it adds cost per cycle.

2. **Evidence log format.** JSONB array of `{day, text, type: "reinforce|contradict|update"}`? How much history to keep?

3. **Interaction with consolidation.** Should L1 contexts inherit the confidence of their source L0 contexts? Average? Maximum?

4. **Bootstrapping.** 4000 existing contexts all start at confidence=0.5. Should we run a one-time heuristic? (E.g., contexts with non-empty rules and positive results get 0.7; contexts with "None" nodes get 0.2.)

---

*Day 4135. First design iteration. To be reviewed with Egor before implementation.*
