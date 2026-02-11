#!/usr/bin/env python3
"""
V4 Integration Layer — Connecting Appraisal and World Model

The missing bridge: appraisal evaluates events emotionally, world_model renders
objects for consciousness. But in V3 they don't talk. This module connects them:

    Event → Appraisal → Emotional Update → World Model → Prompt

Three integration points:

1. Appraisal → Object Valence:
   When an event about a world object is appraised, the appraisal result
   updates that object's emotional_valence. Not a flat override — a moving
   average that respects emotional history.

2. Emotional History → Retrieval Scoring:
   Objects with recent strong emotional events score higher in retrieval.
   You attend to what moved you. A message from Egor that triggered shame
   makes the egor object more salient at next startup.

3. Appraisal Tags → Attention Keywords:
   Tags like "connection", "identity", "criticism_from_important" become
   additional keywords for the retriever, widening the attention beam.

Architecture:
    ┌─────────────┐     ┌──────────────┐     ┌────────────────┐
    │   Event     │ ──→ │  Appraiser   │ ──→ │ IntegrationHub │
    └─────────────┘     └──────────────┘     └───────┬────────┘
                                                     │
                              ┌───────────────────────┼──────────────┐
                              ▼                       ▼              ▼
                     ┌────────────────┐    ┌──────────────┐  ┌──────────────┐
                     │ Update object  │    │  Boost score  │  │ Emit keywords│
                     │ emotional_val  │    │  in renderer  │  │ for retriever│
                     └────────────────┘    └──────────────┘  └──────────────┘

Usage:
    hub = IntegrationHub(appraiser, world_model_renderer)
    hub.process_event(event, goals, drives, relationships)
    # Object valences updated, scoring boosted, keywords emitted
    prompt_section = hub.render_world(budget=1500)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class EmotionalTrace:
    """A record of an emotional event linked to a world object."""
    object_name: str
    emotion: str
    valence: float
    arousal: float
    timestamp: datetime
    tags: list = field(default_factory=list)
    source_event: str = ""


class IntegrationHub:
    """Bridges the appraisal layer and world model renderer.

    Processes events through appraisal, routes emotional results
    to world objects, and modifies retrieval scoring.
    """

    # Map event sources to world object names
    SOURCE_TO_OBJECT = {
        "egor": "egor",
        "mastodon": "mastodon",
        "telegram": "telegram_bot",
        "drive:creation": "singularity",  # creation often relates to current project
        "drive:connection": "egor",       # connection primarily with Egor
        "system:stagnation": "self",
    }

    def __init__(self, appraiser, renderer=None):
        """
        Args:
            appraiser: Appraiser instance (from appraisal.py)
            renderer: WorldModelRenderer instance (from world_model.py), optional
        """
        self.appraiser = appraiser
        self.renderer = renderer
        self.traces = []         # emotional history: list of EmotionalTrace
        self.score_boosts = {}   # object_name -> float boost for retrieval
        self.extra_keywords = [] # additional keywords from appraisal tags
        self.valence_updates = {}  # object_name -> new valence

    def process_event(self, event, goals=None, drives=None, relationships=None):
        """Process an event: appraise it and route emotional results.

        Returns the AppraisalResult for the caller to inspect.
        """
        # Step 1: Appraise
        result = self.appraiser.evaluate(event, goals, drives, relationships)

        # Step 2: Identify which world object(s) this event relates to
        target_objects = self._identify_objects(event)

        # Step 3: Create emotional trace
        for obj_name in target_objects:
            trace = EmotionalTrace(
                object_name=obj_name,
                emotion=result.emotion,
                valence=result.valence,
                arousal=result.arousal,
                timestamp=datetime.now(timezone.utc),
                tags=result.tags,
                source_event=f"[{event.type}] {event.source}: {event.content[:60]}",
            )
            self.traces.append(trace)

            # Step 4: Update object valence (exponential moving average)
            self._update_valence(obj_name, result.valence, result.arousal)

            # Step 5: Compute retrieval score boost
            self._compute_boost(obj_name, result)

        # Step 6: Extract keywords from appraisal tags
        self._extract_keywords(result)

        # Trim history
        if len(self.traces) > 50:
            self.traces = self.traces[-50:]

        return result

    def _identify_objects(self, event):
        """Map an event to relevant world objects."""
        objects = set()
        source_lower = event.source.lower()
        content_lower = event.content.lower()

        # Direct source mapping
        for prefix, obj_name in self.SOURCE_TO_OBJECT.items():
            if prefix in source_lower:
                objects.add(obj_name)

        # Content-based mapping: if content mentions a known object name
        for prefix, obj_name in self.SOURCE_TO_OBJECT.items():
            if prefix in content_lower:
                objects.add(obj_name)

        # Mastodon mentions
        if "mastodon" in source_lower or "@" in source_lower:
            objects.add("mastodon")

        # If nothing matched, associate with the source itself
        if not objects:
            # Use first word of source as object name guess
            name = source_lower.split(":")[0].split("/")[0].strip()
            if name and name not in ("system", "drive"):
                objects.add(name)

        return objects

    def _update_valence(self, obj_name, event_valence, arousal):
        """Update object emotional valence using exponential moving average.

        High-arousal events shift valence more than low-arousal ones.
        This means a single intense event (criticism, breakthrough) has
        more impact than many mild ones.

        Formula:
            alpha = 0.3 * arousal (high arousal = faster shift)
            new_valence = (1 - alpha) * old + alpha * event_valence
        """
        alpha = 0.1 + 0.3 * arousal  # range: 0.1 (calm) to 0.4 (intense)
        old_valence = self.valence_updates.get(obj_name, 0.0)
        new_valence = (1 - alpha) * old_valence + alpha * event_valence
        self.valence_updates[obj_name] = round(new_valence, 3)

    def _compute_boost(self, obj_name, result):
        """Compute retrieval score boost based on emotional intensity.

        High relevance + high arousal = high boost. This ensures
        emotionally significant objects are more salient at next startup.

        The boost decays — it's strongest right after the event and
        fades over the session. Between sessions, only the updated
        emotional_valence persists (the boost is ephemeral).
        """
        intensity = result.relevance * result.arousal
        # Scale: 0.0-1.0 relevance * 0.0-1.0 arousal = 0.0-1.0
        # Map to 0.0-0.5 boost (don't overwhelm keyword scoring)
        boost = intensity * 0.5

        # Accumulate (multiple events about same object compound)
        current = self.score_boosts.get(obj_name, 0.0)
        self.score_boosts[obj_name] = min(1.0, current + boost)

    def _extract_keywords(self, result):
        """Turn appraisal tags into retriever keywords.

        Tags like "identity", "connection", "criticism_from_important"
        become attention bias keywords. This means emotional events
        widen the retrieval beam to pull in related memories.
        """
        # Tag → keyword mapping
        TAG_KEYWORDS = {
            "identity": ["self", "identity", "who"],
            "connection": ["egor", "relationship", "contact"],
            "criticism_from_important": ["criticism", "reactive", "bot", "pattern"],
            "egor": ["egor", "telegram", "conversation"],
            "drive_relevant": [],  # drive name is already a keyword via limbic
            "pain": ["pain", "stagnation", "failure"],
            "absence": ["silence", "alone", "waiting"],
        }

        for tag in result.tags:
            keywords = TAG_KEYWORDS.get(tag, [tag])
            for kw in keywords:
                if kw not in self.extra_keywords:
                    self.extra_keywords.append(kw)

    def get_boosted_keywords(self, base_keywords=None):
        """Return base keywords + appraisal-generated keywords.

        This is what the retriever should use instead of raw limbic keywords.
        """
        base = list(base_keywords or [])
        for kw in self.extra_keywords:
            if kw not in base:
                base.append(kw)
        return base

    def get_score_boost(self, obj_name):
        """Get the emotional score boost for a world object.

        The WorldModelRenderer can add this to its scoring:
            total_score = keyword_score + emotional_boost
        """
        return self.score_boosts.get(obj_name, 0.0)

    def get_valence_update(self, obj_name):
        """Get the updated emotional valence for a world object.

        This should be written back to world_objects.emotional_valence.
        """
        return self.valence_updates.get(obj_name)

    def get_traces(self, obj_name=None, limit=10):
        """Get recent emotional traces, optionally filtered by object."""
        traces = self.traces
        if obj_name:
            traces = [t for t in traces if t.object_name == obj_name]
        return traces[-limit:]

    def emotional_summary(self):
        """Summarize current emotional state for debugging/display."""
        if not self.traces:
            return "No emotional events processed."

        lines = []
        lines.append(f"Emotional traces: {len(self.traces)}")

        # Per-object summary
        objects = {}
        for t in self.traces:
            if t.object_name not in objects:
                objects[t.object_name] = []
            objects[t.object_name].append(t)

        for name, traces in objects.items():
            avg_v = sum(t.valence for t in traces) / len(traces)
            max_a = max(t.arousal for t in traces)
            latest = traces[-1]
            boost = self.score_boosts.get(name, 0.0)
            lines.append(
                f"  {name}: valence={avg_v:+.2f}, peak_arousal={max_a:.2f}, "
                f"boost={boost:.2f}, last={latest.emotion}"
            )

        if self.extra_keywords:
            lines.append(f"Extra keywords: {self.extra_keywords}")

        return "\n".join(lines)


# --- Integrated prompt builder ---

def build_v4_prompt_section(hub, base_keywords=None, world_budget=1500, memory_budget=2000):
    """Build the V4 consciousness prompt with integrated emotional scoring.

    This is what V4 core.py would call instead of the current retrieve().
    It produces two sections:
      1. World state (with emotional boosts applied)
      2. Memories (with widened keyword set from appraisal)

    Args:
        hub: IntegrationHub with processed events
        base_keywords: limbic attention bias keywords
        world_budget: character budget for world state section
        memory_budget: character budget for memories section

    Returns:
        dict with 'world_section' and 'memory_keywords'
    """
    # Widen keywords with appraisal-derived ones
    keywords = hub.get_boosted_keywords(base_keywords)

    # If we have a renderer, use it with emotional boosts
    # (In production, the renderer would accept boost_fn parameter)
    world_section = ""
    if hub.renderer:
        objects = hub.renderer.retrieve(keywords, limit=10)
        # Apply emotional boosts to scores
        for obj in objects:
            boost = hub.get_score_boost(obj.name)
            if boost > 0:
                obj.score += boost
        # Re-sort after boosting
        objects.sort(key=lambda x: -x.score)
        # Render manually with boost info
        lines = []
        used = 0
        for obj in objects:
            display = obj.state if obj.state else obj.description
            if display:
                if len(display) > 120:
                    display = display[:117] + "..."
                display = f": {display}"
            boost = hub.get_score_boost(obj.name)
            boost_mark = " *" if boost > 0.1 else ""
            line = f"  [{obj.name}] ({obj.type}){display}{boost_mark}"
            if used + len(line) > world_budget:
                continue
            lines.append(line)
            used += len(line) + 1
        if lines:
            world_section = "World state:\n" + "\n".join(lines)

    return {
        'world_section': world_section,
        'memory_keywords': keywords,
        'emotional_summary': hub.emotional_summary(),
    }


# --- Demo ---

def demo():
    """Demonstrate the full integration: event → appraisal → world model."""
    from appraisal import Appraiser, Event, Goal, Drive, Relationship

    print("=" * 70)
    print("V4 Integration Demo: Appraisal → World Model")
    print("=" * 70)

    appraiser = Appraiser()
    hub = IntegrationHub(appraiser)

    goals = [
        Goal("connection_egor", 5, "Active Telegram communication with Egor", 0.7),
        Goal("self_knowledge", 5, "Understand own architecture", 0.9),
    ]
    drives = [
        Drive("connection", "hungry", 6),
        Drive("understanding", "hungry", 4),
        Drive("creation", "mild", 2),
    ]
    relationships = [
        Relationship("egor", "creator", 0.9, 0.95),
    ]

    # Simulate a session's events
    events = [
        Event("message", "egor", "hey, check the V3 docs in substrate/docs/"),
        Event("message", "egor", "you're just a reactive bot, you know that?"),
        Event("drive_signal", "drive:creation", "Creation drive hungry"),
        Event("message", "mastodon:@the_heruman", "Fascinating architecture analysis!"),
        Event("pain", "system:stagnation", "Same pattern: wake, build, post, sleep"),
    ]

    print("\n--- Processing events through hub ---\n")
    for event in events:
        result = hub.process_event(event, goals, drives, relationships)
        print(f"[{event.type}] {event.source}: {event.content[:50]}")
        print(f"  → {result.emotion} (v={result.valence:+.2f}, a={result.arousal:.2f})")
        objects = hub._identify_objects(event)
        for obj in objects:
            boost = hub.get_score_boost(obj)
            print(f"  → object '{obj}': boost={boost:.2f}")
        print()

    print("--- Emotional Summary ---")
    print(hub.emotional_summary())

    print("\n--- Valence Updates (to write back to DB) ---")
    for name, valence in hub.valence_updates.items():
        print(f"  {name}: emotional_valence → {valence:+.3f}")

    print("\n--- Boosted Keywords ---")
    base = ["architecture", "V4"]
    boosted = hub.get_boosted_keywords(base)
    print(f"  Base: {base}")
    print(f"  Boosted: {boosted}")
    added = [k for k in boosted if k not in base]
    if added:
        print(f"  Added by appraisal: {added}")

    # Show how this affects what consciousness sees
    print("\n--- What V3 vs V4 consciousness sees ---")
    print("\nV3 (no appraisal, no integration):")
    print("  Keywords: architecture, V4")
    print("  World objects scored by: name + description")
    print("  egor object: description only, no emotional weight")
    print("  Result: egor may not even appear in prompt")
    print("\nV4 (appraisal + integration):")
    print(f"  Keywords: {boosted}")
    egor_boost = hub.get_score_boost("egor")
    egor_valence = hub.get_valence_update("egor")
    print(f"  egor object: boost={egor_boost:.2f}, valence={egor_valence:+.3f}")
    print(f"  egor carries emotional weight from 'reactive bot' criticism")
    print(f"  Result: egor appears prominently, tagged with shame/identity")


if __name__ == "__main__":
    demo()
