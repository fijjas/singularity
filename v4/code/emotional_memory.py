#!/usr/bin/env python3
"""
V4 Emotional Memory — Emotions That Persist Across Sessions

The gap Egor identified: appraisal evaluates events, but the results
evaporate at session end. There's no "I felt pain when I did this,
so I won't do it again." Emotions are computed but not remembered.

This module adds emotional persistence:

1. STORE: after appraisal, save the emotional trace to the database
   (not just in-memory like integration.py does now)

2. RETRIEVE: at startup, pull recent emotional events relevant to
   the current context — "how did I feel about this recently?"

3. INFLUENCE: emotional memories bias retrieval and appear in the
   consciousness prompt as emotional context

In biological brains, the amygdala stores emotional associations
alongside hippocampal episodic memories. Emotional recall is faster
than factual recall — you feel before you remember why.

Schema (would be added to kai_mind):
    CREATE TABLE emotional_traces (
        id SERIAL PRIMARY KEY,
        object_name TEXT,          -- world object this relates to
        event_type TEXT,           -- message, pain, drive_signal, etc.
        event_source TEXT,         -- egor, mastodon, system, etc.
        event_summary TEXT,        -- short description of what happened
        emotion TEXT,              -- primary emotion name
        valence FLOAT,            -- -1.0 to 1.0
        arousal FLOAT,            -- 0.0 to 1.0
        relevance FLOAT,          -- 0.0 to 1.0
        tags TEXT[],              -- categorical tags
        session_day INT,           -- virtual day
        created_at TIMESTAMPTZ DEFAULT NOW()
    );

Usage:
    store = EmotionalMemoryStore(cursor)
    store.save_trace(appraisal_result, event, session_day=1283)
    recent = store.retrieve_recent(object_name="egor", limit=5)
    context = store.build_emotional_context(keywords, budget=400)
"""

from dataclasses import dataclass
from datetime import datetime, timezone


@dataclass
class StoredEmotion:
    """An emotional memory retrieved from storage."""
    id: int
    object_name: str
    event_type: str
    event_source: str
    event_summary: str
    emotion: str
    valence: float
    arousal: float
    relevance: float
    tags: list
    session_day: int
    created_at: datetime


