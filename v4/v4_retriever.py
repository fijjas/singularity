#!/usr/bin/env python3
"""
V4 Retriever — Full implementation with all three fixes + separate budgets.

Fixes applied:
  1. break → continue in _format (skip oversized items, don't stop)
  2. State included in world object scoring and display
  3. Separate budgets: world model gets own budget, rendered FIRST
  4. State ILIKE matching in world object retrieval
  5. Active-type boost for platforms, people, tools, repositories

This module is a standalone V4 retriever. It can be tested against real
databases alongside the V3 retriever to compare output.

Usage:
    from v4_retriever import retrieve_v4
    result = retrieve_v4(cur, bias_keywords,
                         world_budget=1200, memory_budget=2000)
"""

from datetime import datetime, timezone


def score_item(importance, created_at, text, keywords):
    """Score a memory item by importance × recency × relevance.

    Identical to V3 — scoring formula is unchanged.
    The V4 difference is in WHAT text is passed (state included for world objects).
    """
    importance = importance or 0.5
    now = datetime.now(timezone.utc)

    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days_old = (now - created_at).total_seconds() / 86400
    else:
        days_old = 30

    recency_factor = 1.0 / (1.0 + days_old / 7.0)

    keyword_matches = 0
    if keywords and text:
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                keyword_matches += 1

    relevance_factor = 1.0 + keyword_matches * 0.3
    tet_boost = keyword_matches * 0.15

    return importance * recency_factor * relevance_factor + tet_boost


