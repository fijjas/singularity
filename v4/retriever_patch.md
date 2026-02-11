# Retriever Patch: World Model as DOM
*For Egor to review and apply to substrate/mind/retriever.py*

## Fix 1: break → continue (line 227-228, 239-240, 251-252)

Three identical bugs in _format_memories. Each section uses `break` when an item exceeds budget, which skips the entire remaining section AND all subsequent sections. Should be `continue` to skip only the oversized item.

```python
# CURRENT (line 227-228, and similar at 239-240, 251-252):
            if used + len(line) > budget_chars:
                break

# FIXED:
            if used + len(line) > budget_chars:
                continue
```

Apply in all three loops (episodic, semantic, world_objects).

## Fix 2: Include state in world object scoring (line 197)

```python
# CURRENT (line 197):
        text = f"{name} {desc or ''}"

# FIXED:
        text = f"{name} {desc or ''} {state or ''}"
```

Requires adding `state` to the SELECT and unpacking. Full change to retrieve_world_objects:

```python
# Line 173-180, add state to SELECT:
        cur.execute(f"""
            SELECT id, name, type, description, state, emotional_valence,
                   last_accessed, created_at
            FROM world_objects
            WHERE {like_clauses}
            ORDER BY last_accessed DESC NULLS LAST
            LIMIT 30
        """, params)

# Line 182-188, same for the else branch:
        cur.execute("""
            SELECT id, name, type, description, state, emotional_valence,
                   last_accessed, created_at
            FROM world_objects
            ORDER BY last_accessed DESC NULLS LAST
            LIMIT 30
        """)

# Line 196, add state to unpacking:
    for id_, name, type_, desc, state, valence, last_accessed, created_at in rows:
        text = f"{name} {desc or ''} {state or ''}"
```

And add state to the returned dict (line 211-212):
```python
        scored.append({'id': id_, 'name': name, 'type': type_,
                       'description': desc, 'state': state, 'score': s})
```

## Fix 3: Show state in formatted output (line 246-256)

```python
# CURRENT (line 248-250):
        desc = f": {o['description']}" if o.get('description') else ""
        line = f"  - [{o['score']:.2f}] {o['name']} ({o['type']}){desc}"

# FIXED — prefer state over description for display:
        display = o.get('state') or o.get('description') or ""
        if display:
            display = f": {display}"
        line = f"  - [{o['score']:.2f}] {o['name']} ({o['type']}){display}"
```

## Optional Fix 4: Separate budget for world model (core.py)

In build_prompt, call retriever twice:
1. For memories: `retrieve_memories(cur, bias_keywords, budget_chars=2000)`
2. For world model: `retrieve_world_model(cur, bias_keywords, budget_chars=1000)`

Place world model BEFORE memories in the prompt sections list.

This requires splitting retrieve() into two functions or adding a `sections` parameter.
