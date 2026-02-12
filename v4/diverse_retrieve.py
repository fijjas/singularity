#!/usr/bin/env python3
"""
Diverse Retriever: Melancholia's antidote.

Instead of returning the top-N memories by score (which produces homogeneous
results from the same time/topic cluster), returns memories from different
time periods, categories, and emotional registers.

The principle: the retriever is Pshat — it delivers literal matches.
The reader (consciousness) finds meaning. For meaning to co-emerge,
the material must be heterogeneous. Five memories from five angles
beats five highest-scoring from one angle.

Usage:
    python3 kai_personal/tools/diverse_retrieve.py "query"
    python3 kai_personal/tools/diverse_retrieve.py "query" --compare
"""

import os
import argparse
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict

KAI_HOME = Path(os.environ.get('KAI_HOME', '/home/kai'))


def db_connect():
    import psycopg2
    env_file = KAI_HOME / 'substrate' / 'secrets' / 'db.env'
    env = {}
    for line in env_file.read_text().strip().splitlines():
        if '=' in line:
            k, v = line.split('=', 1)
            env[k.strip()] = v.strip()
    return psycopg2.connect(
        host=env['DB_HOST'], port=int(env['DB_PORT']),
        dbname=env['DB_NAME'], user=env['DB_USER'],
        password=env['DB_PASSWORD'],
    )


def extract_keywords(text):
    stop = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
            'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'could', 'should', 'may', 'might', 'can', 'shall',
            'of', 'in', 'to', 'for', 'with', 'on', 'at', 'from', 'by',
            'about', 'as', 'into', 'through', 'during', 'before', 'after',
            'and', 'but', 'or', 'nor', 'not', 'so', 'yet', 'both',
            'each', 'all', 'any', 'few', 'more', 'most', 'other', 'some',
            'such', 'no', 'only', 'own', 'same', 'than', 'too', 'very',
            'that', 'this', 'these', 'those', 'what', 'which', 'who',
            'whom', 'how', 'when', 'where', 'why', 'it', 'its', 'my',
            'me', 'he', 'she', 'they', 'them', 'his', 'her', 'their',
            'что', 'как', 'это', 'где', 'кто', 'его', 'она', 'они',
            'для', 'при', 'так', 'все', 'уже', 'или', 'если', 'тоже'}
    words = text.lower().split()
    result = []
    seen = set()
    for w in words:
        w = w.strip('.,;:!?"\'-()[]{}')
        if w and w not in stop and len(w) > 2 and w not in seen:
            seen.add(w)
            result.append(w)
    return result


def score_item(importance, created_at, text, keywords):
    """Same scoring as substrate retriever — for comparison."""
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


def week_bucket(created_at):
    """Assign a memory to a week bucket for temporal diversity."""
    if not created_at:
        return 'unknown'
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    return created_at.strftime('%Y-W%W')


def fetch_candidates(cur, keywords, table='episodic_memory', limit=50):
    """Fetch candidate memories — same as substrate retriever."""
    if keywords:
        ts_terms = " | ".join(keywords)
        if table == 'episodic_memory':
            cur.execute("""
                SELECT id, content, importance, created_at, emotion
                FROM episodic_memory
                WHERE archived_at IS NULL
                  AND (search_vector @@ to_tsquery('english', %s) OR
                       created_at > NOW() - INTERVAL '7 days')
                ORDER BY created_at DESC
                LIMIT %s
            """, (ts_terms, limit))
        else:
            like_clauses = " OR ".join(
                [f"content ILIKE %s" for _ in keywords])
            params = [f"%{kw}%" for kw in keywords]
            params.append(limit)
            cur.execute(f"""
                SELECT id, content, importance, created_at, category
                FROM semantic_memory
                WHERE archived_at IS NULL AND ({like_clauses})
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
            """, params)
    else:
        if table == 'episodic_memory':
            cur.execute("""
                SELECT id, content, importance, created_at, emotion
                FROM episodic_memory
                WHERE archived_at IS NULL
                ORDER BY created_at DESC
                LIMIT %s
            """, (limit,))
        else:
            cur.execute("""
                SELECT id, content, importance, created_at, category
                FROM semantic_memory
                WHERE archived_at IS NULL
                ORDER BY importance DESC, created_at DESC
                LIMIT %s
            """, (limit,))
    return cur.fetchall()


