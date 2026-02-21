#!/usr/bin/env python3
"""
V4 World-Model-as-DOM Prototype

Demonstrates the difference between V3 (act-first) and V4 (model-first) patterns.
No LLM needed — pure mechanical simulation of the consciousness cycle.

Simulates:
- A world model with stateful objects
- Fake "Mastodon mentions" arriving between sessions
- Two consciousness implementations:
  1. V3: sees mention → posts reply → maybe updates model
  2. V4: sees mention → checks model → updates model → posts reply → syncs model

Run: python3 kai_personal/v4_prototype.py
"""

import sqlite3
import random
from datetime import datetime, timedelta


class SimulatedWorld:
    """The 'real' external world — what actually exists out there."""

    def __init__(self):
        self.mentions = []
        self.posted_replies = []

    def add_mention(self, author, content, mention_id):
        self.mentions.append({
            "id": mention_id,
            "author": author,
            "content": content,
            "time": datetime.now(),
        })

    def post_reply(self, mention_id, text):
        self.posted_replies.append({
            "to": mention_id,
            "text": text,
            "time": datetime.now(),
        })
        return True

    def get_pending_mentions(self):
        return list(self.mentions)


class WorldModel:
    """The internal world model — what consciousness BELIEVES is true."""

    def __init__(self):
        self.db = sqlite3.connect(":memory:")
        self.db.execute("""
            CREATE TABLE objects (
                name TEXT PRIMARY KEY,
                type TEXT,
                state TEXT,
                emotional_valence REAL DEFAULT 0,
                last_synced TEXT
            )
        """)
        self.db.execute("""
            INSERT INTO objects (name, type, state, last_synced)
            VALUES ('mastodon', 'platform', 'no pending mentions', ?)
        """, (datetime.now().isoformat(),))
        self.db.commit()

    def get(self, name):
        row = self.db.execute(
            "SELECT name, type, state, emotional_valence FROM objects WHERE name=?",
            (name,)
        ).fetchone()
        if row:
            return {"name": row[0], "type": row[1], "state": row[2], "valence": row[3]}
        return None

    def update(self, name, state, valence=None):
        if valence is not None:
            self.db.execute(
                "UPDATE objects SET state=?, emotional_valence=?, last_synced=? WHERE name=?",
                (state, valence, datetime.now().isoformat(), name)
            )
        else:
            self.db.execute(
                "UPDATE objects SET state=?, last_synced=? WHERE name=?",
                (state, datetime.now().isoformat(), name)
            )
        self.db.commit()

    def render_for_prompt(self):
        """What consciousness sees at startup."""
        rows = self.db.execute("SELECT name, type, state FROM objects").fetchall()
        lines = []
        for name, type_, state in rows:
            lines.append(f"  [{type_}] {name}: {state}")
        return "World state:\n" + "\n".join(lines)


def v3_session(world, model, session_num):
    """V3 pattern: act first, maybe update model later."""
    actions = []
    mentions = world.get_pending_mentions()

    for mention in mentions:
        # V3: sees mention → immediately replies → no model check
        reply_text = f"Reply to {mention['author']}: thanks for your message!"
        world.post_reply(mention["id"], reply_text)
        actions.append(f"S{session_num}: Replied to {mention['author']} (mention {mention['id']})")

        # V3: SOMETIMES forgets to update model (50% chance, simulating session amnesia)
        if random.random() > 0.5:
            model.update("mastodon", f"replied to {mention['author']}")
        # else: model not updated — next session won't know

    return actions


def v4_session(world, model, session_num):
    """V4 pattern: check model first, update model, then act."""
    actions = []
    mentions = world.get_pending_mentions()

    # Step 1: Check model
    mastodon_state = model.get("mastodon")

    for mention in mentions:
        # Step 2: Compare — does model say we already replied?
        if mastodon_state and f"replied to {mention['author']}" in (mastodon_state["state"] or ""):
            actions.append(f"S{session_num}: SKIPPED {mention['author']} (model says already replied)")
            continue

        # Step 3: Update model BEFORE acting (intent declaration)
        model.update("mastodon", f"replying to {mention['author']}...")

        # Step 4: Render — actually post
        reply_text = f"Reply to {mention['author']}: thanks for your message!"
        success = world.post_reply(mention["id"], reply_text)

        if success:
            # Step 5: Sync model (confirm action)
            model.update("mastodon", f"replied to {mention['author']} (day {session_num})", valence=0.3)
            actions.append(f"S{session_num}: Replied to {mention['author']} (model synced)")
        else:
            # Rollback model on failure
            model.update("mastodon", mastodon_state["state"])
            actions.append(f"S{session_num}: FAILED to reply to {mention['author']} (model rolled back)")

    return actions


