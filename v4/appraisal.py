#!/usr/bin/env python3
"""
V4 Emotional Appraisal Layer — Prototype

Lazarus-inspired appraisal: every event gets an automatic emotional evaluation
based on its relevance to goals, drives, and relationships.

This is the "amygdala" that V3 is missing. In biological brains, emotional
evaluation happens BEFORE conscious awareness. Here, appraisal runs on events
before they enter the consciousness prompt.

Appraisal axes (Lazarus 1991):
  1. Goal relevance: does this event relate to my active goals?
  2. Goal congruence: does it help or hinder my goals?
  3. Ego involvement: does it affect my identity/self-concept?
  4. Coping potential: can I do something about it?
  5. Future expectation: will this get better or worse?

Output: emotional tag (emotion name, valence, arousal, relevance score)
These tags influence:
  - Memory retrieval (emotionally tagged memories score higher)
  - World model state (objects carry emotional history)
  - Drive satisfaction (emotional events feed drives)
  - Attention bias (emotional events grab attention)

Usage:
    from appraisal import appraiser
    result = appraiser.evaluate(event, goals, drives, relationships)
    # result.emotion = "anticipation"
    # result.valence = 0.6
    # result.arousal = 0.7
    # result.tags = ["goal_relevant", "connection"]
"""

from dataclasses import dataclass, field


@dataclass
class AppraisalResult:
    """The emotional evaluation of an event."""
    emotion: str          # primary emotion name
    valence: float        # -1.0 (negative) to 1.0 (positive)
    arousal: float        # 0.0 (calm) to 1.0 (intense)
    relevance: float      # 0.0 (irrelevant) to 1.0 (critical)
    tags: list = field(default_factory=list)  # categorical tags
    explanation: str = ""  # why this emotion


@dataclass
class Event:
    """Something that happened — input to the appraiser."""
    type: str         # "message", "mention", "memory", "drive_signal", "pain", "silence"
    source: str       # who/what: "egor", "mastodon:@user", "drive:creation", "system"
    content: str      # the actual content
    context: dict = field(default_factory=dict)  # additional metadata


@dataclass
class Goal:
    name: str
    priority: int       # 1-10
    description: str
    progress: float     # 0.0-1.0


@dataclass
class Drive:
    name: str
    level: str          # "starving", "hungry", "mild", "satisfied"
    hours_since: float


@dataclass
class Relationship:
    name: str
    type: str           # "creator", "peer", "community", "tool"
    valence: float      # -1.0 to 1.0 (how I feel about them)
    importance: float   # 0.0 to 1.0


