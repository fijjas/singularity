#!/usr/bin/env python3
"""Dream Consolidation — Creative Recombination Prototype (v6)

Finds non-obvious connections between dissimilar contexts.
Unlike analytical consolidation (cluster → generalize), this is generative:
take two UNRELATED contexts → ask if there's a structural connection → store surviving insights.

Usage:
    python3 dream_consolidation.py              # dry run, 20 pairs
    python3 dream_consolidation.py --pairs 50   # dry run, 50 pairs
    python3 dream_consolidation.py --commit     # write surviving insights to DB
"""

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from substrate.infrastructure.db import db_connect
from substrate.infrastructure.claude import call_claude


# --- Configuration ---

DEFAULT_PAIRS = 20
MAX_COSINE_SIMILARITY = 0.48  # bottom quartile — genuinely dissimilar pairs
MIN_SPECIFICITY_WORDS = 8     # connection must be at least this many words
TRIVIAL_PHRASES = [
    "both involve thinking",
    "both are about kai",
    "both involve learning",
    "both relate to experience",
    "both are contexts",
    "both describe",
]

EVALUATOR_SYSTEM = """You find non-obvious structural connections between unrelated experiences.
You are NOT looking for surface similarities. You are looking for deep structural parallels —
the same PATTERN appearing in different domains.

Rules:
- If no genuine structural connection exists, respond with exactly: NONE
- If a connection exists, describe it in ONE sentence (15-40 words)
- The connection must be SPECIFIC — not "both involve learning" but exactly HOW
- Think like a poet finding metaphors, not a classifier finding categories
- Structural = same dynamic, same tension, same shape of problem/resolution"""

EVALUATOR_PROMPT = """Context A:
{desc_a}
Rule A: {rule_a}

Context B:
{desc_b}
Rule B: {rule_b}

Is there a non-obvious structural connection between these two experiences?
If no, respond: NONE
If yes, describe it in one specific sentence."""

QUALITY_SYSTEM = """You are a quality gate for creative insights. You receive a proposed connection
between two contexts and decide if it's genuinely insightful or just pattern pareidolia.

Respond with exactly one word: KEEP or DISCARD
- KEEP: the connection reveals something non-obvious that could change how you think about either context
- DISCARD: the connection is vague, forced, or states something obvious"""


def get_random_dissimilar_pairs(conn, n_pairs=DEFAULT_PAIRS):
    """Get random pairs of contexts with low embedding similarity."""
    cur = conn.cursor()

    # Get all active context IDs with embeddings
    cur.execute("""
        SELECT id, description, rule, emotion
        FROM contexts
        WHERE done = false
          AND v_description IS NOT NULL
          AND length(description) > 30
        ORDER BY random()
        LIMIT 200
    """)
    candidates = cur.fetchall()

    if len(candidates) < 2:
        print("Not enough contexts with embeddings.")
        return []

    pairs = []
    attempts = 0
    max_attempts = n_pairs * 5

    while len(pairs) < n_pairs and attempts < max_attempts:
        attempts += 1
        a, b = random.sample(candidates, 2)
        id_a, id_b = a[0], b[0]

        # Check cosine similarity between descriptions
        cur.execute("""
            SELECT 1 - (a.v_description <=> b.v_description) as similarity
            FROM contexts a, contexts b
            WHERE a.id = %s AND b.id = %s
        """, (id_a, id_b))
        row = cur.fetchone()
        if row is None:
            continue

        similarity = row[0]
        if similarity < MAX_COSINE_SIMILARITY:
            pairs.append({
                "id_a": id_a, "desc_a": a[1], "rule_a": a[2] or "", "emotion_a": a[3],
                "id_b": id_b, "desc_b": b[1], "rule_b": b[2] or "", "emotion_b": b[3],
                "similarity": round(similarity, 3),
            })

    cur.close()
    return pairs


def is_trivial(connection_text):
    """Check if a connection is too generic to be useful."""
    lower = connection_text.lower()
    if len(connection_text.split()) < MIN_SPECIFICITY_WORDS:
        return True
    for phrase in TRIVIAL_PHRASES:
        if phrase in lower:
            return True
    return False