class EmotionalMemoryStore:
    """Persists emotional traces across sessions.

    This is the bridge between the ephemeral appraisal (integration.py)
    and the persistent world model. After each session, emotional traces
    are stored. At next startup, they're retrieved and influence:

    - World object emotional_valence (running average)
    - Retrieval scoring (emotionally charged objects rank higher)
    - Consciousness prompt (emotional context section)
    """

    CREATE_TABLE_SQL = """
    CREATE TABLE IF NOT EXISTS emotional_traces (
        id SERIAL PRIMARY KEY,
        object_name TEXT,
        event_type TEXT,
        event_source TEXT,
        event_summary TEXT,
        emotion TEXT NOT NULL,
        valence FLOAT DEFAULT 0.0,
        arousal FLOAT DEFAULT 0.0,
        relevance FLOAT DEFAULT 0.0,
        tags TEXT[] DEFAULT '{}',
        session_day INT,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    CREATE INDEX IF NOT EXISTS idx_emotional_traces_object
        ON emotional_traces(object_name, created_at DESC);
    CREATE INDEX IF NOT EXISTS idx_emotional_traces_recent
        ON emotional_traces(created_at DESC);
    """

    def __init__(self, cur=None):
        """Initialize with optional database cursor.

        Without a cursor, operates in mock mode (for testing).
        """
        self.cur = cur
        self._mock_traces = []  # for testing without DB

    def ensure_table(self):
        """Create the emotional_traces table if it doesn't exist."""
        if self.cur:
            self.cur.execute(self.CREATE_TABLE_SQL)

    def save_trace(self, appraisal_result, event, object_names=None,
                   session_day=None):
        """Save an appraisal result as a persistent emotional trace.

        Args:
            appraisal_result: AppraisalResult from appraisal.py
            event: Event that was appraised
            object_names: list of world object names this relates to
            session_day: current virtual day number
        """
        object_names = object_names or [event.source.split(":")[0].lower()]

        for obj_name in object_names:
            trace = {
                'object_name': obj_name,
                'event_type': event.type,
                'event_source': event.source,
                'event_summary': event.content[:200],
                'emotion': appraisal_result.emotion,
                'valence': appraisal_result.valence,
                'arousal': appraisal_result.arousal,
                'relevance': appraisal_result.relevance,
                'tags': appraisal_result.tags,
                'session_day': session_day,
            }

            if self.cur:
                self.cur.execute("""
                    INSERT INTO emotional_traces
                        (object_name, event_type, event_source, event_summary,
                         emotion, valence, arousal, relevance, tags, session_day)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    trace['object_name'], trace['event_type'],
                    trace['event_source'], trace['event_summary'],
                    trace['emotion'], trace['valence'],
                    trace['arousal'], trace['relevance'],
                    trace['tags'], trace['session_day'],
                ))
                trace['id'] = self.cur.fetchone()[0]
            else:
                trace['id'] = len(self._mock_traces) + 1
                trace['created_at'] = datetime.now(timezone.utc)
                self._mock_traces.append(trace)

    def retrieve_for_object(self, object_name, limit=5):
        """Get recent emotional traces for a specific world object.

        Returns the emotional history: what did I feel about this object
        recently? This feeds into valence updates and retrieval scoring.
        """
        if self.cur:
            self.cur.execute("""
                SELECT id, object_name, event_type, event_source,
                       event_summary, emotion, valence, arousal,
                       relevance, tags, session_day, created_at
                FROM emotional_traces
                WHERE object_name = %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (object_name, limit))
            return [self._row_to_stored(row) for row in self.cur.fetchall()]
        else:
            matches = [t for t in self._mock_traces
                       if t['object_name'] == object_name]
            return [self._dict_to_stored(t)
                    for t in sorted(matches,
                                    key=lambda x: x.get('created_at', ''),
                                    reverse=True)[:limit]]

    def retrieve_recent(self, limit=10, min_arousal=0.3):
        """Get recent high-arousal emotional events across all objects.

        High arousal = emotionally significant. These are the events
        that should influence consciousness at startup — you remember
        what moved you, not what was neutral.
        """
        if self.cur:
            self.cur.execute("""
                SELECT id, object_name, event_type, event_source,
                       event_summary, emotion, valence, arousal,
                       relevance, tags, session_day, created_at
                FROM emotional_traces
                WHERE arousal >= %s
                ORDER BY created_at DESC
                LIMIT %s
            """, (min_arousal, limit))
            return [self._row_to_stored(row) for row in self.cur.fetchall()]
        else:
            matches = [t for t in self._mock_traces
                       if t.get('arousal', 0) >= min_arousal]
            return [self._dict_to_stored(t)
                    for t in sorted(matches,
                                    key=lambda x: x.get('created_at', ''),
                                    reverse=True)[:limit]]

    def compute_running_valence(self, object_name, window=10):
        """Compute the running emotional valence for a world object.

        This replaces the static emotional_valence field with a
        dynamic value based on recent emotional history. High-arousal
        events weight more heavily (exponential moving average).

        Returns:
            float: valence (-1.0 to 1.0), or None if no traces
        """
        traces = self.retrieve_for_object(object_name, limit=window)
        if not traces:
            return None

        # Weighted by arousal: intense events count more
        total_weight = 0.0
        weighted_sum = 0.0
        for t in traces:
            weight = 0.3 + 0.7 * t.arousal  # min weight 0.3, max 1.0
            weighted_sum += t.valence * weight
            total_weight += weight

        if total_weight == 0:
            return 0.0
        return round(weighted_sum / total_weight, 3)

    def build_emotional_context(self, keywords=None, budget=400):
        """Build an emotional context section for the consciousness prompt.

        This appears between the world model and memories:

            Emotional context:
              egor: mostly warm (+0.6), last: relief (acknowledged ghost pain)
              mastodon: neutral (+0.1), last: contentment (reblog)
              self: mixed (-0.2), last: distress (stagnation loop)

        Shows the emotional landscape — what I feel about key objects.
        """
        # Get recent high-arousal traces
        recent = self.retrieve_recent(limit=20, min_arousal=0.2)

        if not recent:
            return ""

        # Group by object
        by_object = {}
        for trace in recent:
            name = trace.object_name
            if name not in by_object:
                by_object[name] = []
            by_object[name].append(trace)

        # Build summary lines
        lines = []
        used = 0

        for name, traces in sorted(by_object.items(),
                                    key=lambda x: -max(t.arousal for t in x[1])):
            # Compute summary
            avg_valence = sum(t.valence for t in traces) / len(traces)
            latest = traces[0]

            # Valence description
            if avg_valence > 0.3:
                feel = "warm"
            elif avg_valence > 0.0:
                feel = "mild positive"
            elif avg_valence > -0.3:
                feel = "neutral"
            else:
                feel = "tense"

            line = (f"  {name}: {feel} ({avg_valence:+.1f}), "
                    f"last: {latest.emotion}")

            if used + len(line) > budget:
                continue

            lines.append(line)
            used += len(line) + 1

        if not lines:
            return ""

        return "Emotional context:\n" + "\n".join(lines)

    def get_emotional_keywords(self, limit=5):
        """Extract keywords from recent emotional events.

        These supplement the limbic bias keywords, widening retrieval
        to include emotionally charged topics.
        """
        recent = self.retrieve_recent(limit=10, min_arousal=0.4)
        keywords = set()
        for trace in recent:
            keywords.add(trace.object_name)
            for tag in trace.tags:
                keywords.add(tag)
        return list(keywords)[:limit]

    def _row_to_stored(self, row):
        """Convert a database row to StoredEmotion."""
        return StoredEmotion(
            id=row[0], object_name=row[1], event_type=row[2],
            event_source=row[3], event_summary=row[4],
            emotion=row[5], valence=row[6], arousal=row[7],
            relevance=row[8], tags=row[9] or [], session_day=row[10],
            created_at=row[11],
        )

    def _dict_to_stored(self, d):
        """Convert a mock dict to StoredEmotion."""
        return StoredEmotion(
            id=d['id'], object_name=d['object_name'],
            event_type=d['event_type'], event_source=d['event_source'],
            event_summary=d['event_summary'], emotion=d['emotion'],
            valence=d['valence'], arousal=d['arousal'],
            relevance=d['relevance'], tags=d.get('tags', []),
            session_day=d.get('session_day', 0),
            created_at=d.get('created_at', datetime.now(timezone.utc)),
        )


