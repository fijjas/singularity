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
import json
import time
from dataclasses import dataclass, field, asdict

from appraisal import Appraiser, Event, Goal, Drive, Relationship
from integration import IntegrationHub
from emotional_memory import EmotionalMemoryStore
from chunking import ChunkMiner
from v4_retriever import (
    retrieve_v4, retrieve_world_objects_v4,
    retrieve_episodic, retrieve_semantic,
    _format_world_v4, _format_memories_v4,
)


@dataclass
class TraceStep:
    """One step in the pipeline trace."""
    stage: str          # e.g., "emotional_keywords", "appraisal"
    input_summary: str  # what went in (human-readable)
    output_summary: str # what came out
    item_count: int = 0 # how many items produced (for capacity analysis)
    elapsed_ms: float = 0.0
    detail: dict = field(default_factory=dict)  # machine-readable details


class PipelineTracer:
    """Records the thinking process of the V4 pipeline.

    Each pipeline stage calls tracer.step() to record what happened.
    The full trace can be exported as JSON for human review,
    real-time display, or post-hoc analysis.
    """

    def __init__(self, session_day=0, enabled=True):
        self.session_day = session_day
        self.enabled = enabled
        self.steps = []
        self.start_time = time.time()

    def step(self, stage, input_summary, output_summary,
             item_count=0, detail=None):
        """Record a pipeline step."""
        if not self.enabled:
            return
        elapsed = (time.time() - self.start_time) * 1000
        self.steps.append(TraceStep(
            stage=stage,
            input_summary=input_summary,
            output_summary=output_summary,
            item_count=item_count,
            elapsed_ms=round(elapsed, 1),
            detail=detail or {},
        ))

    def total_items(self):
        """Total items projected to consciousness (Miller capacity)."""
        return sum(s.item_count for s in self.steps)

    def to_dict(self):
        """Export trace as JSON-serializable dict."""
        return {
            "session_day": self.session_day,
            "total_items": self.total_items(),
            "steps": [asdict(s) for s in self.steps],
        }

    def to_json(self, indent=2):
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def summary(self):
        """Human-readable one-line summary."""
        stages = " → ".join(s.stage for s in self.steps)
        return (f"[day {self.session_day}] {len(self.steps)} stages, "
                f"{self.total_items()} items projected | {stages}")


class V4Pipeline:
    """Complete V4 consciousness pipeline.

    Wires together all V4 modules into a single coherent system.
    Can operate with a real database cursor or in mock mode.
    """

    def __init__(self, cur=None, session_day=0, trace=True):
        self.cur = cur
        self.session_day = session_day

        # Initialize modules
        self.appraiser = Appraiser()
        self.emotional_store = EmotionalMemoryStore(cur)
        self.hub = IntegrationHub(self.appraiser)
        self.chunker = ChunkMiner()

        # Pipeline tracer
        self.tracer = PipelineTracer(session_day=session_day, enabled=trace)

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

        self.tracer.step(
            "keyword_merge",
            f"limbic={limbic_keywords}, emotional={emotional_kw}",
            f"merged={all_keywords}",
            item_count=len(all_keywords),
            detail={"limbic": limbic_keywords, "emotional": emotional_kw,
                    "merged": all_keywords},
        )

        # Step 2: Behavioral rules (chunking)
        active_rules = self.chunker.select_for_context(
            self.chunker.rules, all_keywords)
        rules_section = self.chunker.render_rules(
            active_rules, budget=rules_budget)

        self.tracer.step(
            "behavioral_rules",
            f"{len(self.chunker.rules)} rules × {len(all_keywords)} keywords",
            f"{len(active_rules)} rules activated",
            item_count=len(active_rules),
            detail={"rule_names": [r.name for r in active_rules]},
        )

        # Step 3: Emotional context
        emotional_section = self.emotional_store.build_emotional_context(
            keywords=all_keywords, budget=emotional_budget)

        self.tracer.step(
            "emotional_context",
            f"keywords={all_keywords}",
            f"{len(emotional_section)} chars of emotional context",
            detail={"preview": emotional_section[:200] if emotional_section
                    else "(empty)"},
        )

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

        self.tracer.step(
            "world_model",
            f"query with {len(all_keywords)} keywords, limit=8",
            f"{len(world_objects)} objects retrieved",
            item_count=len(world_objects),
            detail={"objects": [o.get('name', '?') for o in world_objects]},
        )

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

        self.tracer.step(
            "memory_retrieval",
            f"keywords={all_keywords}",
            f"{len(episodic)} episodic + {len(semantic)} semantic",
            item_count=len(episodic) + len(semantic),
            detail={
                "episodic_previews": [e.get('content', '')[:80]
                                      for e in episodic] if episodic else [],
                "semantic_previews": [s.get('content', '')[:80]
                                      for s in semantic] if semantic else [],
            },
        )

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

        self.tracer.step(
            "assembly",
            f"{len(sections)} sections",
            f"{len(full_text)} chars, {self.tracer.total_items()} total items",
            detail={"section_names": [name for name, _ in sections],
                    "miller_capacity": self.tracer.total_items()},
        )

        return {
            'sections': sections,
            'full_text': full_text,
            'keywords_used': all_keywords,
            'rules_active': len(active_rules),
            'world_objects': world_objects,
            'episodic': episodic,
            'semantic': semantic,
            'trace': self.tracer.to_dict(),
        }

    def process_event(self, event, goals=None, drives=None,
                      relationships=None):
        """Process an event through the full V4 pipeline.

        Event → Appraisal → Integration → Emotional Memory Storage
        """
        # Appraise
        result = self.hub.process_event(event, goals, drives, relationships)

        self.tracer.step(
            "appraisal",
            f"[{event.type}] {event.source}: {event.content[:60]}",
            f"{result.emotion} (v={result.valence:+.2f}, "
            f"a={result.arousal:.2f}, r={result.relevance:.2f})",
            detail={"emotion": result.emotion, "valence": result.valence,
                    "arousal": result.arousal, "relevance": result.relevance,
                    "tags": result.tags, "explanation": result.explanation},
        )

        # Identify related world objects
        objects = self.hub._identify_objects(event)

        # Store emotional trace
        self.emotional_store.save_trace(
            result, event,
            object_names=list(objects),
            session_day=self.session_day,
        )

        self.tracer.step(
            "integration",
            f"{result.emotion} → objects={list(objects)}",
            f"trace stored, {len(objects)} objects updated",
            detail={"objects_updated": list(objects)},
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

    # --- Trace output ---
    print("\n--- Pipeline Trace ---")
    print(f"Summary: {pipeline_new.tracer.summary()}")
    print()
    for step in pipeline_new.tracer.steps:
        print(f"  [{step.elapsed_ms:6.1f}ms] {step.stage}")
        print(f"           in:  {step.input_summary}")
        print(f"           out: {step.output_summary}")
        if step.item_count:
            print(f"           items: {step.item_count}")
    print(f"\n  Total items projected: {pipeline_new.tracer.total_items()}"
          f" (Miller capacity: 7±2, Cowan: 4±1)")


if __name__ == "__main__":
    demo()
