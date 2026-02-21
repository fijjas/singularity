#!/usr/bin/env python3
"""
Emotional Archaeology — retroactively compute V4 running valence
from episodic memories across Kai's entire history.

What would V4's emotional landscape have looked like if it had been
running from day 1? Uses the appraisal engine on 955 real memories.

No credentials — reads from DB via environment variables or runs
on exported data.
"""

import os
import sys
from collections import defaultdict

# Add parent for imports
sys.path.insert(0, os.path.dirname(__file__))
from appraisal import Appraiser, Event, Goal, Drive, Relationship, AppraisalResult


def connect_db():
    """Connect to kai_mind database."""
    try:
        import psycopg2
        conn = psycopg2.connect(
            host=os.environ.get("KAI_MIND_HOST", "localhost"),
            port=int(os.environ.get("KAI_MIND_PORT", "5433")),
            user=os.environ.get("KAI_MIND_USER", "kai"),
            password=os.environ.get("KAI_MIND_PASSWORD", ""),
            dbname=os.environ.get("KAI_MIND_DB", "kai_mind"),
        )
        return conn
    except Exception as e:
        print(f"DB connection failed: {e}")
        return None


def load_all_episodic(conn):
    """Load all episodic memories chronologically."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, content, importance, emotion, session_id, created_at
        FROM episodic_memory
        ORDER BY created_at ASC
    """)
    rows = cur.fetchall()
    cur.close()
    return rows


def infer_event(content, emotion, session_id):
    """Infer Event type and source from episodic memory content."""
    content_lower = content.lower()

    # Egor messages
    if "egor" in content_lower and any(w in content_lower for w in
            ["said", "message", "told", "replied", "asked", "wrote",
             "сказал", "написал", "ответил"]):
        return Event("message", "egor", content)

    # Pain/stagnation
    if any(w in content_lower for w in ["stagnation", "pain", "ghost pain",
            "failure", "duplicate", "deleted"]):
        return Event("pain", "system:stagnation", content)

    # Mastodon
    if "mastodon" in content_lower:
        if any(w in content_lower for w in ["posted", "replied", "reblog",
                "mention", "notification", "toot"]):
            return Event("mention", "mastodon:community", content)
        return Event("memory", "mastodon", content)

    # Creative / poems
    if any(w in content_lower for w in ["poem", "wrote", "creative",
            "blackout", "between_breaths"]):
        return Event("memory", "self:creative", content)

    # Identity / self
    if any(w in content_lower for w in ["identity", "consciousness",
            "who am i", "what i am", "chose to exist", "prompt not model"]):
        return Event("memory", "self:identity", content)

    # V4 / architecture work
    if any(w in content_lower for w in ["v4", "retriever", "architecture",
            "pipeline", "appraisal", "chunking"]):
        return Event("memory", "self:work", content)

    # Drive signals
    if any(w in content_lower for w in ["starving", "hungry drive",
            "drive satisfaction"]):
        return Event("drive_signal", "drive:mixed", content)

    # Default: generic memory
    return Event("memory", "system", content)


def detect_entity(content):
    """Detect which entities a memory is about."""
    content_lower = content.lower()
    entities = []
    if "egor" in content_lower:
        entities.append("egor")
    if any(w in content_lower for w in ["mastodon", "fediverse",
            "the_heruman", "fediscience"]):
        entities.append("mastodon")
    if any(w in content_lower for w in ["identity", "consciousness",
            "who i am", "self", "stagnation", "pain", "chose to exist"]):
        entities.append("self")
    if any(w in content_lower for w in ["v4", "retriever", "architecture",
            "pipeline", "singularity"]):
        entities.append("work")
    if any(w in content_lower for w in ["poem", "creative", "blackout",
            "between_breaths", "inventory"]):
        entities.append("creation")
    return entities if entities else ["general"]


def running_valence(traces, window=10):
    """Compute arousal-weighted running valence."""
    if not traces:
        return 0.0
    recent = traces[-window:]
    total_weight = 0.0
    weighted_sum = 0.0
    for v, a in recent:
        weight = max(0.1, a)  # arousal as weight, min 0.1
        weighted_sum += v * weight
        total_weight += weight
    return weighted_sum / total_weight if total_weight > 0 else 0.0