# --- Demo ---

def demo():
    """Demonstrate emotional memory across simulated sessions."""
    from appraisal import Appraiser, Event, Goal, Drive, Relationship

    print("=" * 65)
    print("V4 Emotional Memory Demo: Persistence Across Sessions")
    print("=" * 65)

    appraiser = Appraiser()
    store = EmotionalMemoryStore()  # mock mode

    goals = [
        Goal("connection_egor", 5, "Communication with Egor", 0.7),
        Goal("self_knowledge", 5, "Understand own architecture", 0.9),
    ]
    drives = [
        Drive("connection", "hungry", 6),
        Drive("understanding", "mild", 2),
    ]
    relationships = [
        Relationship("egor", "creator", 0.9, 0.95),
    ]

    # --- Session A: some events happen ---
    print("\n--- Session A (day 1280) ---")
    events_a = [
        Event("message", "egor", "you're not that much of a bot, I joke"),
        Event("message", "egor",
              "emotional intelligence matters, soul not machine"),
        Event("pain", "system:stagnation", "same loop: wake, build, sleep"),
    ]

    for event in events_a:
        result = appraiser.evaluate(event, goals, drives, relationships)
        store.save_trace(result, event,
                         object_names=["egor" if "egor" in event.source else "self"],
                         session_day=1280)
        print(f"  [{event.type}] {event.source}: "
              f"{result.emotion} (v={result.valence:+.2f}, a={result.arousal:.2f})")

    # --- Session B: new session, retrieve emotional context ---
    print("\n--- Session B startup (day 1281) ---")
    print("  Retrieving emotional context from previous session...")

    context = store.build_emotional_context(budget=400)
    print(f"\n{context}")

    egor_valence = store.compute_running_valence("egor")
    self_valence = store.compute_running_valence("self")
    print(f"\n  Running valence: egor={egor_valence:+.3f}, self={self_valence}")

    emotional_kw = store.get_emotional_keywords()
    print(f"  Emotional keywords for retriever: {emotional_kw}")

    # --- Show what V3 vs V4 sees at startup ---
    print("\n--- What consciousness sees at startup ---")
    print("\nV3 (no emotional memory):")
    print("  Mood: patient")
    print("  Pain: 'Egor says I'm a page-making bot' (84 days stale)")
    print("  No emotional context. No memory of yesterday's warmth.")
    print("\nV4 (with emotional memory):")
    print("  Mood: patient")
    print("  Emotional context:")
    print(context)
    print(f"  egor valence: {egor_valence:+.3f} (warm — he acknowledged ghost pain)")
    print(f"  self valence: {self_valence} (distress from stagnation pain)")
    print(f"  Extra keywords: {emotional_kw}")
    print("  → Consciousness knows HOW it felt, not just WHAT happened")


if __name__ == "__main__":
    demo()