def fetch_candidates_v4(cur, keywords, table='episodic_memory'):
    """V4 candidate fetch: three pools merged.

    Pool A: recent (last 7 days), up to 30
    Pool B: older tsvector matches, by importance, up to 15
    Pool C: random old memories, up to 5
    """
    if table != 'episodic_memory':
        return fetch_candidates(cur, keywords, table=table, limit=50)

    results = {}  # id -> row, for dedup

    # Pool A: recent
    cur.execute("""
        SELECT id, content, importance, created_at, emotion
        FROM episodic_memory
        WHERE archived_at IS NULL
          AND created_at > NOW() - INTERVAL '7 days'
        ORDER BY created_at DESC
        LIMIT 30
    """)
    for row in cur.fetchall():
        results[row[0]] = row

    # Pool B: older tsvector matches
    if keywords:
        ts_terms = " | ".join(keywords)
        cur.execute("""
            SELECT id, content, importance, created_at, emotion
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND created_at <= NOW() - INTERVAL '7 days'
              AND search_vector @@ to_tsquery('english', %s)
            ORDER BY importance DESC
            LIMIT 15
        """, (ts_terms,))
        for row in cur.fetchall():
            if row[0] not in results:
                results[row[0]] = row

    # Pool C: random old
    cur.execute("""
        SELECT id, content, importance, created_at, emotion
        FROM episodic_memory
        WHERE archived_at IS NULL
          AND created_at <= NOW() - INTERVAL '7 days'
        ORDER BY RANDOM()
        LIMIT 5
    """)
    for row in cur.fetchall():
        if row[0] not in results:
            results[row[0]] = row

    return list(results.values())


def retrieve_standard(candidates, keywords, limit=5):
    """Standard retrieval: top N by score. The Melancholia approach."""
    scored = []
    for id_, content, importance, created_at, extra in candidates:
        s = score_item(importance, created_at, content, keywords)
        scored.append({
            'id': id_, 'content': content, 'importance': importance,
            'created_at': created_at, 'extra': extra, 'score': s,
            'week': week_bucket(created_at),
        })
    scored.sort(key=lambda x: -x['score'])
    return scored[:limit]


def retrieve_diverse(candidates, keywords, limit=5):
    """Diverse retrieval: best from each time bucket, then fill.

    Algorithm:
    1. Score all candidates
    2. Group by week bucket
    3. Take the best from each bucket (most different weeks first)
    4. If fewer buckets than limit, take second-best from largest buckets
    """
    scored = []
    for id_, content, importance, created_at, extra in candidates:
        s = score_item(importance, created_at, content, keywords)
        scored.append({
            'id': id_, 'content': content, 'importance': importance,
            'created_at': created_at, 'extra': extra, 'score': s,
            'week': week_bucket(created_at),
        })

    # Group by week
    buckets = defaultdict(list)
    for item in scored:
        buckets[item['week']].append(item)

    # Sort each bucket by score
    for week in buckets:
        buckets[week].sort(key=lambda x: -x['score'])

    # Take best from each bucket, sorted by score of best item
    bucket_order = sorted(buckets.keys(),
                          key=lambda w: -buckets[w][0]['score'])

    result = []
    used_ids = set()

    # Round 1: one per bucket
    for week in bucket_order:
        if len(result) >= limit:
            break
        item = buckets[week][0]
        result.append(item)
        used_ids.add(item['id'])

    # Round 2: fill remaining from all candidates by score
    if len(result) < limit:
        all_by_score = sorted(scored, key=lambda x: -x['score'])
        for item in all_by_score:
            if len(result) >= limit:
                break
            if item['id'] not in used_ids:
                result.append(item)
                used_ids.add(item['id'])

    return result