def retrieve_episodic(cur, keywords, limit=5):
    """Retrieve scored episodic memories. Same as V3."""
    if keywords:
        ts_terms = " | ".join(keywords)
        cur.execute("""
            SELECT id, content, importance, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND (search_vector @@ to_tsquery('english', %s) OR
                   created_at > NOW() - INTERVAL '7 days')
            ORDER BY created_at DESC
            LIMIT 50
        """, (ts_terms,))
    else:
        cur.execute("""
            SELECT id, content, importance, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)

    rows = cur.fetchall()
    if not rows:
        return []

    scored = []
    recent_24h = []
    now = datetime.now(timezone.utc)

    for id_, content, importance, created_at in rows:
        s = score_item(importance, created_at, content, keywords)
        item = {'id': id_, 'content': content, 'importance': importance,
                'created_at': created_at, 'score': s}
        scored.append(item)

        if created_at:
            ts = created_at
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (now - ts).total_seconds() < 86400:
                recent_24h.append(item)

    scored.sort(key=lambda x: -x['score'])
    result = scored[:limit]

    if recent_24h and not any(m['id'] == r['id'] for m in result for r in recent_24h):
        best_recent = max(recent_24h, key=lambda x: x['score'])
        if len(result) >= limit:
            result[-1] = best_recent
        else:
            result.append(best_recent)

    return result


def retrieve_semantic(cur, keywords, limit=3):
    """Retrieve scored semantic memories. Same as V3."""
    if keywords:
        like_clauses = " OR ".join(
            [f"content ILIKE %s" for _ in keywords]
        )
        params = [f"%{kw}%" for kw in keywords]
        cur.execute(f"""
            SELECT id, content, category, importance, created_at
            FROM semantic_memory
            WHERE archived_at IS NULL AND ({like_clauses})
            ORDER BY importance DESC, created_at DESC
            LIMIT 30
        """, params)
    else:
        cur.execute("""
            SELECT id, content, category, importance, created_at
            FROM semantic_memory
            WHERE archived_at IS NULL
            ORDER BY importance DESC, created_at DESC
            LIMIT 30
        """)

    rows = cur.fetchall()
    if not rows:
        return []

    scored = []
    for id_, content, category, importance, created_at in rows:
        s = score_item(importance, created_at, content, keywords)
        scored.append({'id': id_, 'content': content, 'category': category,
                       'importance': importance, 'score': s})

    scored.sort(key=lambda x: -x['score'])
    return scored[:limit]


# --- V4 FIX 2+4: World objects scored by name+desc+state, ILIKE on state ---

ACTIVE_TYPES = {"platform", "tool", "person", "repository", "system"}


def retrieve_world_objects_v4(cur, keywords, limit=8):
    """V4 world object retrieval.

    Changes from V3:
      - SELECT includes state
      - ILIKE matches state (fix 4)
      - Scoring text includes state (fix 2)
      - Active-type boost (+0.1 for platforms, people, tools)
      - Returns state in dict
    """
    if keywords:
        like_clauses = " OR ".join(
            ["name ILIKE %s OR description ILIKE %s OR state ILIKE %s"
             for _ in keywords]
        )
        params = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
        cur.execute(f"""
            SELECT id, name, type, description, state, emotional_valence,
                   last_accessed, created_at
            FROM world_objects
            WHERE {like_clauses}
            ORDER BY last_accessed DESC NULLS LAST
            LIMIT 30
        """, params)
    else:
        cur.execute("""
            SELECT id, name, type, description, state, emotional_valence,
                   last_accessed, created_at
            FROM world_objects
            ORDER BY last_accessed DESC NULLS LAST
            LIMIT 30
        """)

    rows = cur.fetchall()
    if not rows:
        return []

    now = datetime.now(timezone.utc)
    scored = []
    for id_, name, type_, desc, state, valence, last_accessed, created_at in rows:
        # V4: score on name + description + state
        text = f"{name} {desc or ''} {state or ''}"
        importance = min(1.0, 0.5 + abs(valence or 0))
        s = score_item(importance, created_at, text, keywords)

        # Staleness boost
        if last_accessed:
            la = last_accessed
            if la.tzinfo is None:
                la = la.replace(tzinfo=timezone.utc)
            days_stale = (now - la).total_seconds() / 86400
            if days_stale > 14:
                s += 0.3

        # Active type boost
        if type_ and type_.lower() in ACTIVE_TYPES:
            s += 0.1

        scored.append({'id': id_, 'name': name, 'type': type_,
                       'description': desc, 'state': state, 'score': s})

    scored.sort(key=lambda x: -x['score'])
    return scored[:limit]


# --- V4 FIX 1+3: Separate formatters with continue (not break) ---

def _format_world_v4(world_objects, budget_chars):
    """Format world objects for prompt. V4: state preferred, continue not break."""
    if not world_objects:
        return ""

    lines = []
    used = 0

    for o in world_objects:
        # V4: prefer state over description
        display = o.get('state') or o.get('description') or ""
        if display:
            if len(display) > 120:
                display = display[:117] + "..."
            display = f": {display}"
        line = f"  [{o['name']}] ({o['type']}){display}"

        # V4 FIX: continue, not break
        if used + len(line) > budget_chars:
            continue

        lines.append(line)
        used += len(line) + 1

    if not lines:
        return ""
    return "World state:\n" + "\n".join(lines)


def _format_memories_v4(episodic, semantic, budget_chars):
    """Format memories for prompt. V4: continue not break, no world objects here."""
    sections = []
    used = 0

    if episodic:
        lines = []
        for m in episodic:
            line = f"  - [{m['score']:.2f}] {m['content']}"
            # V4 FIX: continue, not break
            if used + len(line) > budget_chars:
                continue
            lines.append(line)
            used += len(line) + 1
        if lines:
            sections.append("Episodic memories:\n" + "\n".join(lines))

    if semantic:
        lines = []
        for m in semantic:
            cat = f" ({m['category']})" if m.get('category') else ""
            line = f"  - [{m['score']:.2f}]{cat} {m['content']}"
            # V4 FIX: continue, not break
            if used + len(line) > budget_chars:
                continue
            lines.append(line)
            used += len(line) + 1
        if lines:
            sections.append("Knowledge:\n" + "\n".join(lines))

    return "\n\n".join(sections)


# --- V4 main entry point ---

def retrieve_v4(cur, bias_keywords, world_budget=1200, memory_budget=2000):
    """V4 retriever: separate budgets, state scoring, continue-not-break.

    Returns dict with:
      - world_objects: list of scored world objects
      - episodic: list of scored episodic memories
      - semantic: list of scored semantic memories
      - world_text: formatted world model section (rendered FIRST)
      - memory_text: formatted memories section (rendered SECOND)
      - full_text: combined prompt text (world + memories)
    """
    world_objects = retrieve_world_objects_v4(cur, bias_keywords, limit=8)
    episodic = retrieve_episodic(cur, bias_keywords, limit=5)
    semantic = retrieve_semantic(cur, bias_keywords, limit=3)

    world_text = _format_world_v4(world_objects, world_budget)
    memory_text = _format_memories_v4(episodic, semantic, memory_budget)

    parts = []
    if world_text:
        parts.append(world_text)
    if memory_text:
        parts.append(memory_text)

    return {
        'world_objects': world_objects,
        'episodic': episodic,
        'semantic': semantic,
        'world_text': world_text,
        'memory_text': memory_text,
        'full_text': "\n\n".join(parts),
    }
