#!/usr/bin/env python3
"""
DB-backed context store — persistent mini-graph contexts in kai_world.

Wraps the in-memory ContextStore with PostgreSQL persistence.
Table: v5_contexts in kai_world (port 5434).

Usage:
    from db_store import DBContextStore
    store = DBContextStore()
    store.store(ctx)                    # save to DB
    results = store.wave(signal)        # retrieve from DB + wave
    store.load_all()                    # load all contexts from DB
    store.convert_from_kai_mind(limit)  # convert episodic memories
"""

import sys
import os
import json
import psycopg2
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prototype import Context, Node, Edge, ContextStore


def _world_connect():
    """Connect to kai_world database."""
    env = {}
    for line in open("/home/kai/kai_personal/secrets/db.env").read().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return psycopg2.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "5434")),
        dbname=env.get("DB_NAME", "kai_world"),
        user=env.get("DB_USER", "kai"),
        password=env.get("DB_PASSWORD", ""),
    )


def _mind_connect():
    """Connect to kai_mind database."""
    env = {}
    for line in open("/home/kai/substrate/secrets/db.env").read().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    return psycopg2.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "5433")),
        dbname=env.get("DB_NAME", "kai_mind"),
        user=env.get("DB_USER", "kai"),
        password=env.get("DB_PASSWORD", ""),
    )


