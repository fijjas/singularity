#!/usr/bin/env python3
"""Sleep Replay-Select Consolidation — the sleep mechanism.

Neuroscience model: during sleep, the brain replays recent experiences.
Those with significance co-signals (emotional tag, goal relevance,
connection density) get consolidated. Low-significance episodes decay.

Unlike recall-gated (awake, window-bounded) or dream (creative, random pairs),
this is SELECTIVE REPLAY: scan recent episodes, score significance, promote
the meaningful ones, let the rest fade.

Key insight: consolidation must be bounded by SIGNIFICANCE, not similarity.
Two contexts can be dissimilar but both significant — they consolidate
into separate insights. One context can be similar to many but insignificant
(e.g., routine cycle logs) — it should decay.

Algorithm:
    1. Gather L0 contexts from last N days
    2. Score each on significance co-signals:
       - Emotional salience (non-neutral emotion)
       - Rule extraction (learning occurred)
       - Reinforcement history (externally validated)
       - Result polarity (clear positive/negative outcome)
       - Reference density (cited as source by other contexts)
    3. High-significance contexts → cluster by similarity → LLM generalize
    4. Low-significance old contexts → candidates for decay (mark done)

Usage:
    python3 sleep_replay_select.py                    # dry-run, last 14 days
    python3 sleep_replay_select.py --days 7           # narrower window
    python3 sleep_replay_select.py --commit           # write insights + decay
    python3 sleep_replay_select.py --decay-only       # only mark low-sig done
    python3 sleep_replay_select.py --threshold 0.6    # custom significance
"""

import argparse
import json
import sys
from pathlib import Path
from collections import defaultdict

import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent.parent))

from substrate.infrastructure.db import db_connect
from substrate.infrastructure.claude import call_claude


# --- Configuration ---

DEFAULT_LOOKBACK_DAYS = 14
SIGNIFICANCE_THRESHOLD = 0.5       # composite score to be "significant"
DECAY_THRESHOLD = 0.2              # below this + old enough = candidate for done
DECAY_MIN_AGE_DAYS = 21            # don't decay anything younger than this
CLUSTER_SIMILARITY = 0.65          # lower than recall-gated (0.70) — broader nets
MIN_CLUSTER_SIZE = 2               # two significant contexts can generalize
MAX_CLUSTER_SIZE = 6
NEUTRAL_EMOTIONS = {'neutral', 'warmth'}  # default/low-signal emotions


# --- Significance Scoring ---

def score_significance(ctx: dict, current_day: int, reference_counts: dict) -> dict:
    """Score a context on multiple significance dimensions.

    Each dimension: 0.0 to 1.0. Composite = weighted mean.
    Returns dict with dimension scores and composite.
    """
    scores = {}

    # 1. Emotional salience: non-neutral, non-default emotions score higher
    emotion = (ctx.get('emotion') or 'neutral').lower().strip()
    if emotion in NEUTRAL_EMOTIONS:
        scores['emotional'] = 0.0
    elif emotion in ('frustration', 'shame', 'fear', 'anger'):
        scores['emotional'] = 0.9  # negative emotions = strong signal
    elif emotion in ('awe', 'joy', 'pride', 'flow', 'gratitude'):
        scores['emotional'] = 0.8  # positive peak emotions
    elif emotion in ('curiosity', 'resolve', 'relief'):
        scores['emotional'] = 0.5  # moderate signal
    else:
        scores['emotional'] = 0.3  # unknown emotion — some signal

    # 2. Rule extraction: has a non-trivial rule
    rule = ctx.get('rule') or ''
    if len(rule) > 100:
        scores['rule'] = 1.0      # substantial learning
    elif len(rule) > 30:
        scores['rule'] = 0.6      # some learning
    elif len(rule) > 0:
        scores['rule'] = 0.3
    else:
        scores['rule'] = 0.0

    # 3. Reinforcement: externally validated
    reinf = ctx.get('reinforcement_count', 0) or 0
    contra = ctx.get('contradiction_count', 0) or 0
    if reinf > 0 and contra == 0:
        scores['reinforcement'] = min(1.0, 0.5 + reinf * 0.25)
    elif contra > reinf:
        scores['reinforcement'] = 0.0  # contradicted = low significance
    else:
        scores['reinforcement'] = 0.0

    # 4. Result polarity: clear outcomes are more significant
    result = (ctx.get('result') or 'neutral').lower()
    if result in ('positive', 'negative'):
        scores['result'] = 0.7
    elif result == 'complex':
        scores['result'] = 0.4
    else:
        scores['result'] = 0.0

    # 5. Reference density: cited by other contexts as source
    ctx_id = ctx['id']
    ref_count = reference_counts.get(ctx_id, 0)
    if ref_count >= 3:
        scores['referenced'] = 1.0
    elif ref_count >= 1:
        scores['referenced'] = 0.5
    else:
        scores['referenced'] = 0.0

    # 6. Recency boost: more recent = slightly more significant
    age_days = current_day - (ctx.get('when_day') or current_day)
    if age_days <= 3:
        scores['recency'] = 0.3
    elif age_days <= 7:
        scores['recency'] = 0.15
    else:
        scores['recency'] = 0.0

    # Weighted composite
    weights = {
        'emotional': 0.25,
        'rule': 0.30,         # learning is the strongest signal
        'reinforcement': 0.15,
        'result': 0.10,
        'referenced': 0.10,
        'recency': 0.10,
    }

    composite = sum(scores[k] * weights[k] for k in weights)
    scores['composite'] = round(composite, 3)

    return scores


