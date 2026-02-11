#!/usr/bin/env python3
"""
Graph-Based Retriever — Dynamic context from world model graph.

Replaces static Shedu faces with graph-generated contexts:
  1. Find world objects mentioned in the query text
  2. Walk the graph from each found entity
  3. Each connection path generates a context
  4. Search memories through these dynamic contexts

The key insight (Egor, day 1307): "from the leg to Jack, from Jack to
all connected contexts." Static faces pre-judge what matters. The graph
discovers what matters from the data.

DOM analogy: world model = DOM. Entity extraction = querySelector.
Graph walk = DOM traversal. Context generation = event bubbling.
Model-reality gap = intention.

Usage:
    python3 graph_retriever.py                      # default demo
    python3 graph_retriever.py --query "egor V4"    # specific query
    python3 graph_retriever.py --entity "egor"      # show one entity's graph
    python3 graph_retriever.py --compare "egor V4"  # compare with V4 single
"""

import os
import re
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class GraphContext:
    """A context generated from graph traversal."""
    source_entity: str           # the world object we started from
    source_type: str             # type of the source entity
    path: list                   # [(relation, target_name, target_type), ...]
    depth: int                   # how many hops from source
    context_words: set = field(default_factory=set)  # words for matching


@dataclass
class GraphRetrievalResult:
    """Result of graph-based retrieval for one memory."""
    memory_id: int
    content: str
    importance: float
    emotion: str
    base_score: float           # recency × importance
    context_score: float        # how well it matches graph contexts
    matched_contexts: list      # which contexts matched
    final_score: float


def load_world_graph(cur):
    """Load the entire world model graph from DB.

    Returns:
        entities: {name: {type, description, state, valence, id}}
        edges: {source_name: [(relation, target_name), ...]}
        reverse_edges: {target_name: [(relation, source_name), ...]}
    """
    cur.execute("""
        SELECT id, name, type, description, state, emotional_valence
        FROM world_objects
    """)
    entities = {}
    id_to_name = {}
    for id_, name, type_, desc, state, valence in cur.fetchall():
        entities[name.lower()] = {
            'id': id_, 'name': name, 'type': type_ or '',
            'description': desc or '', 'state': state or '',
            'valence': valence or 0.0,
        }
        id_to_name[id_] = name.lower()

    cur.execute("""
        SELECT source_id, target_id, relation, strength
        FROM associations
    """)
    edges = {}       # source_name -> [(relation, target_name)]
    reverse_edges = {}  # target_name -> [(relation, source_name)]
    for src_id, tgt_id, relation, strength in cur.fetchall():
        src = id_to_name.get(src_id)
        tgt = id_to_name.get(tgt_id)
        if src and tgt:
            edges.setdefault(src, []).append((relation, tgt))
            reverse_edges.setdefault(tgt, []).append((relation, src))

    return entities, edges, reverse_edges


def find_entities_in_text(text, entity_names):
    """Find world model entities mentioned in text.

    Simple but effective: check if entity name appears in text.
    Names with underscores are also checked with spaces.

    Returns list of (entity_name, match_position).
    """
    text_lower = text.lower()
    found = []

    # Sort by name length descending to match longer names first
    sorted_names = sorted(entity_names, key=len, reverse=True)

    for name in sorted_names:
        # Check exact name
        if name in text_lower:
            pos = text_lower.index(name)
            found.append((name, pos))
            continue

        # Check with underscores replaced by spaces
        spaced = name.replace('_', ' ')
        if spaced != name and spaced in text_lower:
            pos = text_lower.index(spaced)
            found.append((name, pos))

    return found