class DBContextStore(ContextStore):
    """Context store backed by v5_contexts table in kai_world."""

    def __init__(self, auto_load=True):
        super().__init__()
        if auto_load:
            self.load_all()

    def store(self, ctx: Context, persist=True) -> int:
        """Store context in memory and optionally in DB."""
        # Store in memory first
        mem_id = super().store(ctx)

        if persist:
            conn = _world_connect()
            cur = conn.cursor()
            cur.execute("""
                INSERT INTO v5_contexts
                    (description, nodes, edges, emotion, intensity, result, level, rule,
                     sources, when_day, when_cycle, source_memory_id, created_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                RETURNING id
            """, (
                ctx.description,
                json.dumps([{"name": n.name, "role": n.role, "properties": n.properties} for n in ctx.nodes]),
                json.dumps([{"source": e.source, "target": e.target, "relation": e.relation} for e in ctx.edges]),
                ctx.emotion,
                ctx.intensity,
                ctx.result,
                ctx.level,
                ctx.rule,
                ctx.sources or [],
                ctx.when_day or None,
                ctx.when_cycle or None,
                getattr(ctx, 'source_memory_id', None),
                ctx.timestamp,
            ))
            db_id = cur.fetchone()[0]
            conn.commit()
            conn.close()
            ctx.id = db_id  # use DB id

        return ctx.id

    def load_all(self):
        """Load all contexts from DB into memory."""
        self.contexts.clear()
        self._by_node.clear()
        self._by_relation.clear()
        self._by_emotion.clear()
        self._by_result.clear()

        conn = _world_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, description, nodes, edges, emotion, intensity, result, level,
                   source_memory_id, created_at, rule, sources, when_day, when_cycle
            FROM v5_contexts
            ORDER BY created_at
        """)
        rows = cur.fetchall()
        conn.close()

        for r in rows:
            nodes_data = r[2] if isinstance(r[2], list) else json.loads(r[2])
            edges_data = r[3] if isinstance(r[3], list) else json.loads(r[3])

            ctx = Context(
                id=r[0],
                description=r[1],
                nodes=[Node(n["name"], n.get("role", ""), n.get("properties", {})) for n in nodes_data],
                edges=[Edge(e["source"], e["target"], e["relation"]) for e in edges_data],
                emotion=r[4],
                intensity=r[5],
                result=r[6],
                timestamp=r[9],
                level=r[7],
                rule=r[10] or "",
                sources=list(r[11] or []),
                when_day=r[12] or 0,
                when_cycle=r[13] or 0,
            )
            ctx.source_memory_id = r[8]
            # Add to memory without re-persisting
            self.contexts.append(ctx)
            self._next_id = max(self._next_id, ctx.id + 1)
            # Update inverted indexes
            for node in ctx.nodes:
                self._by_node.setdefault(node.name, set()).add(ctx.id)
            for edge in ctx.edges:
                self._by_relation.setdefault(edge.relation, set()).add(ctx.id)
            self._by_emotion.setdefault(ctx.emotion, set()).add(ctx.id)
            self._by_result.setdefault(ctx.result, set()).add(ctx.id)

        return len(self.contexts)

    def convert_from_kai_mind(self, limit=50):
        """Convert episodic memories from kai_mind into contexts.

        Uses the same heuristics as test_real_data.py but persists results.
        Only converts memories not already in the store (by source_memory_id).
        """
        # Import conversion functions
        from test_real_data import memory_to_context

        # Get existing source_memory_ids
        existing = set()
        conn = _world_connect()
        cur = conn.cursor()
        cur.execute("SELECT source_memory_id FROM v5_contexts WHERE source_memory_id IS NOT NULL")
        existing = {r[0] for r in cur.fetchall()}
        conn.close()

        # Load memories from kai_mind
        conn = _mind_connect()
        cur = conn.cursor()
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE importance >= 0.5 AND emotion IS NOT NULL AND emotion != ''
            ORDER BY importance DESC, created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cur.fetchall()
        conn.close()

        converted = 0
        for r in rows:
            if r[0] in existing:
                continue
            ctx = memory_to_context(r[0], r[1], r[2], r[3], r[4])
            ctx.source_memory_id = r[0]
            self.store(ctx, persist=True)
            converted += 1

        return converted


# --- CLI ---

def main():
    import argparse
    parser = argparse.ArgumentParser(description="DB-backed context store")
    parser.add_argument("command", choices=["load", "convert", "wave", "stats"])
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--nodes", nargs="*", default=[])
    parser.add_argument("--emotion", default="")
    parser.add_argument("--result", default="")
    parser.add_argument("--relations", nargs="*", default=[])
    args = parser.parse_args()

    store = DBContextStore(auto_load=True)

    if args.command == "stats":
        print(f"Contexts in DB: {len(store.contexts)}")
        if store.contexts:
            node_counts = {}
            for ctx in store.contexts:
                for n in ctx.nodes:
                    node_counts[n.name] = node_counts.get(n.name, 0) + 1
            print(f"Entities (top 10):")
            for name, count in sorted(node_counts.items(), key=lambda x: -x[1])[:10]:
                print(f"  {name}: {count}")
            emo_counts = {}
            for ctx in store.contexts:
                emo_counts[ctx.emotion] = emo_counts.get(ctx.emotion, 0) + 1
            print(f"Emotions:")
            for emo, count in sorted(emo_counts.items(), key=lambda x: -x[1]):
                print(f"  {emo}: {count}")

    elif args.command == "convert":
        n = store.convert_from_kai_mind(limit=args.limit)
        print(f"Converted {n} memories → contexts (total: {len(store.contexts)})")

    elif args.command == "wave":
        signal = {}
        if args.nodes:
            signal["nodes"] = args.nodes
        if args.relations:
            signal["relations"] = args.relations
        if args.emotion:
            signal["emotion"] = args.emotion
        if args.result:
            signal["result"] = args.result
        if not signal:
            print("Provide at least one of: --nodes, --emotion, --result, --relations")
            return
        print(f"Signal: {signal}")
        results = store.wave(signal, top_k=5)
        for ctx, resonance in results:
            lvl = f" [L{ctx.level}]" if ctx.level > 0 else ""
            print(f"  {resonance:.2f}{lvl} | {ctx.emotion} | {ctx.description[:100]}")

    elif args.command == "load":
        print(f"Loaded {len(store.contexts)} contexts from DB")


if __name__ == "__main__":
    main()