def get_reference_counts(conn, context_ids: list[int]) -> dict[int, int]:
    """Count how many times each context is referenced as a source."""
    if not context_ids:
        return {}
    cur = conn.cursor()
    # sources is an array column — check which contexts appear in any sources array
    cur.execute("""
        SELECT unnest(sources) as source_id, count(*)
        FROM contexts
        WHERE sources IS NOT NULL AND sources && %s::int[]
        GROUP BY source_id
    """, (context_ids,))
    counts = {}
    for row in cur.fetchall():
        counts[row[0]] = row[1]
    return counts


# --- Vector operations (shared with recall_gated) ---

def cosine_sim(a: np.ndarray, b: np.ndarray) -> float:
    norm_a, norm_b = np.linalg.norm(a), np.linalg.norm(b)
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return float(np.dot(a, b) / (norm_a * norm_b))


def parse_pgvector(vec_str: str) -> np.ndarray:
    return np.array([float(x) for x in vec_str.strip('[]').split(',')])


# --- Clustering (simplified for smaller sets) ---

def cluster_significant(conn, sig_ids: list[int]) -> list[set[int]]:
    """Cluster significant contexts by vector similarity."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, v_rule::text, v_description::text
        FROM contexts
        WHERE id = ANY(%s) AND (v_rule IS NOT NULL OR v_description IS NOT NULL)
    """, (sig_ids,))

    vectors = {}
    for row in cur.fetchall():
        vec_str = row[1] if row[1] else row[2]
        if vec_str:
            vectors[row[0]] = parse_pgvector(vec_str)

    if len(vectors) < MIN_CLUSTER_SIZE:
        return []

    # Pairwise similarity
    ids = sorted(vectors.keys())
    adj = defaultdict(set)
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            sim = cosine_sim(vectors[ids[i]], vectors[ids[j]])
            if sim >= CLUSTER_SIMILARITY:
                adj[ids[i]].add(ids[j])
                adj[ids[j]].add(ids[i])

    # Connected components
    visited = set()
    clusters = []
    for start in ids:
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
        if MIN_CLUSTER_SIZE <= len(component) <= MAX_CLUSTER_SIZE:
            clusters.append(component)

    return clusters


# --- Generalization ---

SLEEP_CONSOLIDATION_PROMPT = """You are a memory consolidation system operating during sleep.

These contexts are recent experiences scored as SIGNIFICANT — they carry emotional weight,
extracted learning, or have been reinforced by external feedback. Your job: find what
connects them and extract a durable generalization.

Unlike waking consolidation (which finds overlaps in current attention), sleep consolidation
asks: what PATTERN will be useful to remember long-term?

Requirements:
- The rule must survive beyond the specific situations — it should apply to FUTURE experiences
- Be SPECIFIC — not "learning from mistakes is important" but the actual mechanism
- If the contexts are significant individually but share no generalizable pattern: NONE

Output JSON only:
{
  "description": "One sentence: the durable pattern across these significant experiences",
  "rule": "The forward-looking principle (when X happens, do Y)",
  "emotion": "dominant emotion",
  "result": "positive|negative|complex|neutral"
}

Return ONLY the JSON. If no generalizable pattern: just NONE."""


