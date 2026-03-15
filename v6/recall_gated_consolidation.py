#!/usr/bin/env python3
"""Recall-Gated Consolidation — the awake mechanism.

Unlike batch consolidation (consolidation.py) which scans all contexts O(N²),
this operates on the working memory window O(k²) where k ≈ 12.

Biological analogy: recall-gated plasticity. When multiple memories are
co-activated during waking, their overlap triggers generalization.
The gate is co-activation, not time.

Algorithm:
    1. Take working memory context IDs
    2. Fetch v_rule vectors (fallback: v_description)
    3. Compute pairwise cosine similarity
    4. Cluster contexts where sim > threshold
    5. For clusters of size >= 3: extract common rule via LLM
    6. Create L1 insight with source_ids
    7. Optionally mark superseded L0s done

Usage:
    python3 recall_gated_consolidation.py                    # dry-run on current window
    python3 recall_gated_consolidation.py --commit           # create insights
    python3 recall_gated_consolidation.py --ids 100,200,300  # specific context IDs
    python3 recall_gated_consolidation.py --threshold 0.65   # custom threshold
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from substrate.infrastructure.db import db_connect
from substrate.infrastructure.claude import call_claude


# --- Configuration ---

DEFAULT_SIMILARITY_THRESHOLD = 0.70  # cosine sim to consider "overlapping"
MIN_CLUSTER_SIZE = 3                 # minimum contexts to trigger consolidation
MAX_CLUSTER_SIZE = 8                 # prevent mega-clusters


# --- Vector operations ---

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    """Cosine similarity between two vectors."""
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def parse_pgvector(vec_str: str) -> np.ndarray:
    """Parse PostgreSQL vector string to numpy array."""
    return np.array([float(x) for x in vec_str.strip('[]').split(',')])


# --- Core algorithm ---

def fetch_vectors(conn, context_ids: list[int]) -> dict[int, np.ndarray]:
    """Fetch v_rule vectors for contexts, falling back to v_description."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, v_rule::text, v_description::text, level
        FROM contexts
        WHERE id = ANY(%s) AND (v_rule IS NOT NULL OR v_description IS NOT NULL)
    """, (context_ids,))

    vectors = {}
    for row in cur.fetchall():
        ctx_id, v_rule_str, v_desc_str, level = row
        # Prefer v_rule (captures what was learned), fall back to v_description
        vec_str = v_rule_str if v_rule_str else v_desc_str
        if vec_str:
            vectors[ctx_id] = parse_pgvector(vec_str)
    return vectors


def compute_similarity_matrix(vectors: dict[int, np.ndarray]) -> dict[tuple[int, int], float]:
    """Compute pairwise cosine similarity for all context pairs."""
    ids = sorted(vectors.keys())
    similarities = {}
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            sim = cosine_sim(vectors[ids[i]], vectors[ids[j]])
            similarities[(ids[i], ids[j])] = sim
    return similarities


def find_clusters(
    similarities: dict[tuple[int, int], float],
    all_ids: list[int],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    min_size: int = MIN_CLUSTER_SIZE,
    max_size: int = MAX_CLUSTER_SIZE,
) -> list[set[int]]:
    """Find clusters of contexts with pairwise similarity above threshold.

    Uses connected components on the similarity graph.
    """
    # Build adjacency from high-similarity pairs
    adj = defaultdict(set)
    for (a, b), sim in similarities.items():
        if sim >= threshold:
            adj[a].add(b)
            adj[b].add(a)

    # Connected components via BFS
    visited = set()
    clusters = []
    for start in all_ids:
        if start in visited or start not in adj:
            continue
        queue = [start]
        component = set()
        while queue:
            node = queue.pop(0)
            if node in visited:
                continue
            visited.add(node)
            component.add(node)
            for neighbor in adj[node]:
                if neighbor not in visited:
                    queue.append(neighbor)

        if min_size <= len(component) <= max_size:
            clusters.append(component)
        elif len(component) > max_size:
            # Split by raising threshold
            sub_sims = {
                (a, b): s for (a, b), s in similarities.items()
                if a in component and b in component
            }
            sub_clusters = find_clusters(
                sub_sims, sorted(component),
                threshold=threshold + 0.05,
                min_size=min_size, max_size=max_size,
            )
            clusters.extend(sub_clusters)

    return clusters


def fetch_context_details(conn, context_ids: set[int]) -> list[dict]:
    """Fetch full context details for a cluster."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, description, emotion, result, rule, procedure, level, nodes
        FROM contexts WHERE id = ANY(%s)
    """, (sorted(context_ids),))

    contexts = []
    for row in cur.fetchall():
        contexts.append({
            "id": row[0],
            "description": row[1],
            "emotion": row[2],
            "result": row[3],
            "rule": row[4] or "",
            "procedure": row[5] or "",
            "level": row[6],
            "nodes": row[7] if isinstance(row[7], list) else json.loads(row[7] or "[]"),
        })
    return contexts


# --- Generalization ---

RECALL_GATE_PROMPT = """You are a memory consolidation system operating during waking cognition.

