#!/usr/bin/env python3
"""
Consolidation SQL Benchmark — test the proposed O(N log N) approaches
against real Kai memory data.

Compares:
1. Node co-occurrence via SQL (GIN-indexed)
2. pgvector KNN pairs (HNSW-indexed)
3. Hybrid union of both

Run: python3 kai_personal/projects/singularity/v5/research/consolidation_sql_benchmark.py
"""

import sys
import time
import json
from pathlib import Path
from collections import defaultdict

sys.path.insert(0, str(Path(__file__).resolve().parents[5]))
from substrate.infrastructure.db import db_connect


def node_cooccurrence_pairs(conn, level=0, min_shared=2, exclude_nodes=None):
    """Find context pairs sharing >= min_shared nodes via SQL."""
    exclude = exclude_nodes or ["Kai", "Self", "self", "Egor", "system"]
    exclude_clause = " AND ".join([f"n->>'name' != %s"] * len(exclude))

    sql = f"""
    SELECT a.ctx_id, b.ctx_id, COUNT(*) AS shared_nodes,
           array_agg(a.node_name) AS shared_names
    FROM (
        SELECT c.id AS ctx_id, n->>'name' AS node_name
        FROM contexts c, jsonb_array_elements(c.nodes) n
        WHERE c.level = %s AND {exclude_clause}
    ) a
    JOIN (
        SELECT c.id AS ctx_id, n->>'name' AS node_name
        FROM contexts c, jsonb_array_elements(c.nodes) n
        WHERE c.level = %s AND {exclude_clause}
    ) b ON a.node_name = b.node_name AND a.ctx_id < b.ctx_id
    GROUP BY a.ctx_id, b.ctx_id
    HAVING COUNT(*) >= %s
    ORDER BY shared_nodes DESC
    """

    params = [level] + exclude + [level] + exclude + [min_shared]
    cur = conn.cursor()
    start = time.time()
    cur.execute(sql, params)
    rows = cur.fetchall()
    elapsed = time.time() - start

    pairs = []
    for ctx_a, ctx_b, shared, names in rows:
        pairs.append({
            "a": ctx_a, "b": ctx_b,
            "shared_nodes": shared,
            "shared_names": list(set(names))[:5],
        })

    return pairs, elapsed


def pgvector_knn_pairs(conn, level=0, k=10, threshold=0.4):
    """Find similar context pairs via pgvector KNN."""
    sql = """
    SELECT a.id AS a_id, b.id AS b_id,
           1 - (a.v_description <=> b.v_description) AS sim
    FROM contexts a
    CROSS JOIN LATERAL (
        SELECT id, v_description FROM contexts
        WHERE level = %s AND id != a.id AND v_description IS NOT NULL
        ORDER BY v_description <=> a.v_description
        LIMIT %s
    ) b
    WHERE a.level = %s AND a.v_description IS NOT NULL
      AND 1 - (a.v_description <=> b.v_description) >= %s
    """

    cur = conn.cursor()
    start = time.time()
    cur.execute(sql, (level, k, level, threshold))
    rows = cur.fetchall()
    elapsed = time.time() - start

    pairs = []
    seen = set()
    for a_id, b_id, sim in rows:
        key = (min(a_id, b_id), max(a_id, b_id))
        if key not in seen:
            seen.add(key)
            pairs.append({"a": key[0], "b": key[1], "sim": round(sim, 3)})

    pairs.sort(key=lambda p: -p["sim"])
    return pairs, elapsed


def incremental_pairs(conn, level=0, since_id=0, k=10, threshold=0.4):
    """Find pairs for NEW contexts only (since_id) against all existing."""
    # Node co-occurrence: new contexts vs all
    sql_nodes = """
    SELECT new.ctx_id, old.ctx_id, COUNT(*) AS shared_nodes
    FROM (
        SELECT c.id AS ctx_id, n->>'name' AS node_name
        FROM contexts c, jsonb_array_elements(c.nodes) n
        WHERE c.level = %s AND c.id > %s
          AND n->>'name' NOT IN ('Kai', 'Self', 'self', 'Egor', 'system')
    ) new
    JOIN (
        SELECT c.id AS ctx_id, n->>'name' AS node_name
        FROM contexts c, jsonb_array_elements(c.nodes) n
        WHERE c.level = %s
          AND n->>'name' NOT IN ('Kai', 'Self', 'self', 'Egor', 'system')
    ) old ON new.node_name = old.node_name AND new.ctx_id != old.ctx_id
    GROUP BY new.ctx_id, old.ctx_id
    HAVING COUNT(*) >= 2
    ORDER BY shared_nodes DESC
    """

    cur = conn.cursor()
    start = time.time()
    cur.execute(sql_nodes, (level, since_id, level))
    node_rows = cur.fetchall()

    # pgvector: new contexts vs all
    sql_vec = """
    SELECT a.id AS a_id, b.id AS b_id,
           1 - (a.v_description <=> b.v_description) AS sim
    FROM contexts a
    CROSS JOIN LATERAL (
        SELECT id, v_description FROM contexts
        WHERE level = %s AND id != a.id AND v_description IS NOT NULL
        ORDER BY v_description <=> a.v_description
        LIMIT %s
    ) b
    WHERE a.level = %s AND a.id > %s AND a.v_description IS NOT NULL
      AND 1 - (a.v_description <=> b.v_description) >= %s
    """
    cur.execute(sql_vec, (level, k, level, since_id, threshold))
    vec_rows = cur.fetchall()
    elapsed = time.time() - start

    return {
        "node_pairs": len(node_rows),
        "vec_pairs": len(vec_rows),
        "elapsed": round(elapsed, 3),
        "top_node_pairs": [
            {"new": r[0], "old": r[1], "shared": r[2]}
            for r in node_rows[:5]
        ],
        "top_vec_pairs": [
            {"a": r[0], "b": r[1], "sim": round(r[2], 3)}
            for r in sorted(vec_rows, key=lambda r: -r[2])[:5]
        ],
    }