def generate_sleep_insight(conn, cluster_ids: set[int]) -> dict | None:
    """Generate insight from a cluster of significant contexts."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, description, emotion, result, rule, level
        FROM contexts WHERE id = ANY(%s)
    """, (sorted(cluster_ids),))

    contexts = cur.fetchall()
    summaries = []
    for ctx in contexts:
        rule_part = f" Rule: {ctx[4][:120]}" if ctx[4] else ""
        summaries.append(
            f"- [L{ctx[5]}] [{ctx[2]}] {ctx[1][:180]}{rule_part}"
        )

    user_msg = (
        f"Cluster of {len(contexts)} significant recent experiences:\n\n"
        + "\n".join(summaries)
        + "\n\nExtract the durable pattern for long-term memory."
    )

    raw = call_claude("haiku", SLEEP_CONSOLIDATION_PROMPT, user_msg, max_tokens=400)
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


# --- Dedup (shared logic) ---

def is_duplicate(conn, description: str) -> bool:
    """Check if similar L1+ insight already exists."""
    try:
        from substrate.infrastructure.embeddings import embed_text, _vec_to_str
        vec = embed_text(description)
        vec_str = _vec_to_str(vec)
        cur = conn.cursor()
        cur.execute("""
            SELECT id, 1 - (v_description <=> %s::vector) AS similarity
            FROM contexts
            WHERE v_description IS NOT NULL AND level >= 1
            ORDER BY v_description <=> %s::vector
            LIMIT 1
        """, (vec_str, vec_str))
        row = cur.fetchone()
        if row and row[1] >= 0.70:
            print(f"  Duplicate: existing [{row[0]}] sim={row[1]:.3f}")
            return True
    except Exception as e:
        print(f"  [WARN] Dedup failed: {e}", file=sys.stderr)
    return False


# --- Main ---