These contexts are co-active in working memory right now. They were retrieved because they're relevant to the current moment. Your job: find the REAL pattern connecting them and extract it as a rule.

Requirements:
- The rule must be SPECIFIC and ACTIONABLE — not "learning is important"
- It must capture what these contexts share that makes them co-relevant NOW
- If no genuine pattern exists beyond surface similarity, respond with: NONE

Output JSON only:
{
  "description": "One sentence: what pattern connects these co-active memories",
  "rule": "The actionable principle (if X then Y)",
  "procedure": "Steps to apply this rule. Empty string if no clear procedure.",
  "emotion": "dominant emotion across these contexts",
  "result": "positive|negative|complex|neutral"
}

Return ONLY the JSON, nothing else. If no genuine pattern: just the word NONE."""


def generate_insight(contexts: list[dict]) -> dict | None:
    """Use LLM to extract insight from co-active cluster."""
    summaries = []
    for ctx in contexts[:8]:
        rule_part = f" Rule: {ctx['rule'][:100]}" if ctx.get('rule') else ""
        summaries.append(
            f"- [L{ctx['level']}] [{ctx['emotion']}] {ctx['description'][:150]}{rule_part}"
        )

    user_msg = (
        f"Cluster of {len(contexts)} co-active contexts in working memory:\n\n"
        + "\n".join(summaries)
        + "\n\nExtract the pattern that makes these co-relevant."
    )

    raw = call_claude("haiku", RECALL_GATE_PROMPT, user_msg, max_tokens=400)
    text = raw.strip()

    if text.upper() == "NONE":
        return None

    try:
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()
        return json.loads(text)
    except (json.JSONDecodeError, Exception) as e:
        print(f"  [WARN] LLM parse failed: {e}", file=sys.stderr)
        return None


# --- Dedup ---

def is_duplicate(conn, description: str, target_level: int = 1) -> bool:
    """Check if similar insight already exists."""
    try:
        from substrate.infrastructure.embeddings import embed_text, _vec_to_str
        vec = embed_text(description)
        vec_str = _vec_to_str(vec)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, 1 - (v_description <=> %s::vector) AS similarity
            FROM contexts
            WHERE v_description IS NOT NULL AND level >= %s
            ORDER BY v_description <=> %s::vector
            LIMIT 1
        """, (vec_str, target_level, vec_str))
        row = cur.fetchone()
        if row and row[1] >= 0.70:
            print(f"  Duplicate detected: existing context [{row[0]}] sim={row[1]:.3f}")
            return True
    except Exception as e:
        print(f"  [WARN] Dedup check failed: {e}", file=sys.stderr)
    return False


# --- Main ---

