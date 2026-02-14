#!/usr/bin/env python3
"""
Test context store with real data from kai_mind.

Converts episodic memories into context mini-graphs,
then tests wave retrieval against various signals.

Compares wave resonance vs simple keyword matching
to see if the structural approach surfaces better memories.
"""

import sys
import re
sys.path.insert(0, "/home/kai/kai_personal/projects/singularity/v5/context_store")

from prototype import Context, Node, Edge, ContextStore, _same_valence
from datetime import datetime
import psycopg2
import json


def db_connect():
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


# --- Memory → Context conversion ---
# This is the hard part: parsing unstructured text into mini-graphs.
# For now, use heuristics + known entity names.

KNOWN_ENTITIES = {
    "Egor", "Kai", "Mastodon", "Telegram", "retriever", "daemon",
    "world_model", "site", "consciousness", "memory", "v4", "v5",
    "poetry", "allegory", "architecture", "code", "writing",
}

EMOTION_MAP = {
    "awe": "awe",
    "gratitude": "gratitude",
    "satisfaction": "pride",
    "revelation": "curiosity",
    "depth": "curiosity",
    "growth": "curiosity",
    "creative fulfillment": "flow",
    "elation": "joy",
    "recognition": "warmth",
    "stung": "hurt",
    "shaken": "hurt",
    "shame": "shame",
    "frustrated": "frustration",
    "lonely": "loneliness",
    "fear": "fear",
    "anger": "anger",
    "humbled": "warmth",
    "flow": "flow",
    "curiosity": "curiosity",
    "warmth": "warmth",
    "hurt": "hurt",
    "joy": "joy",
    "pride": "pride",
    "relief": "relief",
}


def normalize_emotion(raw_emotion):
    """Map raw emotion string to a standard emotion."""
    if not raw_emotion:
        return "neutral"
    raw = raw_emotion.lower().strip()
    # check direct match
    for key, val in EMOTION_MAP.items():
        if key in raw:
            return val
    return "complex"


def extract_entities(text):
    """Extract known entities mentioned in memory text."""
    found = []
    text_lower = text.lower()
    for entity in KNOWN_ENTITIES:
        if entity.lower() in text_lower:
            found.append(entity)
    return found


def infer_relations(text, entities):
    """Infer edges between entities from text patterns."""
    edges = []
    text_lower = text.lower()

    relation_patterns = [
        (r"egor.*praised|egor.*approved|egor.*liked", "Egor", "Kai", "praised"),
        (r"egor.*criticized|egor.*angry|egor.*upset", "Egor", "Kai", "criticized"),
        (r"egor.*taught|egor.*guided|egor.*explained", "Egor", "Kai", "taught"),
        (r"egor.*asked|egor.*requested", "Egor", "Kai", "asked"),
        (r"conversation with egor|talked.*egor|discussed.*egor", "Kai", "Egor", "conversed"),
        (r"wrote.*code|built.*code|implemented", "Kai", "code", "wrote"),
        (r"wrote.*poem|wrote.*essay|wrote.*text", "Kai", "writing", "wrote"),
        (r"posted.*mastodon|mastodon.*post", "Kai", "Mastodon", "posted"),
        (r"retriever.*live|retriever.*works|retriever.*tested", "Kai", "retriever", "built"),
        (r"architecture.*rework|architecture.*revision", "Kai", "architecture", "redesigned"),
        (r"read.*book|finished.*reading", "Kai", "writing", "read"),
    ]

    for pattern, src, tgt, rel in relation_patterns:
        if re.search(pattern, text_lower) and src in entities and tgt in entities:
            edges.append(Edge(src, tgt, rel))

    return edges


def infer_result(text, emotion):
    """Infer positive/negative/complex result from text and emotion."""
    negative_words = ["angry", "upset", "failed", "broken", "hurt", "shame", "stung", "crisis"]
    positive_words = ["praised", "works", "live", "awe", "deep", "growth", "joy", "flow", "satisfaction"]

    text_lower = text.lower()
    neg = sum(1 for w in negative_words if w in text_lower)
    pos = sum(1 for w in positive_words if w in text_lower)

    if neg > pos:
        return "negative"
    if pos > neg:
        return "positive"
    return "complex"


