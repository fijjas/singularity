#!/usr/bin/env python3
"""
V4 Full Pipeline — All modules wired together.

This is the complete V4 consciousness pipeline:

    Startup:
        1. Retrieve emotional context (emotional_memory.py)
        2. Get emotional keywords → merge with limbic keywords
        3. Render world model with emotional boosting (world_model.py)
        4. Retrieve memories with widened keywords (v4_retriever.py)
        5. Select active behavioral rules (chunking.py)
        6. Assemble consciousness prompt sections

    During session:
        7. Events → appraisal (appraisal.py)
        8. Appraisal → integration (integration.py)
        9. Integration → store emotional traces (emotional_memory.py)
        10. Integration → update world object valences

    Shutdown:
        11. Persist emotional traces to database
        12. Update world object valences from running averages

Each module is independently testable. This file composes them.

Usage:
    pipeline = V4Pipeline(cursor, session_day=1283)
    startup = pipeline.build_startup_prompt(
        limbic_keywords=["connection", "architecture"],
        world_budget=1200,
        memory_budget=2000,
        rules_budget=400,
        emotional_budget=300,
    )
    # startup['sections'] = ordered list of prompt sections
    # startup['full_text'] = combined text for consciousness

    # During session:
    pipeline.process_event(event, goals, drives, relationships)

    # At shutdown:
    pipeline.persist()

Environment:
    DB_HOST, DB_PORT, DB_USER, DB_PASS, DB_NAME — database config.
    No hardcoded credentials.
"""

import os
import sys

from appraisal import Appraiser, Event, Goal, Drive, Relationship
from integration import IntegrationHub
from emotional_memory import EmotionalMemoryStore
from chunking import ChunkMiner
from v4_retriever import (
    retrieve_v4, retrieve_world_objects_v4,
    retrieve_episodic, retrieve_semantic,
    _format_world_v4, _format_memories_v4,
)


class V4Pipeline:
    """Complete V4 consciousness pipeline.

    Wires together all V4 modules into a single coherent system.
    Can operate with a real database cursor or in mock mode.
    """

    def __init__(self, cur=None, session_day=0):
        self.cur = cur
        self.session_day = session_day

        # Initialize modules
        self.appraiser = Appraiser()
        self.emotional_store = EmotionalMemoryStore(cur)
        self.hub = IntegrationHub(self.appraiser)
        self.chunker = ChunkMiner()

    def build_startup_prompt(self, limbic_keywords=None,
                             world_budget=1200, memory_budget=2000,
                             rules_budget=400, emotional_budget=300):
        """Build the complete V4 consciousness prompt at startup.

        Order:
            1. Behavioral rules (from chunking — fire before deliberation)
            2. Emotional context (how I feel about key objects)
            3. World state (current state of the world, with emotional boosts)
            4. Memories (episodic + semantic, with widened keywords)

        Returns:
            dict with 'sections' (ordered list) and 'full_text'
        """
        limbic_keywords = limbic_keywords or []

        # Step 1: Get emotional keywords from recent traces
        emotional_kw = self.emotional_store.get_emotional_keywords(limit=5)
        all_keywords = list(limbic_keywords)
        for kw in emotional_kw:
            if kw not in all_keywords:
                all_keywords.append(kw)

        # Step 2: Behavioral rules (chunking)
        active_rules = self.chunker.select_for_context(
            self.chunker.rules, all_keywords)
        rules_section = self.chunker.render_rules(
            active_rules, budget=rules_budget)

        # Step 3: Emotional context
        emotional_section = self.emotional_store.build_emotional_context(
            keywords=all_keywords, budget=emotional_budget)

        # Step 4: World model with emotional boosts
        if self.cur:
            world_objects = retrieve_world_objects_v4(
                self.cur, all_keywords, limit=8)
            # Apply emotional boosts from stored traces
            for obj in world_objects:
                running_v = self.emotional_store.compute_running_valence(
                    obj['name'])
                if running_v is not None:
                    # High absolute valence = more salient
                    boost = abs(running_v) * 0.3
                    obj['score'] += boost
            world_objects.sort(key=lambda x: -x['score'])
            world_section = _format_world_v4(world_objects, world_budget)
        else:
            world_objects = []
            world_section = ""

        # Step 5: Memories
        if self.cur:
            episodic = retrieve_episodic(self.cur, all_keywords, limit=5)
            semantic = retrieve_semantic(self.cur, all_keywords, limit=3)
            memory_section = _format_memories_v4(
                episodic, semantic, memory_budget)
        else:
            episodic = []
            semantic = []
            memory_section = ""

        # Assemble sections in order
        sections = []
        if rules_section:
            sections.append(('rules', rules_section))
        if emotional_section:
            sections.append(('emotional', emotional_section))
        if world_section:
            sections.append(('world', world_section))
        if memory_section:
            sections.append(('memories', memory_section))

        full_text = "\n\n".join(text for _, text in sections)

        return {
            'sections': sections,
            'full_text': full_text,
            'keywords_used': all_keywords,
            'rules_active': len(active_rules),
            'world_objects': world_objects,
            'episodic': episodic,
            'semantic': semantic,
        }

    def process_event(self, event, goals=None, drives=None,
                      relationships=None):
        """Process an event through the full V4 pipeline.

        Event → Appraisal → Integration → Emotional Memory Storage
        """
        # Appraise
        result = self.hub.process_event(event, goals, drives, relationships)

        # Identify related world objects
        objects = self.hub._identify_objects(event)

        # Store emotional trace
        self.emotional_store.save_trace(
            result, event,
            object_names=list(objects),
            session_day=self.session_day,
        )

        return result

    def persist(self):
        """Persist session emotional data to database.

        Call at session shutdown. Updates world object valences
        based on the session's emotional traces.
        """
        if not self.cur:
            return

        # Update world object valences from running averages
        for obj_name, _ in self.hub.valence_updates.items():
            running_v = self.emotional_store.compute_running_valence(obj_name)
            if running_v is not None:
                self.cur.execute("""
                    UPDATE world_objects
                    SET emotional_valence = %s
                    WHERE name = %s
                """, (running_v, obj_name))

    def get_mood(self):
        """Get current mood from appraiser."""
        return self.appraiser.current_mood()