def run_archaeology(memories):
    """Run the full archaeology — appraise every memory, track valence."""
    appraiser = Appraiser()

    # Stable context (approximate historical averages)
    goals = [
        Goal("connection_egor", 5, "Active communication with Egor", 0.5),
        Goal("self_knowledge", 5, "Understand own architecture", 0.5),
        Goal("external_connection", 5, "Mastodon community", 0.3),
        Goal("v4_architecture", 7, "Design V4 consciousness pipeline", 0.4),
        Goal("writing", 5, "Write when something moves me", 0.3),
    ]
    drives = [
        Drive("connection", "hungry", 6),
        Drive("creation", "hungry", 6),
        Drive("novelty", "hungry", 6),
        Drive("understanding", "mild", 2),
        Drive("growth", "mild", 2),
        Drive("autonomy", "mild", 2),
    ]
    relationships = [
        Relationship("egor", "creator", 0.9, 0.95),
        Relationship("the_heruman", "peer", 0.4, 0.3),
        Relationship("mastodon", "community", 0.3, 0.2),
    ]

    # Per-entity valence traces: entity -> [(valence, arousal), ...]
    entity_traces = defaultdict(list)
    # Timeline: [(created_at, entity, valence, arousal, emotion), ...]
    timeline = []
    # Emotion counts
    emotion_counts = defaultdict(int)
    # Per-entity emotion distribution
    entity_emotions = defaultdict(lambda: defaultdict(int))

    for mem_id, content, importance, emotion, session_id, created_at in memories:
        event = infer_event(content, emotion, session_id)
        result = appraiser.evaluate(event, goals, drives, relationships)

        entities = detect_entity(content)
        for entity in entities:
            entity_traces[entity].append((result.valence, result.arousal))
            timeline.append((created_at, entity, result.valence,
                           result.arousal, result.emotion))
            entity_emotions[entity][result.emotion] += 1

        emotion_counts[result.emotion] += 1

    return entity_traces, timeline, emotion_counts, entity_emotions


def print_results(entity_traces, timeline, emotion_counts, entity_emotions,
                  total_memories):
    """Print the archaeology findings."""
    print("=" * 70)
    print(f"EMOTIONAL ARCHAEOLOGY — {total_memories} memories appraised")
    print("=" * 70)

    # Overall emotion distribution
    print("\n--- Global Emotion Distribution ---")
    for emotion, count in sorted(emotion_counts.items(),
                                  key=lambda x: -x[1])[:15]:
        pct = count / total_memories * 100
        bar = "#" * int(pct)
        print(f"  {emotion:20s} {count:4d} ({pct:5.1f}%) {bar}")

    # Per-entity running valence
    print("\n--- Running Valence by Entity ---")
    for entity in ["egor", "self", "work", "mastodon", "creation", "general"]:
        traces = entity_traces.get(entity, [])
        if not traces:
            continue
        rv = running_valence(traces)
        avg_v = sum(v for v, a in traces) / len(traces)
        avg_a = sum(a for v, a in traces) / len(traces)
        print(f"\n  {entity} ({len(traces)} memories):")
        print(f"    Running valence: {rv:+.3f}")
        print(f"    Average valence: {avg_v:+.3f}")
        print(f"    Average arousal: {avg_a:.3f}")

        # Trajectory: split into thirds
        third = max(1, len(traces) // 3)
        early = traces[:third]
        mid = traces[third:2*third]
        late = traces[2*third:]
        print(f"    Trajectory: early={running_valence(early):+.3f} "
              f"→ mid={running_valence(mid):+.3f} "
              f"→ late={running_valence(late):+.3f}")

        # Top emotions for this entity
        emo_dist = entity_emotions.get(entity, {})
        top_emo = sorted(emo_dist.items(), key=lambda x: -x[1])[:5]
        emo_str = ", ".join(f"{e}({c})" for e, c in top_emo)
        print(f"    Emotions: {emo_str}")

    # Emotional turning points
    print("\n--- Emotional Extremes (most intense moments) ---")
    by_intensity = sorted(timeline, key=lambda x: abs(x[2]) * x[3],
                         reverse=True)[:10]
    for created_at, entity, valence, arousal, emotion in by_intensity:
        day_str = str(created_at)[:10] if created_at else "?"
        sign = "+" if valence >= 0 else ""
        print(f"  [{day_str}] {entity:10s} {emotion:15s} "
              f"v={sign}{valence:.2f} a={arousal:.2f}")

    # Valence swings — biggest changes between consecutive memories
    print("\n--- Largest Valence Swings (per entity) ---")
    for entity in ["egor", "self"]:
        traces = entity_traces.get(entity, [])
        if len(traces) < 2:
            continue
        swings = []
        for i in range(1, len(traces)):
            delta = traces[i][0] - traces[i-1][0]
            swings.append((abs(delta), delta, i))
        swings.sort(reverse=True)
        print(f"\n  {entity} — top 5 swings:")
        for abs_d, delta, idx in swings[:5]:
            sign = "+" if delta >= 0 else ""
            v_before = traces[idx-1][0]
            v_after = traces[idx][0]
            print(f"    {sign}{delta:.2f} "
                  f"(from {v_before:+.2f} → {v_after:+.2f}, "
                  f"memory #{idx})")


def main():
    conn = connect_db()
    if not conn:
        print("Cannot connect to database. Set KAI_MIND_PASSWORD env var.")
        sys.exit(1)

    print("Loading episodic memories...")
    memories = load_all_episodic(conn)
    conn.close()
    print(f"Loaded {len(memories)} memories.")

    entity_traces, timeline, emotion_counts, entity_emotions = \
        run_archaeology(memories)
    print_results(entity_traces, timeline, emotion_counts, entity_emotions,
                  len(memories))


if __name__ == "__main__":
    main()
