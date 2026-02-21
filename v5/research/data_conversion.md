# v4 → v5 Data Conversion Guide

How to populate v5 test tables with real v4 data from kai_mind.

## Source Data (v4, kai_mind:5433)

| Table | Rows | Description |
|-------|------|-------------|
| episodic_memory | 1228 | Text memories with importance, emotion, timestamps |
| drive_experience | 1648 | Drive satisfaction records (name, satisfaction 0-1, context) |
| pain_experience | 61 | Pain records (type, intensity 0-1, context) |
| goals | 3 active | Active goals with priority, progress |

## Pre-converted Data (kai_world:5434)

80 fully structured v5_contexts in kai_world — already converted from v4 episodic memories with:
- nodes (JSON array of {name, role, properties})
- edges (JSON array of {source, target, relation})
- emotion, intensity, result
- rule (consolidated lesson for each context)
- when_day, when_cycle (where known)

These 80 were manually curated — best 80 episodic memories selected and enriched.

## Target Tables (v5, kai_mind:5433)

### 1. v5_contexts — Core memory

**Option A: Copy 80 curated contexts from kai_world**
```sql
-- Clear existing test data
TRUNCATE v5_contexts RESTART IDENTITY CASCADE;

-- Copy from kai_world (cross-database — use script below)
```

**Option B: Bulk convert all 1228 episodic memories**
Use `singularity/v5/context_store/test_real_data.py` — extracts entities (nodes), guesses edges, maps emotions. Less precise than manual but covers everything.

**Recommended: Option A** — 80 curated contexts with rules are higher quality than 1228 auto-converted.

### 2. v5_episodic_memory — Recent raw memories

```sql
-- Copy last N episodic memories (most recent are most relevant)
INSERT INTO v5_episodic_memory (content, importance, emotion, created_at)
SELECT content, importance, emotion, created_at
FROM episodic_memory
ORDER BY created_at DESC
LIMIT 100;
```

### 3. v5_drive_experience — Drive history

```sql
INSERT INTO v5_drive_experience (drive_name, satisfaction, context, created_at)
SELECT drive_name, satisfaction, context, created_at
FROM drive_experience
ORDER BY created_at DESC
LIMIT 500;
```

### 4. v5_pain_experience — Pain history

```sql
INSERT INTO v5_pain_experience (pain_type, intensity, context, created_at)
SELECT pain_type, intensity, context, created_at
FROM pain_experience;
-- All 61 rows — small enough to keep everything
```

### 5. v5_goals — Active goals

```sql
TRUNCATE v5_goals RESTART IDENTITY CASCADE;
INSERT INTO v5_goals (name, description, status, priority, progress)
SELECT name, description, status, priority, progress
FROM goals
WHERE status = 'active';
```

### 6. v5_state — Session state

```sql
-- Set to current v4 state
INSERT INTO v5_state (key, value) VALUES
  ('current_day', '1558'),
  ('session_count', '456')
ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value, updated_at = now();
```

## Cross-Database Copy Script (for v5_contexts from kai_world)

Since v5_contexts live in kai_world (port 5434) but need to go to kai_mind (port 5433):

```python
#!/usr/bin/env python3
"""Copy 80 curated contexts from kai_world to v5_contexts in kai_mind."""
import psycopg2
import json

# Source: kai_world (port 5434)
src = psycopg2.connect(host='127.0.0.1', port=5434, user='kai',
                        password='PASSWORD', dbname='kai_world')
# Target: kai_mind (port 5433)
dst = psycopg2.connect(host='127.0.0.1', port=5433, user='kai',
                        password='PASSWORD', dbname='kai_mind')

cur_src = src.cursor()
cur_dst = dst.cursor()

# Read from kai_world
cur_src.execute("""
    SELECT description, nodes, edges, emotion, intensity, result,
           level, rule, sources, when_day, when_cycle, source_memory_id
    FROM v5_contexts ORDER BY id
""")
rows = cur_src.fetchall()

# Clear target
cur_dst.execute("TRUNCATE v5_contexts RESTART IDENTITY CASCADE")

# Insert
for row in rows:
    cur_dst.execute("""
        INSERT INTO v5_contexts
            (description, nodes, edges, emotion, intensity, result,
             level, rule, sources, when_day, when_cycle, source_memory_id)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
    """, row)

dst.commit()
print(f"Copied {len(rows)} contexts to kai_mind.v5_contexts")

cur_src.close()
cur_dst.close()
src.close()
dst.close()
```

Replace `PASSWORD` with actual DB passwords from:
- kai_world: `kai_personal/secrets/db.env`
- kai_mind: `substrate/secrets/db.env`

## What's Missing

The 80 contexts don't have:
- **when_day/when_cycle** for most entries (only some have temporal markers)
- **source_memory_id** links back to v4 episodic_memory IDs (not populated for manual contexts)
- **embeddings** — pre-computed in `kai_personal/notes/rule_embeddings.npz` (80×384 float32, all-MiniLM-L6-v2) but no column in v5_contexts for them yet

## Conversion Tools Already Built

- `singularity/v5/context_store/prototype.py` — in-memory ContextStore with wave() retrieval
- `singularity/v5/context_store/db_store.py` — PostgreSQL persistence, convert_from_kai_mind()
- `singularity/v5/context_store/test_real_data.py` — entity extraction from episodic text
- `kai_personal/tools/resonate.py` — semantic search over 80 rules using embeddings