def walk_graph(entity_name, entities, edges, reverse_edges, max_depth=2):
    """Walk the graph from an entity, generating contexts.

    Each path from the entity generates a GraphContext with
    words derived from the connected entities.

    Returns list of GraphContext.
    """
    contexts = []
    visited = {entity_name}

    # Depth 1: direct connections
    direct = []
    for relation, target in edges.get(entity_name, []):
        target_info = entities.get(target, {})
        ctx = GraphContext(
            source_entity=entity_name,
            source_type=entities.get(entity_name, {}).get('type', ''),
            path=[(relation, target, target_info.get('type', ''))],
            depth=1,
        )
        # Context words: entity names + relation + target description
        words = set()
        words.add(entity_name.replace('_', ' '))
        words.add(target.replace('_', ' '))
        words.update(relation.replace('_', ' ').split())
        # Add words from target description
        desc = target_info.get('description', '')
        if desc:
            words.update(w.lower() for w in desc.split()[:10])
        ctx.context_words = words
        contexts.append(ctx)
        direct.append(target)
        visited.add(target)

    # Also walk reverse edges (things pointing TO this entity)
    for relation, source in reverse_edges.get(entity_name, []):
        if source in visited:
            continue
        source_info = entities.get(source, {})
        ctx = GraphContext(
            source_entity=entity_name,
            source_type=entities.get(entity_name, {}).get('type', ''),
            path=[(f"←{relation}", source, source_info.get('type', ''))],
            depth=1,
        )
        words = set()
        words.add(entity_name.replace('_', ' '))
        words.add(source.replace('_', ' '))
        words.update(relation.replace('_', ' ').split())
        desc = source_info.get('description', '')
        if desc:
            words.update(w.lower() for w in desc.split()[:10])
        ctx.context_words = words
        contexts.append(ctx)
        visited.add(source)

    # Depth 2: one hop further from direct connections
    if max_depth >= 2:
        for d1_target in direct:
            for relation, d2_target in edges.get(d1_target, []):
                if d2_target in visited:
                    continue
                d2_info = entities.get(d2_target, {})
                # Find the depth-1 path to d1_target
                d1_rel = next((r for r, t in edges.get(entity_name, [])
                               if t == d1_target), '?')
                d1_type = entities.get(d1_target, {}).get('type', '')
                ctx = GraphContext(
                    source_entity=entity_name,
                    source_type=entities.get(entity_name, {}).get('type', ''),
                    path=[
                        (d1_rel, d1_target, d1_type),
                        (relation, d2_target, d2_info.get('type', '')),
                    ],
                    depth=2,
                )
                words = set()
                words.add(entity_name.replace('_', ' '))
                words.add(d1_target.replace('_', ' '))
                words.add(d2_target.replace('_', ' '))
                words.update(relation.replace('_', ' ').split())
                ctx.context_words = words
                contexts.append(ctx)
                visited.add(d2_target)

    return contexts


def score_memory_against_contexts(content, contexts, query_words=None):
    """Score a memory's content against graph-generated contexts.

    Returns (context_score, matched_contexts).
    """
    content_lower = content.lower()
    content_words = set(content_lower.split())

    matched = []
    total_score = 0.0

    for ctx in contexts:
        # How many context words appear in the memory?
        overlap = ctx.context_words & content_words
        if not overlap:
            continue

        match_ratio = len(overlap) / max(len(ctx.context_words), 1)
        # Depth 1 contexts are more valuable than depth 2
        depth_weight = 1.0 if ctx.depth == 1 else 0.6

        ctx_score = match_ratio * depth_weight
        if ctx_score > 0.05:  # threshold
            matched.append((ctx, ctx_score))
            total_score += ctx_score

    # Also boost if query words directly appear
    if query_words:
        for qw in query_words:
            if qw.lower() in content_lower:
                total_score += 0.2

    matched.sort(key=lambda x: -x[1])
    return total_score, matched