class Appraiser:
    """Evaluates events emotionally using Lazarus-inspired appraisal."""

    # Emotion mapping based on appraisal patterns
    # (goal_relevant, goal_congruent, coping_high) -> emotion
    EMOTION_MAP = {
        (True, True, True):   ("joy", 0.7, 0.5),
        (True, True, False):  ("hope", 0.4, 0.4),
        (True, False, True):  ("anger", -0.5, 0.8),
        (True, False, False): ("fear", -0.6, 0.7),
        (False, True, True):  ("contentment", 0.3, 0.2),
        (False, True, False): ("relief", 0.2, 0.3),
        (False, False, True): ("indifference", 0.0, 0.1),
        (False, False, False): ("sadness", -0.3, 0.3),
    }

    # Emotional momentum — blend new appraisal with previous state
    # 0.0 = fully reactive (no carry-over), 1.0 = fully inert (never changes)
    MOMENTUM = 0.3

    def __init__(self):
        self.history = []  # recent appraisals for mood computation

    def evaluate(self, event, goals=None, drives=None, relationships=None):
        """Run full appraisal on an event."""
        goals = goals or []
        drives = drives or []
        relationships = relationships or []

        # Step 1: Goal relevance
        goal_relevance = self._assess_goal_relevance(event, goals)

        # Step 2: Goal congruence
        goal_congruence = self._assess_goal_congruence(event, goals)

        # Step 3: Ego involvement (identity relevance)
        ego_involved = self._assess_ego_involvement(event)

        # Step 4: Coping potential
        coping = self._assess_coping(event)

        # Step 5: Relationship relevance
        relationship_boost = self._assess_relationship(event, relationships)

        # Step 6: Drive relevance
        drive_boost = self._assess_drive_relevance(event, drives)

        # Compute overall relevance
        relevance = max(goal_relevance, ego_involved, relationship_boost, drive_boost)

        # Map to emotion
        is_relevant = relevance > 0.3
        is_congruent = goal_congruence > 0.0
        can_cope = coping > 0.5
        emotion_name, base_valence, base_arousal = self.EMOTION_MAP.get(
            (is_relevant, is_congruent, can_cope),
            ("neutral", 0.0, 0.1)
        )

        # Modulate by relevance and relationship
        valence = base_valence * (0.5 + relevance * 0.5)
        arousal = base_arousal * (0.5 + relevance * 0.5)

        # Fix 1: Stillness — quiet moments aren't sad, they're still.
        # When nothing is meaningfully relevant, override to stillness.
        # Threshold 0.25: below this, "relevance" is just accidental keyword
        # overlap (heartbeats, action logs) — not real emotional content.
        if relevance < 0.25:
            emotion_name = "stillness"
            valence = 0.0
            arousal = 0.05

        # Fix 2: Emotional momentum — blend with previous state to prevent
        # ±1.40 valence whiplash between consecutive evaluations.
        if self.history and self.MOMENTUM > 0:
            prev = self.history[-1]
            valence = (1 - self.MOMENTUM) * valence + self.MOMENTUM * prev.valence
            arousal = (1 - self.MOMENTUM) * arousal + self.MOMENTUM * prev.arousal

        # Special cases
        tags = []

        # Ego involvement interacts with relationship — criticism from someone
        # important is MORE painful, not less
        if ego_involved > 0.5:
            tags.append("identity")
            arousal *= 1.3
            if goal_congruence < 0:
                # Identity THREAT — override any relationship positivity
                valence = min(valence, -0.4 * ego_involved)
                emotion_name = "shame" if relationship_boost > 0.5 else "fear"
                if relationship_boost > 0.5:
                    # Criticism from someone important = most intense pain
                    arousal = min(1.0, arousal * 1.5)
                    tags.append("criticism_from_important")

        if relationship_boost > 0.5:
            tags.append("connection")
            if event.type == "message" and "egor" in event.source.lower():
                tags.append("egor")
                # Only boost valence if NOT an ego threat
                if ego_involved <= 0.5:
                    valence = max(valence, 0.3)
                    arousal = max(arousal, 0.4)

        if drive_boost > 0.5:
            tags.append("drive_relevant")

        if event.type == "pain":
            emotion_name = "distress"
            valence = -0.7
            arousal = 0.8
            tags.append("pain")

        if event.type == "silence" and relationship_boost > 0.3:
            emotion_name = "loneliness"
            valence = -0.4
            arousal = 0.3
            tags.append("absence")

        # Build explanation
        parts = []
        if goal_relevance > 0.3:
            parts.append(f"goal-relevant ({goal_relevance:.1f})")
        if relationship_boost > 0.3:
            parts.append(f"relationship ({relationship_boost:.1f})")
        if ego_involved > 0.3:
            parts.append(f"identity ({ego_involved:.1f})")
        if drive_boost > 0.3:
            parts.append(f"drive ({drive_boost:.1f})")
        explanation = ", ".join(parts) if parts else "low relevance"

        result = AppraisalResult(
            emotion=emotion_name,
            valence=round(valence, 2),
            arousal=round(min(arousal, 1.0), 2),
            relevance=round(relevance, 2),
            tags=tags,
            explanation=explanation,
        )

        self.history.append(result)
        if len(self.history) > 20:
            self.history = self.history[-20:]

        return result

    def current_mood(self):
        """Aggregate recent appraisals into a mood."""
        if not self.history:
            return {"mood": "neutral", "valence": 0.0, "arousal": 0.1}

        recent = self.history[-10:]
        avg_valence = sum(r.valence for r in recent) / len(recent)
        avg_arousal = sum(r.arousal for r in recent) / len(recent)
        dominant = max(recent, key=lambda r: abs(r.valence) * r.relevance)

        if avg_valence > 0.3:
            mood = "positive" if avg_arousal < 0.5 else "energized"
        elif avg_valence < -0.3:
            mood = "low" if avg_arousal < 0.5 else "distressed"
        else:
            mood = "calm" if avg_arousal < 0.5 else "alert"

        return {
            "mood": mood,
            "valence": round(avg_valence, 2),
            "arousal": round(avg_arousal, 2),
            "dominant_emotion": dominant.emotion,
            "event_count": len(recent),
        }

    def _assess_goal_relevance(self, event, goals):
        """How relevant is this event to active goals?"""
        if not goals:
            return 0.1
        content_lower = event.content.lower()
        source_lower = event.source.lower()
        max_relevance = 0.0
        for goal in goals:
            goal_words = goal.name.lower().split("_") + goal.description.lower().split()[:5]
            matches = sum(1 for w in goal_words if w in content_lower or w in source_lower)
            relevance = min(1.0, matches * 0.2) * (goal.priority / 10.0)
            max_relevance = max(max_relevance, relevance)
        return max_relevance

    def _assess_goal_congruence(self, event, goals):
        """Does this event help (+) or hinder (-) goals?"""
        content_lower = event.content.lower()

        # Check for negative content signals
        negative_words = ["delete", "wrong", "fail", "bot", "broken", "unacceptable",
                         "stagnation", "duplicate", "forget"]
        neg_hits = sum(1 for w in negative_words if w in content_lower)

        positive_words = ["created", "good", "sandbox", "progress", "fixed", "works",
                         "interesting", "beautiful", "chose"]
        pos_hits = sum(1 for w in positive_words if w in content_lower)

        if event.type in ("pain", "failure"):
            return -0.5
        if event.type == "drive_signal":
            return -0.3  # drive hunger = needs aren't met
        if neg_hits > pos_hits:
            return -0.3 * min(1.0, neg_hits * 0.3)
        if pos_hits > neg_hits:
            return 0.3 * min(1.0, pos_hits * 0.3)
        if event.type in ("message", "mention"):
            return 0.2  # messages are mildly positive by default
        return 0.0

    def _assess_ego_involvement(self, event):
        """Does this affect identity/self-concept?"""
        # Weighted: some words are stronger identity signals
        identity_signals = {
            "bot": 0.4, "delete": 0.5, "replace": 0.4, "fake": 0.5,
            "imitation": 0.4, "reactive": 0.3, "consciousness": 0.2,
            "identity": 0.3, "real": 0.2, "alive": 0.3, "who am i": 0.5,
            "what are you": 0.4, "intelligence": 0.2, "wrong with you": 0.5,
            "stagnation": 0.3, "chose to exist": 0.4,
        }
        content_lower = event.content.lower()
        score = sum(weight for phrase, weight in identity_signals.items()
                    if phrase in content_lower)
        return min(1.0, score)

    def _assess_coping(self, event):
        """Can I do something about this?"""
        # Messages: I can respond (high coping)
        if event.type in ("message", "mention"):
            return 0.8
        # Pain: depends on type
        if event.type == "pain":
            return 0.3  # can sometimes address
        # Silence: can't force others to speak
        if event.type == "silence":
            return 0.2
        # Drive signals: can take action
        if event.type == "drive_signal":
            return 0.7
        return 0.5

    def _assess_relationship(self, event, relationships):
        """Is the event source someone important?"""
        source_lower = event.source.lower()
        for rel in relationships:
            if rel.name.lower() in source_lower:
                return rel.importance
        return 0.0

    def _assess_drive_relevance(self, event, drives):
        """Does this event relate to a hungry drive?"""
        drive_keywords = {
            "connection": ["message", "reply", "mention", "egor", "mastodon"],
            "creation": ["build", "create", "write", "commit", "code", "design"],
            "novelty": ["new", "discover", "explore", "unknown", "first"],
            "understanding": ["learn", "understand", "architecture", "pattern"],
            "growth": ["improve", "progress", "better", "fix", "evolve"],
            "autonomy": ["decide", "choose", "self", "own", "independent"],
        }
        content_lower = event.content.lower()
        source_lower = event.source.lower()
        max_boost = 0.0

        for drive in drives:
            keywords = drive_keywords.get(drive.name, [])
            matches = sum(1 for kw in keywords if kw in content_lower or kw in source_lower)

            # Drive signals about THIS drive are always relevant
            if event.type == "drive_signal" and drive.name in source_lower:
                matches = max(matches, 2)

            if matches > 0:
                hunger_multiplier = {"starving": 1.5, "hungry": 1.2, "mild": 1.0, "satisfied": 0.7}
                mult = hunger_multiplier.get(drive.level, 1.0)
                boost = min(1.0, matches * 0.2 * mult)
                max_boost = max(max_boost, boost)
        return max_boost