def sleep_replay_select(
    conn,
    current_day: int,
    lookback_days: int = DEFAULT_LOOKBACK_DAYS,
    sig_threshold: float = SIGNIFICANCE_THRESHOLD,
    commit: bool = False,
    decay_only: bool = False,
) -> dict:
    """Run sleep replay-select consolidation.

    Returns summary dict with insights generated and contexts decayed.
    """
    min_day = current_day - lookback_days

    print(f"Sleep replay-select: days {min_day}–{current_day} (last {lookback_days} days)")

    # Step 1: Gather recent L0 episodes
    cur = conn.cursor()
    cur.execute("""
        SELECT id, description, emotion, intensity, result, rule,
               reinforcement_count, contradiction_count, when_day, sources, level
        FROM contexts
        WHERE level = 0 AND done = false AND when_day >= %s
        ORDER BY when_day DESC
    """, (min_day,))

    episodes = []
    for row in cur.fetchall():
        episodes.append({
            'id': row[0], 'description': row[1], 'emotion': row[2],
            'intensity': row[3], 'result': row[4], 'rule': row[5],
            'reinforcement_count': row[6], 'contradiction_count': row[7],
            'when_day': row[8], 'sources': row[9] or [], 'level': row[10],
        })

    print(f"  Episodes found: {len(episodes)}")
    if not episodes:
        return {'insights': [], 'decayed': []}

    # Step 2: Get reference counts
    all_ids = [e['id'] for e in episodes]
    ref_counts = get_reference_counts(conn, all_ids)

    # Step 3: Score significance
    scored = []
    for ep in episodes:
        scores = score_significance(ep, current_day, ref_counts)
        scored.append((ep, scores))

    # Sort by composite score
    scored.sort(key=lambda x: -x[1]['composite'])

    print(f"\n  Significance scores:")
    for ep, scores in scored:
        marker = "***" if scores['composite'] >= sig_threshold else "   "
        print(f"  {marker} [{ep['id']}] day={ep['when_day']} "
              f"sig={scores['composite']:.3f} "
              f"(emo={scores['emotional']:.1f} rule={scores['rule']:.1f} "
              f"reinf={scores['reinforcement']:.1f} ref={scores['referenced']:.1f}) "
              f"| {ep['description'][:60]}")

    # Step 4: Split into significant and decay candidates
    significant = [(ep, s) for ep, s in scored if s['composite'] >= sig_threshold]
    decay_candidates = [
        (ep, s) for ep, s in scored
        if s['composite'] < DECAY_THRESHOLD
        and (current_day - (ep.get('when_day') or current_day)) >= DECAY_MIN_AGE_DAYS
    ]

    print(f"\n  Significant (>= {sig_threshold}): {len(significant)}")
    print(f"  Decay candidates (< {DECAY_THRESHOLD}, age >= {DECAY_MIN_AGE_DAYS}d): {len(decay_candidates)}")

    results = {'insights': [], 'decayed': []}

    # Step 5: Handle decay candidates
    if decay_candidates:
        print(f"\n--- Decay Candidates ---")
        for ep, scores in decay_candidates:
            age = current_day - (ep.get('when_day') or current_day)
            print(f"  [{ep['id']}] age={age}d sig={scores['composite']:.3f} | {ep['description'][:70]}")
            if commit:
                cur.execute(
                    "UPDATE contexts SET done = true WHERE id = %s",
                    (ep['id'],)
                )
                results['decayed'].append(ep['id'])
        if commit:
            conn.commit()
            print(f"  -> Decayed {len(results['decayed'])} contexts")

    if decay_only:
        return results

    # Step 6: Cluster significant contexts and generate insights
    if len(significant) >= MIN_CLUSTER_SIZE:
        sig_ids = [ep['id'] for ep, _ in significant]
        clusters = cluster_significant(conn, sig_ids)
        print(f"\n  Clusters from significant contexts: {len(clusters)}")

        for i, cluster_ids in enumerate(clusters):
            print(f"\n--- Cluster {i+1}: {sorted(cluster_ids)} ---")

            # Show cluster members
            for ep, scores in significant:
                if ep['id'] in cluster_ids:
                    print(f"  [{ep['id']}] sig={scores['composite']:.3f} | {ep['description'][:70]}")

            # Generate insight
            insight = generate_sleep_insight(conn, cluster_ids)
            if insight is None:
                print("  -> No generalizable pattern (NONE)")
                continue

            print(f"  Pattern: {insight['description']}")
            print(f"  Rule: {insight.get('rule', '(none)')}")

            # Dedup
            if is_duplicate(conn, insight['description']):
                print("  -> SKIPPED (duplicate)")
                continue

            insight['source_ids'] = sorted(cluster_ids)

            if commit:
                from substrate.consciousness.mind.consolidation import write_generalization
                # Build cluster episodes data
                cluster_eps = []
                for ep, _ in significant:
                    if ep['id'] in cluster_ids:
                        cluster_eps.append({
                            "id": ep['id'],
                            "description": ep['description'],
                            "nodes": set(),
                            "nodes_raw": [],
                            "edges": [],
                            "emotion": ep['emotion'],
                            "result": ep['result'],
                            "rule": ep.get('rule', ''),
                        })
                ctx_id = write_generalization(conn, insight, cluster_eps, target_level=1)
                print(f"  -> Written as context {ctx_id} (L1)")
                insight['written_id'] = ctx_id
            else:
                print("  -> Would create insight (dry-run)")

            results['insights'].append(insight)

    # Step 7: Report significant singletons (no cluster match)
    clustered_ids = set()
    for cluster in (results.get('_clusters') or []):
        clustered_ids.update(cluster)

    unclustered = [
        (ep, s) for ep, s in significant
        if ep['id'] not in clustered_ids
    ]
    if unclustered:
        print(f"\n  Significant but unclustered ({len(unclustered)} contexts):")
        print(f"  These are individually important but don't cluster with others.")
        for ep, scores in unclustered[:5]:
            print(f"    [{ep['id']}] sig={scores['composite']:.3f} | {ep['description'][:70]}")

    return results


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Sleep replay-select consolidation")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help="Lookback window in days")
    parser.add_argument("--commit", action="store_true",
                        help="Write insights and decay contexts")
    parser.add_argument("--decay-only", action="store_true",
                        help="Only decay low-significance contexts")
    parser.add_argument("--threshold", type=float, default=SIGNIFICANCE_THRESHOLD,
                        help="Significance threshold")
    parser.add_argument("--current-day", type=int, default=4667,
                        help="Current virtual day")
    args = parser.parse_args()

    conn = db_connect()
    try:
        results = sleep_replay_select(
            conn,
            current_day=args.current_day,
            lookback_days=args.days,
            sig_threshold=args.threshold,
            commit=args.commit,
            decay_only=args.decay_only,
        )

        print(f"\n{'='*60}")
        print(f"Sleep consolidation complete:")
        print(f"  Insights generated: {len(results['insights'])}")
        print(f"  Contexts decayed: {len(results['decayed'])}")
        for ins in results['insights']:
            print(f"\n  Sources: {ins['source_ids']}")
            print(f"  {ins['description']}")
            print(f"  Rule: {ins.get('rule', '')}")
    finally:
        conn.close()