def recall_gated_consolidate(
    conn,
    context_ids: list[int],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    commit: bool = False,
) -> list[dict]:
    """Run recall-gated consolidation on given context IDs.

    Returns list of generated insights (as dicts).
    """
    print(f"Recall-gated consolidation: {len(context_ids)} contexts, threshold={threshold}")

    # Step 1: Fetch vectors
    vectors = fetch_vectors(conn, context_ids)
    print(f"  Vectors fetched: {len(vectors)}/{len(context_ids)}")

    if len(vectors) < MIN_CLUSTER_SIZE:
        print("  Not enough vectors for clustering.")
        return []

    # Step 2: Compute pairwise similarity
    similarities = compute_similarity_matrix(vectors)
    high_pairs = [(a, b, s) for (a, b), s in similarities.items() if s >= threshold]
    high_pairs.sort(key=lambda x: -x[2])

    print(f"  High-similarity pairs (>={threshold}): {len(high_pairs)}")
    for a, b, s in high_pairs[:5]:
        print(f"    [{a}] × [{b}] = {s:.3f}")

    # Step 3: Find clusters
    clusters = find_clusters(similarities, sorted(vectors.keys()), threshold=threshold)
    print(f"  Clusters found: {len(clusters)}")

    if not clusters:
        print("  No clusters above threshold.")
        return []

    # Step 4: For each cluster, generate insight
    insights = []
    for i, cluster_ids in enumerate(clusters):
        print(f"\n--- Cluster {i+1}: {sorted(cluster_ids)} ---")
        contexts = fetch_context_details(conn, cluster_ids)

        for ctx in contexts:
            print(f"  [{ctx['id']}] L{ctx['level']} {ctx['emotion']:10s} | {ctx['description'][:70]}")

        # Step 5: LLM extraction
        insight = generate_insight(contexts)
        if insight is None:
            print("  -> No genuine pattern found (LLM returned NONE)")
            continue

        print(f"  Pattern: {insight['description']}")
        print(f"  Rule: {insight.get('rule', '(none)')}")

        # Step 6: Dedup check
        if is_duplicate(conn, insight['description']):
            print("  -> SKIPPED (duplicate)")
            continue

        insight['source_ids'] = sorted(cluster_ids)
        insight['source_levels'] = [ctx['level'] for ctx in contexts]

        if commit:
            # Write as L1 insight via cortex
            from substrate.consciousness.mind.cortex.operations import cmd_write_insight
            insight_data = {
                "description": insight['description'],
                "rule": insight.get('rule', ''),
                "emotion": insight.get('emotion', 'neutral'),
                "source_ids": insight['source_ids'],
                "level": max(ctx['level'] for ctx in contexts) + 1,
            }
            # Direct DB write for reliability
            from substrate.consciousness.mind.consolidation import (
                write_generalization, merge_nodes, merge_edges,
            )
            target_level = insight_data['level']
            # Convert contexts to format expected by write_generalization
            cluster_eps = []
            for ctx in contexts:
                node_names = set()
                for n in ctx['nodes']:
                    name = n.get('name', '') if isinstance(n, dict) else str(n)
                    if name:
                        node_names.add(name)
                cluster_eps.append({
                    "id": ctx['id'],
                    "description": ctx['description'],
                    "nodes": node_names,
                    "nodes_raw": ctx['nodes'],
                    "edges": [],  # edges from detail fetch
                    "emotion": ctx['emotion'],
                    "result": ctx['result'],
                    "rule": ctx['rule'],
                })
            ctx_id = write_generalization(conn, insight, cluster_eps, target_level=target_level)
            print(f"  -> Written as context {ctx_id} (level {target_level})")
            insight['written_id'] = ctx_id
        else:
            print("  -> Would create insight (dry-run)")

        insights.append(insight)

    return insights


def get_current_window_ids(conn) -> list[int]:
    """Get context IDs from current working memory window (deduplicated)."""
    from substrate.consciousness.mind.window import load_window
    window = load_window(conn)
    seen = set()
    result = []
    for cid in window.context_ids + window.pinned_ids:
        if cid not in seen:
            seen.add(cid)
            result.append(cid)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recall-gated consolidation")
    parser.add_argument("--commit", action="store_true", help="Create insights in DB")
    parser.add_argument("--ids", type=str, help="Comma-separated context IDs")
    parser.add_argument("--threshold", type=float, default=DEFAULT_SIMILARITY_THRESHOLD)
    args = parser.parse_args()

    conn = db_connect()
    try:
        if args.ids:
            context_ids = [int(x.strip()) for x in args.ids.split(',')]
        else:
            context_ids = get_current_window_ids(conn)
            print(f"Using current window: {context_ids}")

        insights = recall_gated_consolidate(
            conn, context_ids,
            threshold=args.threshold,
            commit=args.commit,
        )

        print(f"\n{'='*50}")
        print(f"Results: {len(insights)} insights generated")
        for ins in insights:
            print(f"  Sources: {ins['source_ids']}")
            print(f"  {ins['description']}")
            print(f"  Rule: {ins.get('rule', '')}")
            print()
    finally:
        conn.close()