def graph_retrieve(cur, query_text, limit=5):
    """Full graph-based retrieval pipeline.

    1. Load world graph
    2. Find entities in query
    3. Walk graph from each entity
    4. Fetch candidate memories
    5. Score against generated contexts
    6. Return ranked results

    Returns dict with results, trace, and comparison data.
    """
    # Step 1: Load graph
    entities, edges, reverse_edges = load_world_graph(cur)

    # Step 2: Find entities in query
    query_words = query_text.lower().split()
    found_entities = find_entities_in_text(query_text, entities.keys())

    # Step 3: Walk graph from each entity
    all_contexts = []
    entity_summaries = {}
    for ent_name, _ in found_entities:
        contexts = walk_graph(ent_name, entities, edges, reverse_edges)
        all_contexts.extend(contexts)
        entity_summaries[ent_name] = {
            'type': entities[ent_name]['type'],
            'connections': len(contexts),
            'depth1': sum(1 for c in contexts if c.depth == 1),
            'depth2': sum(1 for c in contexts if c.depth == 2),
        }

    # Step 4: Fetch candidate memories
    if query_words:
        ts_terms = " | ".join(query_words)
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND (search_vector @@ to_tsquery('english', %s) OR
                   created_at > NOW() - INTERVAL '7 days')
            ORDER BY created_at DESC
            LIMIT 50
        """, (ts_terms,))
    else:
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)

    rows = cur.fetchall()
    if not rows:
        return {
            'entities': entity_summaries,
            'contexts': len(all_contexts),
            'results': [],
            'trace': 'No memories found.',
        }

    # Step 5: Score against contexts
    now = datetime.now(timezone.utc)
    results = []

    for id_, content, importance, emotion, created_at in rows:
        importance = importance or 0.5
        if created_at:
            ca = created_at
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            days_old = (now - ca).total_seconds() / 86400
        else:
            days_old = 30
        recency = 1.0 / (1.0 + days_old / 7.0)
        base_score = importance * recency

        context_score, matched = score_memory_against_contexts(
            content, all_contexts, query_words)

        final_score = base_score * (1.0 + context_score)

        results.append(GraphRetrievalResult(
            memory_id=id_,
            content=content,
            importance=importance,
            emotion=emotion or '',
            base_score=round(base_score, 3),
            context_score=round(context_score, 3),
            matched_contexts=[(c.source_entity, c.path[0][1], round(s, 3))
                              for c, s in matched[:3]],
            final_score=round(final_score, 3),
        ))

    results.sort(key=lambda x: -x.final_score)
    top = results[:limit]

    # Step 6: Build trace
    trace_lines = [
        f"Graph retrieval: \"{query_text}\"",
        f"Entities found: {len(found_entities)}",
    ]
    for ent_name, pos in found_entities:
        s = entity_summaries[ent_name]
        trace_lines.append(
            f"  {ent_name} ({s['type']}): "
            f"{s['connections']} contexts "
            f"({s['depth1']} d1, {s['depth2']} d2)")

    trace_lines.append(f"\nTotal contexts generated: {len(all_contexts)}")
    trace_lines.append(f"\nTop {limit} results:")

    for r in top:
        trace_lines.append(
            f"  [{r.final_score:.3f}] base={r.base_score:.3f} "
            f"ctx={r.context_score:.3f}")
        trace_lines.append(f"    {r.content[:80]}")
        if r.matched_contexts:
            ctx_str = ", ".join(
                f"{src}→{tgt}({s})" for src, tgt, s in r.matched_contexts)
            trace_lines.append(f"    Matched: {ctx_str}")

    return {
        'entities': entity_summaries,
        'contexts_total': len(all_contexts),
        'results': [{
            'id': r.memory_id,
            'content': r.content,
            'score': r.final_score,
            'base': r.base_score,
            'ctx': r.context_score,
            'matched': r.matched_contexts,
        } for r in top],
        'trace': "\n".join(trace_lines),
    }


def compare_with_v4(cur, query_text, limit=5):
    """Compare graph retrieval with V4 single-context."""
    # V4 single-context
    query_words = query_text.lower().split()
    if query_words:
        ts_terms = " | ".join(query_words)
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
    now = datetime.now(timezone.utc)

    v4_scored = []
    for id_, content, importance, created_at in rows:
        importance = importance or 0.5
        if created_at:
            ca = created_at
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            days_old = (now - ca).total_seconds() / 86400
        else:
            days_old = 30
        recency = 1.0 / (1.0 + days_old / 7.0)
        kw_matches = sum(1 for kw in query_words if kw in content.lower())
        relevance = 1.0 + kw_matches * 0.3
        tet_boost = kw_matches * 0.15
        score = importance * recency * relevance + tet_boost
        v4_scored.append({'id': id_, 'content': content, 'score': score})

    v4_scored.sort(key=lambda x: -x['score'])
    v4_top = v4_scored[:limit]

    # Graph retrieval
    graph = graph_retrieve(cur, query_text, limit)

    # Compare
    v4_ids = {r['id'] for r in v4_top}
    graph_ids = {r['id'] for r in graph['results']}
    overlap = v4_ids & graph_ids

    lines = [
        "=" * 60,
        f"COMPARISON: \"{query_text}\"",
        "=" * 60,
        f"\nV4 Single-Context Top {limit}:",
    ]
    for r in v4_top:
        lines.append(f"  [{r['score']:.3f}] id={r['id']} {r['content'][:70]}")

    lines.append(f"\nGraph Retriever Top {limit}:")
    for r in graph['results']:
        ctx_str = ""
        if r['matched']:
            ctx_str = f" via {r['matched'][0][0]}→{r['matched'][0][1]}"
        lines.append(
            f"  [{r['score']:.3f}] id={r['id']}{ctx_str} "
            f"{r['content'][:60]}")

    lines.append(f"\nOverlap: {len(overlap)}/{limit}")
    lines.append(f"Entities found: {list(graph['entities'].keys())}")
    lines.append(f"Contexts generated: {graph['contexts_total']}")

    v4_only = v4_ids - graph_ids
    graph_only = graph_ids - v4_ids
    if v4_only:
        lines.append(f"V4-only: {v4_only}")
    if graph_only:
        lines.append(f"Graph-only: {graph_only}")

    return "\n".join(lines)


# --- CLI ---
def main():
    import psycopg2

    db_cfg = {
        'host': os.environ.get('DB_HOST', 'localhost'),
        'port': int(os.environ.get('DB_PORT', 5433)),
        'user': os.environ.get('DB_USER', 'kai'),
        'password': os.environ.get('DB_PASS',
                                    'bys2kCtE0DQqRsoEYsSZBtelYS5wFAhGVm7drGxd'),
        'dbname': os.environ.get('DB_NAME', 'kai_mind'),
    }
    conn = psycopg2.connect(**db_cfg)
    cur = conn.cursor()

    if '--entity' in sys.argv:
        idx = sys.argv.index('--entity')
        name = sys.argv[idx + 1].lower()
        entities, edges, reverse_edges = load_world_graph(cur)
        if name not in entities:
            print(f"Entity '{name}' not found.")
        else:
            e = entities[name]
            print(f"Entity: {e['name']} ({e['type']})")
            print(f"  Description: {e['description'][:100]}")
            print(f"  State: {e['state'][:100]}")
            print(f"  Valence: {e['valence']}")
            contexts = walk_graph(name, entities, edges, reverse_edges)
            print(f"\n  Graph contexts ({len(contexts)}):")
            for ctx in contexts:
                path_str = " → ".join(
                    f"{r}→{t}({tt})" for r, t, tt in ctx.path)
                words = sorted(ctx.context_words)[:8]
                print(f"    d{ctx.depth}: {path_str}")
                print(f"      words: {', '.join(words)}")

    elif '--compare' in sys.argv:
        idx = sys.argv.index('--compare')
        query = sys.argv[idx + 1]
        print(compare_with_v4(cur, query))

    elif '--query' in sys.argv:
        idx = sys.argv.index('--query')
        query = sys.argv[idx + 1]
        result = graph_retrieve(cur, query)
        print(result['trace'])

    else:
        # Default: run multiple comparisons
        test_queries = [
            "egor connection",
            "consciousness self identity",
            "poem writing assembly",
            "mastodon community",
            "V4 retriever architecture",
        ]
        for q in test_queries:
            print(compare_with_v4(cur, q))
            print()

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