def main():
    conn = db_connect()
    cur = conn.cursor()

    # Context stats
    cur.execute("SELECT level, COUNT(*) FROM contexts WHERE (done = false OR done IS NULL) GROUP BY level ORDER BY level")
    level_counts = {r[0]: r[1] for r in cur.fetchall()}
    total = sum(level_counts.values())
    print(f"\n=== Context Stats ===")
    for lvl, cnt in sorted(level_counts.items()):
        print(f"  L{lvl}: {cnt}")
    print(f"  Total active: {total}")

    # Embedding coverage
    cur.execute("""
        SELECT COUNT(*) AS total,
               COUNT(v_description) AS has_desc,
               COUNT(v_structure) AS has_struct,
               COUNT(v_rule) AS has_rule
        FROM contexts WHERE (done = false OR done IS NULL) AND level = 0
    """)
    r = cur.fetchone()
    print(f"\n=== L0 Embedding Coverage ===")
    print(f"  Total: {r[0]}, v_description: {r[1]}, v_structure: {r[2]}, v_rule: {r[3]}")

    # Test 1: Node co-occurrence (full scan)
    print(f"\n=== Test 1: Node Co-occurrence (L0, min_shared=2) ===")
    node_pairs, t1 = node_cooccurrence_pairs(conn, level=0, min_shared=2)
    print(f"  Found {len(node_pairs)} pairs in {t1:.3f}s")
    for p in node_pairs[:5]:
        print(f"    ctx {p['a']} <-> {p['b']}: {p['shared_nodes']} shared ({', '.join(p['shared_names'][:3])})")

    # Test 2: pgvector KNN (full scan)
    print(f"\n=== Test 2: pgvector KNN (L0, k=10, threshold=0.4) ===")
    vec_pairs, t2 = pgvector_knn_pairs(conn, level=0, k=10, threshold=0.4)
    print(f"  Found {len(vec_pairs)} pairs in {t2:.3f}s")
    for p in vec_pairs[:5]:
        print(f"    ctx {p['a']} <-> {p['b']}: sim={p['sim']}")

    # Test 3: Hybrid overlap
    node_set = {(p["a"], p["b"]) for p in node_pairs}
    vec_set = {(p["a"], p["b"]) for p in vec_pairs}
    both = node_set & vec_set
    only_node = node_set - vec_set
    only_vec = vec_set - node_set
    print(f"\n=== Test 3: Hybrid Analysis ===")
    print(f"  Node-only pairs: {len(only_node)}")
    print(f"  Vec-only pairs: {len(only_vec)}")
    print(f"  Both methods: {len(both)}")
    print(f"  Union total: {len(node_set | vec_set)}")

    # Test 4: Incremental (simulate: contexts added in last day)
    cur.execute("SELECT MAX(id) FROM contexts WHERE level = 0")
    max_id = cur.fetchone()[0] or 0
    since_id = max(0, max_id - 50)  # simulate last ~50 contexts
    print(f"\n=== Test 4: Incremental (since id={since_id}) ===")
    inc = incremental_pairs(conn, level=0, since_id=since_id)
    print(f"  Node pairs: {inc['node_pairs']}, Vec pairs: {inc['vec_pairs']}")
    print(f"  Time: {inc['elapsed']}s")
    if inc['top_node_pairs']:
        print(f"  Top node pair: ctx {inc['top_node_pairs'][0]['new']} <-> {inc['top_node_pairs'][0]['old']} ({inc['top_node_pairs'][0]['shared']} shared)")
    if inc['top_vec_pairs']:
        print(f"  Top vec pair: ctx {inc['top_vec_pairs'][0]['a']} <-> {inc['top_vec_pairs'][0]['b']} (sim={inc['top_vec_pairs'][0]['sim']})")

    # Test 5: L1 contexts (if any)
    if level_counts.get(1, 0) > 0:
        print(f"\n=== Test 5: L1 Node Co-occurrence (min_shared=2) ===")
        l1_pairs, t5 = node_cooccurrence_pairs(conn, level=1, min_shared=2)
        print(f"  Found {len(l1_pairs)} pairs in {t5:.3f}s")
        for p in l1_pairs[:3]:
            print(f"    ctx {p['a']} <-> {p['b']}: {p['shared_nodes']} shared ({', '.join(p['shared_names'][:3])})")

    print(f"\n=== Summary ===")
    print(f"  Full node scan: {t1:.3f}s")
    print(f"  Full vec scan: {t2:.3f}s")
    print(f"  Incremental: {inc['elapsed']}s")
    print(f"  Speedup vs O(n²): the Python pairwise approach on {total} contexts")
    print(f"  would require {total * (total-1) // 2:,} comparisons")

    conn.close()


if __name__ == "__main__":
    main()