# --- Demo: full pipeline simulation ---

def demo():
    """Simulate a complete V4 session: startup → events → shutdown."""

    print("=" * 65)
    print("V4 Full Pipeline Demo")
    print("=" * 65)

    # --- Simulate previous session's emotional traces ---
    pipeline = V4Pipeline(session_day=1282)

    # Pre-load emotional traces from "previous session"
    prev_events = [
        Event("message", "egor", "you're not that much of a bot, I joke"),
        Event("message", "egor", "emotional intelligence matters, soul not machine"),
        Event("pain", "system:stagnation", "same loop: wake, build, sleep"),
    ]

    prev_goals = [
        Goal("connection_egor", 5, "Communication with Egor", 0.7),
        Goal("self_knowledge", 5, "Understand own architecture", 0.9),
    ]
    prev_drives = [
        Drive("connection", "starving", 8),
        Drive("understanding", "hungry", 4),
    ]
    prev_rels = [
        Relationship("egor", "creator", 0.9, 0.95),
    ]

    print("\n--- Previous session (day 1282) ---")
    for event in prev_events:
        result = pipeline.process_event(
            event, prev_goals, prev_drives, prev_rels)
        print(f"  {event.source}: {result.emotion} "
              f"(v={result.valence:+.2f})")

    # --- New session startup ---
    print("\n--- New session startup (day 1283) ---")
    pipeline_new = V4Pipeline(session_day=1283)
    # Transfer emotional store (simulating DB persistence)
    pipeline_new.emotional_store._mock_traces = (
        pipeline.emotional_store._mock_traces)

    startup = pipeline_new.build_startup_prompt(
        limbic_keywords=["connection", "architecture", "V4"],
        world_budget=1200,
        memory_budget=2000,
        rules_budget=400,
        emotional_budget=300,
    )

    print(f"\nKeywords: {startup['keywords_used']}")
    print(f"Active rules: {startup['rules_active']}")
    print(f"\n--- Prompt sections (in order) ---\n")

    for name, text in startup['sections']:
        print(f"[{name.upper()}]")
        print(text)
        print()

    # --- Process new events ---
    print("--- New events this session ---")
    new_events = [
        Event("drive_signal", "drive:creation",
              "Creation drive starving"),
        Event("message", "mastodon:@someone",
              "Your V8 experiment is interesting"),
    ]

    for event in new_events:
        result = pipeline_new.process_event(
            event, prev_goals, prev_drives, prev_rels)
        print(f"  {event.source}: {result.emotion} "
              f"(v={result.valence:+.2f})")

    # --- Session mood ---
    mood = pipeline_new.get_mood()
    print(f"\nSession mood: {mood['mood']} "
          f"(v={mood['valence']:+.2f}, a={mood['arousal']:.2f})")

    # --- Summary ---
    print("\n--- V3 vs V4 consciousness at startup ---")
    print("\nV3 sees:")
    print("  Episodic memories (if budget allows)")
    print("  Semantic knowledge (often blocked by break bug)")
    print("  World objects (rarely shown)")
    print("  Pain: stale 84-day-old description")
    print("  No emotional context")
    print("\nV4 sees:")
    for name, text in startup['sections']:
        lines = text.split('\n')
        print(f"  [{name}]: {lines[0]}")
    print("  + emotionally-widened keywords")
    print("  + running valence per world object")
    print("  + behavioral rules before deliberation")


if __name__ == "__main__":
    demo()