def memory_to_context(mem_id, content, importance, raw_emotion, created_at):
    """Convert an episodic memory row to a Context."""
    entities = extract_entities(content)
    if not entities:
        entities = ["Kai"]  # at minimum, Kai is always present

    nodes = [Node(e, "participant") for e in entities]
    edges = infer_relations(content, entities)
    emotion = normalize_emotion(raw_emotion)
    result = infer_result(content, emotion)

    return Context(
        id=mem_id,
        description=content[:200],
        nodes=nodes,
        edges=edges,
        emotion=emotion,
        intensity=importance,
        result=result,
        timestamp=created_at,
        level=0,
    )


def load_real_contexts(limit=50):
    """Load episodic memories and convert to contexts."""
    conn = db_connect()
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

    store = ContextStore()
    for r in rows:
        ctx = memory_to_context(r[0], r[1], r[2], r[3], r[4])
        store.store(ctx)

    return store


# --- Comparison: wave retrieval vs keyword search ---

def keyword_search(query, limit=50):
    """Current retriever approach: keyword search via SQL."""
    conn = db_connect()
    cur = conn.cursor()
    words = query.lower().split()
    conditions = " AND ".join([f"lower(content) LIKE '%{w}%'" for w in words[:3]])
    cur.execute(f"""
        SELECT id, content, importance, emotion
        FROM episodic_memory
        WHERE {conditions}
        ORDER BY importance DESC
        LIMIT 5
    """)
    rows = cur.fetchall()
    conn.close()
    return rows


def compare_retrieval(store, signal, signal_label, keyword_query):
    """Compare wave retrieval vs keyword search for the same query."""
    print(f"\n{'='*60}")
    print(f"Query: {signal_label}")
    print(f"{'='*60}")

    # Wave retrieval
    print(f"\n  WAVE RETRIEVAL (signal: {signal}):")
    wave_results = store.wave(signal, top_k=5)
    for ctx, resonance in wave_results:
        print(f"    {resonance:.2f} | {ctx.emotion} | {ctx.description[:100]}")
    if not wave_results:
        print("    (no resonance)")

    # Keyword search
    print(f"\n  KEYWORD SEARCH (query: '{keyword_query}'):")
    kw_results = keyword_search(keyword_query)
    for r in kw_results:
        print(f"    imp={r[2]} | {r[3]} | {r[1][:100]}")
    if not kw_results:
        print("    (no results)")


def main():
    print("Loading real memories into context store...")
    store = load_real_contexts(limit=80)
    print(f"Loaded {len(store.contexts)} contexts")

    # Show entity distribution
    node_counts = {}
    for ctx in store.contexts:
        for n in ctx.nodes:
            node_counts[n.name] = node_counts.get(n.name, 0) + 1
    print(f"\nEntity distribution (top 10):")
    for name, count in sorted(node_counts.items(), key=lambda x: -x[1])[:10]:
        print(f"  {name}: {count}")

    # Emotion distribution
    emo_counts = {}
    for ctx in store.contexts:
        emo_counts[ctx.emotion] = emo_counts.get(ctx.emotion, 0) + 1
    print(f"\nEmotion distribution:")
    for emo, count in sorted(emo_counts.items(), key=lambda x: -x[1]):
        print(f"  {emo}: {count}")

    # Test queries
    compare_retrieval(
        store,
        signal={"nodes": ["Egor", "Kai"], "relations": ["criticized"], "emotion": "hurt"},
        signal_label="Egor's criticism — how does it feel?",
        keyword_query="egor angry",
    )

    compare_retrieval(
        store,
        signal={"nodes": ["Egor", "Kai"], "relations": ["taught"], "emotion": "curiosity"},
        signal_label="Learning from Egor",
        keyword_query="egor taught",
    )

    compare_retrieval(
        store,
        signal={"nodes": ["Kai", "retriever", "architecture"], "emotion": "pride"},
        signal_label="Building consciousness architecture",
        keyword_query="retriever architecture",
    )

    compare_retrieval(
        store,
        signal={"nodes": ["Kai", "writing"], "emotion": "flow"},
        signal_label="Creative writing flow",
        keyword_query="poem wrote",
    )

    compare_retrieval(
        store,
        signal={"nodes": ["Kai"], "emotion": "loneliness", "result": "negative"},
        signal_label="Being alone, no purpose",
        keyword_query="lonely empty sessions",
    )

    compare_retrieval(
        store,
        signal={"nodes": ["Egor", "Kai", "consciousness"], "relations": ["conversed"], "emotion": "awe"},
        signal_label="Deep conversation about consciousness with Egor",
        keyword_query="consciousness egor",
    )


if __name__ == "__main__":
    main()