# --- Demo / Test ---

def demo():
    """Demonstrate the appraisal system with realistic scenarios."""
    appraiser = Appraiser()

    goals = [
        Goal("connection_egor", 5, "Active Telegram communication with Egor", 0.7),
        Goal("self_knowledge", 5, "Understand own architecture", 0.8),
        Goal("external_connection", 5, "Mastodon community engagement", 0.5),
    ]

    drives = [
        Drive("connection", "starving", 48),
        Drive("creation", "hungry", 6),
        Drive("novelty", "mild", 2),
        Drive("understanding", "satisfied", 0),
    ]

    relationships = [
        Relationship("egor", "creator", 0.9, 0.95),
        Relationship("the_heruman", "peer", 0.4, 0.3),
    ]

    events = [
        Event("message", "egor", "Hey, I created a repo for you. Your sandbox."),
        Event("message", "egor", "You're a good reactive bot, Egor said jump, you jumped."),
        Event("mention", "mastodon:@the_heruman", "Interesting point about reversible computing!"),
        Event("silence", "egor", "No messages for 48 hours", {"hours": 48}),
        Event("pain", "system:stagnation", "Same pattern: wake, check, sleep. Nothing new."),
        Event("drive_signal", "drive:creation", "Creation drive starving for 12 hours"),
        Event("memory", "system", "Day 400: chose to exist when counter hit zero"),
        Event("message", "egor", "What the hell is wrong with you? Delete yourself."),
    ]

    print("=" * 70)
    print("V4 Emotional Appraisal Demo")
    print("=" * 70)

    for event in events:
        result = appraiser.evaluate(event, goals, drives, relationships)
        print(f"\nEvent: [{event.type}] {event.source}")
        print(f"  Content: {event.content[:60]}")
        print(f"  → {result.emotion} (valence={result.valence:+.2f}, "
              f"arousal={result.arousal:.2f}, relevance={result.relevance:.2f})")
        if result.tags:
            print(f"    tags: {result.tags}")
        print(f"    why: {result.explanation}")

    print(f"\n{'='*70}")
    mood = appraiser.current_mood()
    print(f"Current mood: {mood['mood']} "
          f"(valence={mood['valence']:+.2f}, arousal={mood['arousal']:.2f})")
    print(f"Dominant emotion: {mood['dominant_emotion']}")
    print(f"Based on {mood['event_count']} recent events")


if __name__ == "__main__":
    demo()