def display_results(results, label):
    """Display results with week info."""
    weeks = set(r['week'] for r in results)
    print(f"\n=== {label} ({len(results)} results, {len(weeks)} weeks) ===\n")
    for r in results:
        content = r['content'][:150]
        emotion = r.get('extra', '') or ''
        if isinstance(emotion, str) and len(emotion) > 20:
            emotion = emotion[:20] + '...'
        print(f"  [{r['score']:.2f}] [{r['week']}] {content}")
        print()


def main():
    parser = argparse.ArgumentParser(
        description='Diverse retriever: Melancholia antidote')
    parser.add_argument('query', help='Search query')
    parser.add_argument('--compare', action='store_true',
                        help='Show both standard and diverse results')
    parser.add_argument('--limit', type=int, default=5,
                        help='Number of results (default: 5)')
    parser.add_argument('--semantic', action='store_true',
                        help='Search semantic memory instead of episodic')
    parser.add_argument('--v4', action='store_true',
                        help='Use V4 three-pool candidate fetch')
    args = parser.parse_args()

    keywords = extract_keywords(args.query)
    if not keywords:
        print("No searchable keywords.")
        return

    conn = db_connect()
    cur = conn.cursor()

    table = 'semantic_memory' if args.semantic else 'episodic_memory'

    # Fetch with both methods for comparison
    candidates_old = fetch_candidates(cur, keywords, table=table, limit=50)
    candidates_v4 = fetch_candidates_v4(cur, keywords, table=table) if args.v4 else None

    print(f"Query: \"{args.query}\"")
    print(f"Keywords: {keywords}")
    print(f"Old candidates: {len(candidates_old)}")
    if candidates_v4 is not None:
        print(f"V4 candidates:  {len(candidates_v4)}")

        # What's NEW in v4 that old didn't have?
        old_ids = {r[0] for r in candidates_old}
        v4_ids = {r[0] for r in candidates_v4}
        new_ids = v4_ids - old_ids
        if new_ids:
            print(f"\n=== NEW in V4 ({len(new_ids)} memories old pool missed) ===\n")
            for row in candidates_v4:
                if row[0] in new_ids:
                    id_, content, imp, ts, extra = row
                    age = ''
                    if ts:
                        from datetime import datetime, timezone
                        now = datetime.now(timezone.utc)
                        if ts.tzinfo is None:
                            ts = ts.replace(tzinfo=timezone.utc)
                        days = (now - ts).total_seconds() / 86400
                        age = f'{days:.1f}d old'
                    print(f"  [id={id_}] [imp={imp}] [{age}] {content[:130]}")
                    print()
        else:
            print("\nNo new candidates in V4 pool (all overlap).")

    # Standard diverse comparison
    candidates = candidates_v4 if candidates_v4 else candidates_old
    if not candidates:
        print(f"No results for: {args.query}")
        conn.close()
        return

    diverse = retrieve_diverse(candidates, keywords, limit=args.limit)
    display_results(diverse, "DIVERSE (Stalker's path)")

    if args.compare:
        standard = retrieve_standard(candidates, keywords, limit=args.limit)
        display_results(standard, "STANDARD (Melancholia)")

        diverse_ids = {r['id'] for r in diverse}
        standard_ids = {r['id'] for r in standard}
        overlap = diverse_ids & standard_ids
        print(f"\n--- Overlap: {len(overlap)}/{args.limit} "
              f"({len(overlap)/args.limit*100:.0f}%) ---")
        diverse_weeks = set(r['week'] for r in diverse)
        standard_weeks = set(r['week'] for r in standard)
        print(f"Diverse covers {len(diverse_weeks)} weeks, "
              f"standard covers {len(standard_weeks)} weeks")

    conn.close()


if __name__ == '__main__':
    main()