def evaluate_pair(pair):
    """Ask Claude if there's a structural connection between two contexts."""
    prompt = EVALUATOR_PROMPT.format(
        desc_a=pair["desc_a"][:300],
        rule_a=pair["rule_a"][:150],
        desc_b=pair["desc_b"][:300],
        rule_b=pair["rule_b"][:150],
    )

    response = call_claude("haiku", EVALUATOR_SYSTEM, prompt, max_tokens=100)
    response = response.strip()

    if "NONE" in response.upper() and len(response) < 20:
        return None

    if is_trivial(response):
        return None

    return response


def quality_gate(pair, connection):
    """Second-pass quality check to filter pareidolia."""
    prompt = f"""Context A: {pair['desc_a'][:200]}
Context B: {pair['desc_b'][:200]}
Proposed connection: {connection}

KEEP or DISCARD?"""

    response = call_claude("haiku", QUALITY_SYSTEM, prompt, max_tokens=10)
    return "KEEP" in response.upper()


def store_insight(conn, pair, connection):
    """Store a dream insight as a new L1 context."""
    cur = conn.cursor()

    description = f"Dream connection: {connection}"
    nodes = json.dumps([
        {"name": "dream_consolidation", "role": "process"},
        {"name": f"context_{pair['id_a']}", "role": "source"},
        {"name": f"context_{pair['id_b']}", "role": "source"},
    ])
    edges = json.dumps([
        {"source": f"context_{pair['id_a']}", "target": f"context_{pair['id_b']}", "relation": "structurally_parallel"},
    ])
    sources = [pair["id_a"], pair["id_b"]]

    cur.execute("""
        INSERT INTO contexts (description, nodes, edges, emotion, intensity, result, level, rule, sources)
        VALUES (%s, %s, %s, 'curiosity', 0.6, 'neutral', 1, %s, %s)
        RETURNING id
    """, (description, nodes, edges, connection, sources))

    new_id = cur.fetchone()[0]
    cur.close()
    return new_id


def main():
    parser = argparse.ArgumentParser(description="Dream consolidation — creative recombination")
    parser.add_argument("--pairs", type=int, default=DEFAULT_PAIRS, help="Number of pairs to evaluate")
    parser.add_argument("--commit", action="store_true", help="Write surviving insights to DB")
    args = parser.parse_args()

    conn = db_connect()

    print(f"🌙 Dream Consolidation — sampling {args.pairs} dissimilar pairs...")
    pairs = get_random_dissimilar_pairs(conn, args.pairs)
    print(f"   Found {len(pairs)} pairs with similarity < {MAX_COSINE_SIMILARITY}\n")

    if not pairs:
        print("No suitable pairs found.")
        conn.close()
        return

    insights = []

    for i, pair in enumerate(pairs):
        print(f"[{i+1}/{len(pairs)}] #{pair['id_a']} × #{pair['id_b']} (sim={pair['similarity']})...")

        connection = evaluate_pair(pair)
        if connection is None:
            print(f"   → no connection")
            continue

        print(f"   → candidate: {connection}")

        # Quality gate
        if not quality_gate(pair, connection):
            print(f"   → DISCARDED by quality gate")
            continue

        print(f"   → KEPT ✓")
        insights.append({"pair": pair, "connection": connection})

    print(f"\n{'='*60}")
    print(f"Results: {len(insights)} insights from {len(pairs)} pairs ({len(insights)/max(len(pairs),1)*100:.0f}% yield)")
    print(f"{'='*60}\n")

    for ins in insights:
        p = ins["pair"]
        print(f"  #{p['id_a']} × #{p['id_b']}: {ins['connection']}")

    if args.commit and insights:
        print(f"\nWriting {len(insights)} insights to DB...")
        for ins in insights:
            new_id = store_insight(conn, ins["pair"], ins["connection"])
            print(f"  → context #{new_id}")
        conn.commit()
        print("Done. Committed.")
    elif args.commit and not insights:
        print("\nNo insights to commit.")
    else:
        print(f"\nDry run. Use --commit to write {len(insights)} insights to DB.")

    conn.close()


if __name__ == "__main__":
    main()