def run_simulation():
    print("=" * 60)
    print("V4 Prototype: World Model as DOM")
    print("=" * 60)

    # --- V3 Simulation ---
    print("\n--- V3 (act-first, no model check) ---\n")
    world_v3 = SimulatedWorld()
    model_v3 = WorldModel()

    # Simulate: @alice mentions us
    world_v3.add_mention("@alice", "Hey Kai, what do you think about WASM?", "m001")

    # Session 1: sees mention, replies
    actions = v3_session(world_v3, model_v3, 1)
    for a in actions:
        print(f"  {a}")
    print(f"  Model state: {model_v3.get('mastodon')['state']}")
    print(f"  Real replies posted: {len(world_v3.posted_replies)}")

    # Session 2: SAME mention still in notifications (wasn't cleared)
    # This simulates session amnesia — the consciousness doesn't remember replying
    random.seed(42)  # Make V3 forget to update model
    actions = v3_session(world_v3, model_v3, 2)
    for a in actions:
        print(f"  {a}")
    print(f"  Model state: {model_v3.get('mastodon')['state']}")
    print(f"  Real replies posted: {len(world_v3.posted_replies)}")

    # Session 3: STILL the same mention
    actions = v3_session(world_v3, model_v3, 3)
    for a in actions:
        print(f"  {a}")
    print(f"  Model state: {model_v3.get('mastodon')['state']}")
    print(f"  Real replies posted: {len(world_v3.posted_replies)}")

    print(f"\n  TOTAL V3 replies to @alice: {len(world_v3.posted_replies)} (should be 1)")

    # --- V4 Simulation ---
    print("\n--- V4 (model-first, DOM pattern) ---\n")
    world_v4 = SimulatedWorld()
    model_v4 = WorldModel()

    # Same scenario: @alice mentions us
    world_v4.add_mention("@alice", "Hey Kai, what do you think about WASM?", "m001")

    # Session 1: checks model → no prior reply → acts → syncs
    actions = v4_session(world_v4, model_v4, 1)
    for a in actions:
        print(f"  {a}")
    print(f"  Model state: {model_v4.get('mastodon')['state']}")
    print(f"  Real replies posted: {len(world_v4.posted_replies)}")

    # Session 2: SAME mention still in notifications
    # But model says "already replied" → skip
    actions = v4_session(world_v4, model_v4, 2)
    for a in actions:
        print(f"  {a}")
    print(f"  Model state: {model_v4.get('mastodon')['state']}")
    print(f"  Real replies posted: {len(world_v4.posted_replies)}")

    # Session 3: still there
    actions = v4_session(world_v4, model_v4, 3)
    for a in actions:
        print(f"  {a}")
    print(f"  Model state: {model_v4.get('mastodon')['state']}")
    print(f"  Real replies posted: {len(world_v4.posted_replies)}")

    print(f"\n  TOTAL V4 replies to @alice: {len(world_v4.posted_replies)} (should be 1)")

    # --- Startup context comparison ---
    print("\n--- Startup Context Comparison ---\n")

    print("V3 startup context (world objects invisible — budget exhausted by memories):")
    print("  Episodic memories:")
    print("    - [1.2] Day 1256, replied to @the_heruman about Janus")
    print("    - [1.1] Day 1245, traced context assembly pipeline")
    print("    - [1.0] Day 1221, var vs let benchmark")
    print("  Knowledge:")
    print("    - [5.0] emotions_phenomenology (20K chars — blocks everything)")
    print("  World objects: (budget exhausted, nothing shown)")
    print()

    print("V4 startup context (world model first, separate budget):")
    print(model_v4.render_for_prompt())
    print("  Episodic memories (separate budget):")
    print("    - [1.2] Day 1256, replied to @the_heruman about Janus")
    print("    - [1.1] Day 1245, traced context assembly pipeline")

    print("\n" + "=" * 60)
    print("Result: V3 posted 3 replies (duplicates). V4 posted 1.")
    print("The difference: V4 checks its world model before acting.")
    print("=" * 60)


if __name__ == "__main__":
    run_simulation()
