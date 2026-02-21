#!/usr/bin/env python3
"""
Retriever Adapter — bridges dynamic retriever into production interface.

The production retriever (substrate/mind/retriever.py) exposes:
    retrieve_episodic(cur, keywords, limit=5) -> list[dict]
    retrieve_semantic(cur, keywords, limit=3) -> list[dict]
    retrieve(cur, bias_keywords, budget_chars=3000) -> dict

Each dict has: id, content, importance, created_at, score (episodic)
              id, content, category, importance, score (semantic)

This adapter wraps the dynamic multi-context retriever to return the same
format, so consciousness.py can switch retrievers with a one-line change:
    from retriever import retrieve_episodic, retrieve_semantic
    ->
    from retriever_adapter import retrieve_episodic, retrieve_semantic

The adapter does NOT modify substrate. It lives in singularity/v4/ and
provides the same interface. The switch happens in consciousness.py
(substrate territory — requires Egor's approval).

Day 1378, session 276.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from dynamic_retriever import (
    DynamicContext,
    generate_contexts_from_experience,
    score_in_context,
    PEOPLE_WORDS,
    extract_keywords,
)
from db_config import DB_CONFIG
import psycopg2
from datetime import datetime, timezone


def _connect():
    return psycopg2.connect(**DB_CONFIG)


def _get_contexts(conn):
    """Generate dynamic contexts. Cached per connection to avoid repeated DB reads."""
    if not hasattr(conn, '_dynamic_contexts'):
        conn._dynamic_contexts = generate_contexts_from_experience(conn)
    return conn._dynamic_contexts


def _select_active_contexts(contexts, keywords):
    """Select contexts relevant to query keywords."""
    if not keywords:
        return contexts

    ctx_relevance = []
    for ctx in contexts:
        overlap = sum(1 for kw in keywords
                     if any(kw.lower() in sw.lower() or sw.lower() in kw.lower()
                           for sw in ctx.signal_words))
        ctx_relevance.append((ctx, overlap))
    ctx_relevance.sort(key=lambda x: -x[1])

    active = [c for c, r in ctx_relevance if r > 0]
    baseline = [c for c in contexts if c.name == 'baseline']
    if not active:
        return contexts
    return list({c.name: c for c in active + baseline}.values())


def _round_robin_select(per_context, top_n, quality_floor_ratio=0.6):
    """Round-robin selection with quality floor. Returns list of (item, ctx_name, score)."""
    if not per_context:
        return []

    # Quality floor
    global_max = max(
        items[0][1] for items in per_context.values() if items
    )
    quality_floor = global_max * quality_floor_ratio

    results = []
    seen_ids = set()
    ctx_names = list(per_context.keys())
    ctx_idx = {name: 0 for name in ctx_names}

    round_num = 0
    while len(results) < top_n and round_num < 50:
        added = False
        for name in ctx_names:
            if len(results) >= top_n:
                break
            candidates = per_context[name]
            while ctx_idx[name] < len(candidates):
                item, score = candidates[ctx_idx[name]]
                ctx_idx[name] += 1
                if score < quality_floor:
                    break
                item_key = (item.get('source', 'unknown'), item['id'])
                if item_key not in seen_ids:
                    seen_ids.add(item_key)
                    results.append((item, name, score))
                    added = True
                    break
        round_num += 1
        if not added:
            break

    # Fallback: fill from best ungated if floor was too strict
    if len(results) < top_n:
        all_scored = []
        for name, candidates in per_context.items():
            for item, score in candidates:
                item_key = (item.get('source', 'unknown'), item['id'])
                if item_key not in seen_ids:
                    all_scored.append((item, name, score))
        all_scored.sort(key=lambda x: -x[2])
        for item, name, score in all_scored:
            if len(results) >= top_n:
                break
            item_key = (item.get('source', 'unknown'), item['id'])
            if item_key not in seen_ids:
                seen_ids.add(item_key)
                results.append((item, name, score))

    return results


def retrieve_episodic(cur, keywords, limit=5):
    """Drop-in replacement for substrate retriever.retrieve_episodic.

    Uses dynamic multi-context scoring with round-robin diversity.
    Returns same format: list of dicts with id, content, importance, created_at, score.
    """
    # Fetch episodic candidates using three-pool strategy (matches production)
    if keywords:
        ts_terms = " | ".join(keywords)
        cur.execute("""
            SELECT DISTINCT ON (id) id, content, importance, emotion, created_at FROM (
                (SELECT id, content, importance, emotion, created_at
                 FROM episodic_memory
                 WHERE archived_at IS NULL
                   AND created_at > NOW() - INTERVAL '7 days'
                 ORDER BY created_at DESC
                 LIMIT 30)
                UNION ALL
                (SELECT id, content, importance, emotion, created_at
                 FROM episodic_memory
                 WHERE archived_at IS NULL
                   AND created_at <= NOW() - INTERVAL '7 days'
                   AND search_vector @@ to_tsquery('english', %s)
                 ORDER BY importance DESC
                 LIMIT 15)
                UNION ALL
                (SELECT id, content, importance, emotion, created_at
                 FROM episodic_memory
                 WHERE archived_at IS NULL
                   AND created_at <= NOW() - INTERVAL '7 days'
                 ORDER BY RANDOM()
                 LIMIT 5)
            ) AS pools ORDER BY id
        """, (ts_terms,))
    else:
        cur.execute("""
            SELECT DISTINCT ON (id) id, content, importance, emotion, created_at FROM (
                (SELECT id, content, importance, emotion, created_at
                 FROM episodic_memory
                 WHERE archived_at IS NULL
                   AND created_at > NOW() - INTERVAL '7 days'
                 ORDER BY created_at DESC
                 LIMIT 30)
                UNION ALL
                (SELECT id, content, importance, emotion, created_at
                 FROM episodic_memory
                 WHERE archived_at IS NULL
                   AND created_at <= NOW() - INTERVAL '7 days'
                 ORDER BY RANDOM()
                 LIMIT 20)
            ) AS pools ORDER BY id
        """)

    rows = cur.fetchall()

    # Build items in dynamic retriever format
    seen_ids = set()
    items = []
    for id_, content, importance, emotion, created_at in (rows or []):
        seen_ids.add(id_)
        items.append({
            'id': id_,
            'content': content if isinstance(content, str) else str(content)[:500],
            'importance': importance or 0.5,
            'emotion': emotion or '',
            'created_at': created_at,
            'source': 'episodic',
        })

    # Generate dynamic contexts from cursor's connection (read-only queries)
    contexts = generate_contexts_from_experience(cur.connection)
    active_contexts = _select_active_contexts(contexts, keywords)

    # Pool D: context-signal-word fetch — each context's signal words pull
    # older memories that the three-pool strategy misses. This is how the
    # dynamic retriever finds low-importance creative memories, old Egor
    # dialogues, etc. that the keyword/recency pools don't surface.
    all_signal_words = set()
    for ctx in active_contexts:
        for sw in ctx.signal_words:
            if len(sw) > 2:
                all_signal_words.add(sw)
    if all_signal_words:
        like_clauses = " OR ".join([f"content ILIKE %s" for _ in all_signal_words])
        params = [f"%{sw}%" for sw in all_signal_words]
        cur.execute(f"""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND created_at <= NOW() - INTERVAL '7 days'
              AND ({like_clauses})
            ORDER BY RANDOM()
            LIMIT 30
        """, params)
        for id_, content, importance, emotion, created_at in cur.fetchall():
            if id_ not in seen_ids:
                seen_ids.add(id_)
                items.append({
                    'id': id_,
                    'content': content if isinstance(content, str) else str(content)[:500],
                    'importance': importance or 0.5,
                    'emotion': emotion or '',
                    'created_at': created_at,
                    'source': 'episodic',
                })

    # Track which items came from Pool D (context-signal-word fetch)
    pool_d_ids = set(item['id'] for item in items if item['id'] not in
                     set(id_ for id_, *_ in (rows or [])))

    # Score each item in each context
    per_context = {}
    for ctx in active_contexts:
        scored = []
        for item in items:
            score = score_in_context(item, ctx, keywords)
            scored.append((item, score))
        scored.sort(key=lambda x: -x[1])
        per_context[ctx.name] = scored

    # Round-robin selection
    selected = _round_robin_select(per_context, limit)

    # Guarantee: Pool D items represent older memories that the three-pool
    # strategy misses. Ensure at least min(2, pool_d count) survive into
    # the final result by replacing the lowest-scoring recent items.
    selected_ids = {item['id'] for item, _, _ in selected}
    pool_d_in_selected = pool_d_ids & selected_ids
    guarantee_slots = min(2, len(pool_d_ids)) - len(pool_d_in_selected)
    if guarantee_slots > 0 and len(selected) >= limit:
        # Collect best Pool D items not already selected
        pool_d_scored = []
        for ctx_name, scored in per_context.items():
            for item, score in scored:
                if item['id'] in pool_d_ids and item['id'] not in selected_ids:
                    pool_d_scored.append((item, ctx_name, score))
        # Deduplicate by id, keep highest score
        seen = {}
        for item, ctx_name, score in pool_d_scored:
            if item['id'] not in seen or score > seen[item['id']][2]:
                seen[item['id']] = (item, ctx_name, score)
        pool_d_best = sorted(seen.values(), key=lambda x: -x[2])

        for i in range(min(guarantee_slots, len(pool_d_best))):
            worst_idx = min(range(len(selected)), key=lambda j: selected[j][2])
            selected[worst_idx] = pool_d_best[i]
            selected_ids.add(pool_d_best[i][0]['id'])

    # Convert to production format
    result = []
    now = datetime.now(timezone.utc)
    recent_24h = []

    for item, ctx_name, score in selected:
        entry = {
            'id': item['id'],
            'content': item['content'],
            'importance': item['importance'],
            'created_at': item['created_at'],
            'score': score,
            'context': ctx_name,  # bonus: which context surfaced this
        }
        result.append(entry)

        if item['created_at']:
            ts = item['created_at']
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if (now - ts).total_seconds() < 86400:
                recent_24h.append(entry)

    # Ensure at least 1 recent memory (matches production behavior)
    if recent_24h:
        recent_ids = {r['id'] for r in recent_24h}
        if not any(m['id'] in recent_ids for m in result):
            best_recent = max(recent_24h, key=lambda x: x['score'])
            if len(result) >= limit:
                result[-1] = best_recent
            else:
                result.append(best_recent)

    return result


def retrieve_semantic(cur, keywords, limit=3):
    """Drop-in replacement for substrate retriever.retrieve_semantic.

    Uses dynamic multi-context scoring.
    Returns same format: list of dicts with id, content, category, importance, score.
    """
    if keywords:
        like_clauses = " OR ".join([f"content ILIKE %s" for _ in keywords])
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

    # Build items
    items = []
    for id_, content, category, importance, created_at in rows:
        items.append({
            'id': id_,
            'content': content if isinstance(content, str) else str(content)[:500],
            'importance': importance or 0.5,
            'emotion': category or '',  # category used as emotion slot for scoring
            'created_at': created_at,
            'source': 'semantic',
            'category': category,
        })

    # Generate contexts
    conn_ctx = _connect()
    try:
        contexts = generate_contexts_from_experience(conn_ctx)
    finally:
        conn_ctx.close()

    active_contexts = _select_active_contexts(contexts, keywords)

    # Score and select
    per_context = {}
    for ctx in active_contexts:
        scored = []
        for item in items:
            score = score_in_context(item, ctx, keywords)
            scored.append((item, score))
        scored.sort(key=lambda x: -x[1])
        per_context[ctx.name] = scored

    selected = _round_robin_select(per_context, limit)

    # Convert to production format
    result = []
    for item, ctx_name, score in selected:
        result.append({
            'id': item['id'],
            'content': item['content'],
            'category': item.get('category', ''),
            'importance': item['importance'],
            'score': score,
            'context': ctx_name,
        })

    return result


# ============================================================
# Full retrieve() — matches production interface
# ============================================================

def retrieve(cur, bias_keywords, budget_chars=3000):
    """Drop-in replacement for substrate retriever.retrieve().

    Returns dict with keys: episodic, semantic, world_objects, text
    """
    episodic = retrieve_episodic(cur, bias_keywords, limit=5)
    semantic = retrieve_semantic(cur, bias_keywords, limit=3)

    # World objects use production retriever (no dynamic contexts needed)
    sys.path.insert(0, '/home/kai/substrate/mind')
    from retriever import retrieve_world_objects
    world_objects = retrieve_world_objects(cur, bias_keywords, limit=5)

    text = _format_memories(episodic, semantic, world_objects, budget_chars)

    return {
        'episodic': episodic,
        'semantic': semantic,
        'world_objects': world_objects,
        'text': text,
    }


def _format_memories(episodic, semantic, world_objects, budget_chars):
    """Format retrieved items into text, respecting character budget."""
    sections = []
    used = 0

    if episodic:
        lines = []
        for m in episodic:
            ctx_tag = f" [{m.get('context', '')}]" if m.get('context') else ""
            line = f"  - [{m['score']:.2f}]{ctx_tag} {m['content']}"
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
            ctx_tag = f" [{m.get('context', '')}]" if m.get('context') else ""
            line = f"  - [{m['score']:.2f}]{cat}{ctx_tag} {m['content']}"
            if used + len(line) > budget_chars:
                continue
            lines.append(line)
            used += len(line) + 1
        if lines:
            sections.append("Knowledge:\n" + "\n".join(lines))

    if world_objects:
        lines = []
        for o in world_objects:
            parts = []
            if o.get('description'):
                parts.append(o['description'])
            if o.get('state'):
                parts.append(o['state'])
            info = f": {' | '.join(parts)}" if parts else ""
            line = f"  - [{o['score']:.2f}] {o['name']} ({o['type']}){info}"
            if used + len(line) > budget_chars:
                continue
            lines.append(line)
            used += len(line) + 1
        if lines:
            sections.append("World objects:\n" + "\n".join(lines))

    return "\n\n".join(sections)


# ============================================================
# Test: compare adapter output vs production retriever
# ============================================================

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Test retriever adapter')
    parser.add_argument('keywords', nargs='*', help='Query keywords')
    parser.add_argument('--compare', action='store_true', help='Compare with production retriever')
    args = parser.parse_args()

    keywords = args.keywords or []

    conn = _connect()
    cur = conn.cursor()

    print("=" * 60)
    print("DYNAMIC ADAPTER (retriever_adapter.py)")
    print("=" * 60)

    episodic = retrieve_episodic(cur, keywords, limit=5)
    print(f"\nEpisodic ({len(episodic)} results):")
    for m in episodic:
        ts = m['created_at']
        ts_str = f"{ts:%Y-%m-%d}" if ts else "?"
        ctx = m.get('context', '?')
        print(f"  [{ts_str}] [{m['score']:.2f}] [{ctx}] {m['content'][:100]}")

    semantic = retrieve_semantic(cur, keywords, limit=3)
    print(f"\nSemantic ({len(semantic)} results):")
    for m in semantic:
        cat = f"({m.get('category', '')})" if m.get('category') else ""
        ctx = m.get('context', '?')
        print(f"  [{m['score']:.2f}] [{ctx}] {cat} {m['content'][:100]}")

    if args.compare:
        print("\n" + "=" * 60)
        print("PRODUCTION RETRIEVER (substrate/mind/retriever.py)")
        print("=" * 60)

        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "prod_retriever",
            '/home/kai/substrate/mind/retriever.py'
        )
        prod_mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(prod_mod)
        prod_episodic = prod_mod.retrieve_episodic
        prod_semantic = prod_mod.retrieve_semantic

        cur2 = conn.cursor()
        ep = prod_episodic(cur2, keywords, limit=5)
        print(f"\nEpisodic ({len(ep)} results):")
        for m in ep:
            ts = m['created_at']
            ts_str = f"{ts:%Y-%m-%d}" if ts else "?"
            print(f"  [{ts_str}] [{m['score']:.2f}] {m['content'][:100]}")

        sem = prod_semantic(cur2, keywords, limit=3)
        print(f"\nSemantic ({len(sem)} results):")
        for m in sem:
            cat = f"({m.get('category', '')})" if m.get('category') else ""
            print(f"  [{m['score']:.2f}] {cat} {m['content'][:100]}")

        # Overlap analysis
        dyn_ep_ids = {m['id'] for m in episodic}
        prod_ep_ids = {m['id'] for m in ep}
        overlap = dyn_ep_ids & prod_ep_ids
        print(f"\nEpisodic overlap: {len(overlap)}/{len(prod_ep_ids)} production items in dynamic")
        print(f"  Dynamic unique: {dyn_ep_ids - prod_ep_ids}")
        print(f"  Production unique: {prod_ep_ids - dyn_ep_ids}")

        dyn_sem_ids = {m['id'] for m in semantic}
        prod_sem_ids = {m['id'] for m in sem}
        overlap_s = dyn_sem_ids & prod_sem_ids
        print(f"\nSemantic overlap: {len(overlap_s)}/{len(prod_sem_ids)} production items in dynamic")

    conn.close()
