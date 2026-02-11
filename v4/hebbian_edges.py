#!/usr/bin/env python3
"""
Hebbian Edge Suggestion — find missing lateral connections in the world model.

Scans episodic memories for entity co-occurrences. Entity pairs that
frequently appear together but have no edge are candidates for new
connections. This is "fire together → wire together" applied to the graph.

The goal: break the 43% hub concentration (kai has 80/187 edges) by
discovering lateral connections between concepts.

Usage:
    python3 hebbian_edges.py                    # full analysis
    python3 hebbian_edges.py --top 20           # top 20 suggestions
    python3 hebbian_edges.py --entity "egor"    # co-occurrences for one entity
"""

import os
import re
import sys
from collections import Counter, defaultdict

# Reuse fuzzy matching from graph_retriever
from graph_retriever import load_world_graph, find_entities_in_text


def scan_memories(cur, entities):
    """Scan all episodic memories for entity mentions.

    Returns:
        cooccurrences: Counter of (entity_a, entity_b) frozensets
        entity_freq: Counter of entity mention counts
        memory_count: total memories scanned
    """
    cur.execute("""
        SELECT id, content FROM episodic_memory
        WHERE archived_at IS NULL
        ORDER BY created_at
    """)

    entity_names = list(entities.keys())
    cooccurrences = Counter()
    entity_freq = Counter()
    memory_count = 0

    for id_, content in cur.fetchall():
        memory_count += 1
        # Find entities in this memory — exact match only for co-occurrence
        # (fuzzy matching at 0.6 is too noisy: "day 400" matches "day_400"
        # in every memory that mentions any day number)
        found = find_entities_in_text(content, entity_names)
        # Filter to confidence >= 0.9 (exact + all-parts stem only)
        found_names = [name for name, conf in found if conf >= 0.9]

        for name in found_names:
            entity_freq[name] += 1

        # Count co-occurrences (all pairs in this memory)
        for i, a in enumerate(found_names):
            for b in found_names[i + 1:]:
                if a != b:
                    pair = frozenset([a, b])
                    cooccurrences[pair] += 1

    return cooccurrences, entity_freq, memory_count


def find_missing_edges(cooccurrences, entity_freq, edges, reverse_edges,
                       min_cooccur=3):
    """Find entity pairs with high co-occurrence but no existing edge.

    Filters out:
      - Pairs involving 'kai' (hub — everything connects to kai)
      - Pairs involving 'site' (another hub)
      - Pairs with fewer than min_cooccur co-occurrences

    Returns list of (pair, count, strength) sorted by strength descending.
    strength = co-occurrence / (freq_a + freq_b) — Jaccard-like normalization.
    """
    # Build set of existing edges (undirected)
    existing = set()
    for src, targets in edges.items():
        for _, tgt in targets:
            existing.add(frozenset([src, tgt]))
    for tgt, sources in reverse_edges.items():
        for _, src in sources:
            existing.add(frozenset([src, tgt]))

    hub_entities = {'kai', 'site'}
    # Also skip site sections — they co-occur trivially in site work memories
    structural_prefixes = ('site:', 'days_html', 'state_html', 'listen_html')
    suggestions = []

    for pair, count in cooccurrences.items():
        if count < min_cooccur:
            continue
        a, b = sorted(pair)
        # Skip hub pairs
        if a in hub_entities or b in hub_entities:
            continue
        # Skip structural co-occurrences (site sections)
        if (a.startswith(structural_prefixes) and
                b.startswith(structural_prefixes)):
            continue
        # Skip if edge already exists
        if pair in existing:
            continue
        # Strength: normalized by total frequency
        total_freq = entity_freq.get(a, 1) + entity_freq.get(b, 1)
        strength = count / total_freq
        suggestions.append((a, b, count, round(strength, 3)))

    suggestions.sort(key=lambda x: (-x[2], -x[3]))
    return suggestions


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

    entities, edges, reverse_edges = load_world_graph(cur)

    print(f"World model: {len(entities)} entities, "
          f"{sum(len(v) for v in edges.values())} edges")
    print("Scanning memories for entity co-occurrences...")

    cooccurrences, entity_freq, mem_count = scan_memories(cur, entities)

    print(f"Scanned {mem_count} memories")
    print(f"Entities mentioned: {len(entity_freq)}")
    print(f"Co-occurrence pairs: {len(cooccurrences)}")

    if '--entity' in sys.argv:
        idx = sys.argv.index('--entity')
        target = sys.argv[idx + 1].lower()
        print(f"\nCo-occurrences for '{target}':")
        pairs = [(pair, cnt) for pair, cnt in cooccurrences.items()
                 if target in pair]
        pairs.sort(key=lambda x: -x[1])
        for pair, cnt in pairs[:20]:
            other = (pair - {target}).pop()
            has_edge = frozenset([target, other]) in {
                frozenset([s, t])
                for s, targets in edges.items() for _, t in targets
            } | {
                frozenset([s, t])
                for t, sources in reverse_edges.items() for _, s in sources
            }
            marker = "✓" if has_edge else "×"
            print(f"  {marker} {other}: {cnt} co-occurrences")
    else:
        top_n = 20
        if '--top' in sys.argv:
            idx = sys.argv.index('--top')
            top_n = int(sys.argv[idx + 1])

        suggestions = find_missing_edges(cooccurrences, entity_freq,
                                         edges, reverse_edges, min_cooccur=3)

        print(f"\n{'=' * 60}")
        print(f"MISSING EDGES — Top {top_n} suggestions")
        print(f"(pairs with ≥3 co-occurrences but no edge, excluding kai/site)")
        print(f"{'=' * 60}")

        if not suggestions:
            print("No suggestions found (all high-co-occurrence pairs "
                  "already have edges).")
        else:
            for i, (a, b, count, strength) in enumerate(suggestions[:top_n]):
                a_type = entities.get(a, {}).get('type', '?')
                b_type = entities.get(b, {}).get('type', '?')
                print(f"  {i + 1}. {a} ({a_type}) ↔ {b} ({b_type})")
                print(f"     co-occurs: {count} times, "
                      f"strength: {strength}")

        # Also show top entity frequencies (excluding kai/site)
        print(f"\n{'=' * 60}")
        print("TOP ENTITY FREQUENCIES (excluding kai/site)")
        print(f"{'=' * 60}")
        for name, freq in entity_freq.most_common(15):
            if name not in ('kai', 'site'):
                etype = entities.get(name, {}).get('type', '?')
                print(f"  {name} ({etype}): {freq} mentions")

        # Show existing hub concentration
        kai_edges = len(edges.get('kai', [])) + len(
            reverse_edges.get('kai', []))
        total_edges = sum(len(v) for v in edges.values())
        print(f"\nHub concentration: kai has {kai_edges}/{total_edges} "
              f"edges ({kai_edges / max(total_edges, 1) * 100:.0f}%)")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
