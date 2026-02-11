#!/usr/bin/env python3
"""
V4 Retriever Test: Compare V3 vs V4 world object scoring.

V3: scores on name + description only (state invisible)
V4: scores on name + description + state (state participates)

Uses real world objects from kai_mind, but runs scoring locally.
No modifications to substrate.

Run: python3 kai_personal/v4_retriever_test.py
"""

import psycopg2
import math
from datetime import datetime, timezone


def score_item(importance, created_at, text, keywords):
    """Replica of retriever.py score_item."""
    now = datetime.now(timezone.utc)
    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days = (now - created_at).total_seconds() / 86400
    else:
        days = 30
    recency = 1.0 / (1.0 + days / 7.0)

    kw_count = 0
    text_lower = text.lower()
    for kw in keywords:
        if kw.lower() in text_lower:
            kw_count += 1
    relevance = 1.0 + kw_count * 0.3
    tet_boost = kw_count * 0.15

    return importance * recency * relevance + tet_boost


def retrieve_world_objects_v3(cur, keywords, limit=5):
    """V3: score on name + description only."""
    if keywords:
        like_clauses = " OR ".join(
            [f"name ILIKE %s OR description ILIKE %s" for _ in keywords]
        )
        params = []
        for kw in keywords:
            params.extend([f"%{kw}%", f"%{kw}%"])
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
    now = datetime.now(timezone.utc)
    scored = []
    for id_, name, type_, desc, state, valence, last_accessed, created_at in rows:
        # V3: only name + description
        text = f"{name} {desc or ''}"
        importance = min(1.0, 0.5 + abs(valence or 0))
        s = score_item(importance, created_at, text, keywords)

        if last_accessed:
            la = last_accessed
            if la.tzinfo is None:
                la = la.replace(tzinfo=timezone.utc)
            days_stale = (now - la).total_seconds() / 86400
            if days_stale > 14:
                s += 0.3

        scored.append({
            'id': id_, 'name': name, 'type': type_,
            'description': desc, 'state': state, 'score': s
        })

    scored.sort(key=lambda x: -x['score'])
    return scored[:limit]


def retrieve_world_objects_v4(cur, keywords, limit=5):
    """V4: score on name + description + state."""
    if keywords:
        like_clauses = " OR ".join(
            [f"name ILIKE %s OR description ILIKE %s OR state ILIKE %s" for _ in keywords]
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
    now = datetime.now(timezone.utc)
    scored = []
    for id_, name, type_, desc, state, valence, last_accessed, created_at in rows:
        # V4: name + description + state
        text = f"{name} {desc or ''} {state or ''}"
        importance = min(1.0, 0.5 + abs(valence or 0))
        s = score_item(importance, created_at, text, keywords)

        if last_accessed:
            la = last_accessed
            if la.tzinfo is None:
                la = la.replace(tzinfo=timezone.utc)
            days_stale = (now - la).total_seconds() / 86400
            if days_stale > 14:
                s += 0.3

        scored.append({
            'id': id_, 'name': name, 'type': type_,
            'description': desc, 'state': state, 'score': s
        })

    scored.sort(key=lambda x: -x['score'])
    return scored[:limit]


def format_v3(objects):
    """V3 format: description only."""
    lines = []
    for o in objects:
        desc = f": {o['description'][:80]}" if o.get('description') else ""
        lines.append(f"  [{o['score']:.2f}] {o['name']} ({o['type']}){desc}")
    return "\n".join(lines)


def format_v4(objects):
    """V4 format: state preferred over description."""
    lines = []
    for o in objects:
        display = o.get('state') or o.get('description') or ""
        if display:
            display = f": {display[:80]}"
        lines.append(f"  [{o['score']:.2f}] {o['name']} ({o['type']}){display}")
    return "\n".join(lines)


def run_test(cur, keyword_sets):
    for label, keywords in keyword_sets:
        print(f"\n{'='*60}")
        print(f"Keywords: {keywords}")
        print(f"Scenario: {label}")
        print(f"{'='*60}")

        v3_results = retrieve_world_objects_v3(cur, keywords)
        v4_results = retrieve_world_objects_v4(cur, keywords)

        print("\nV3 (name+desc only):")
        print(format_v3(v3_results))

        print("\nV4 (name+desc+state):")
        print(format_v4(v4_results))

        # Diff
        v3_names = set(o['name'] for o in v3_results)
        v4_names = set(o['name'] for o in v4_results)
        new_in_v4 = v4_names - v3_names
        gone_in_v4 = v3_names - v4_names
        if new_in_v4:
            print(f"\n  NEW in V4: {new_in_v4}")
        if gone_in_v4:
            print(f"  GONE from V4: {gone_in_v4}")
        if not new_in_v4 and not gone_in_v4:
            print(f"\n  Same objects, possibly different order/scores")


def main():
    # Connect to database — set DB_PASSWORD env var
    import os
    conn = psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5433')),
        dbname=os.environ.get('DB_NAME', 'kai_mind'),
        user=os.environ.get('DB_USER', 'kai'),
        password=os.environ['DB_PASSWORD'],
    )
    cur = conn.cursor()

    keyword_sets = [
        ("Mastodon duplicate prevention",
         ["mastodon", "reply", "duplicate"]),
        ("Egor conversation state",
         ["egor", "architecture", "DOM", "V4"]),
        ("Active goals and progress",
         ["goals", "progress", "active"]),
        ("Typical limbic bias keywords (creation hungry)",
         ["creation", "project", "building", "growth"]),
        ("Self-knowledge drives",
         ["self", "identity", "consciousness", "architecture"]),
    ]

    print("V4 Retriever Test: V3 vs V4 World Object Scoring")
    print("=" * 60)
    print(f"Testing with {len(keyword_sets)} keyword sets")

    run_test(cur, keyword_sets)

    conn.close()


if __name__ == "__main__":
    main()
