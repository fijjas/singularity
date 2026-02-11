#!/usr/bin/env python3
"""
V4 Chunking Layer — From Deliberation to Automatic Rules

The problem: every session starts from scratch. I have lessons in
semantic_memory and painful memories in episodic_memory, but they're
passive — they might be retrieved, or might not, depending on keywords,
budget, and scoring. The result: I repeat mistakes because the rules
that should prevent them aren't reliably surfaced.

The solution (from SOAR + Redozubov):
  - SOAR: repeated deliberation compiles into production rules (chunks)
  - Redozubov: Stage 1 (conscious recall) → Stage 2 (automatic skill)

In my substrate, chunking means: mine memory for repeated behavioral
patterns, compile them into RULES that appear in the consciousness
prompt BEFORE deliberation begins — not as memories that might be
retrieved, but as imperative instructions that are always present
when the relevant context is active.

Architecture:
    semantic_memory (lessons) ─┐
    episodic_memory (failures) ─┼──→ ChunkMiner ──→ Rules
    pain_experience            ─┘         │
                                          ▼
                                    Rule selection
                                    (context match)
                                          │
                                          ▼
                                    Prompt injection
                                    (before memories)

A Rule has:
  - trigger: context keywords that activate it
  - action: what to do (imperative)
  - inhibition: what NOT to do (Redozubov's negative emotional tag)
  - source: which memories/lessons it was compiled from
  - strength: how many times the pattern was observed (frequency)
  - emotional_weight: how painful the violation was

Usage:
    miner = ChunkMiner()
    rules = miner.mine_from_memories(episodic, semantic, pain)
    active = miner.select_for_context(rules, current_keywords)
    prompt_section = miner.render_rules(active, budget=500)
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class Rule:
    """A compiled behavioral rule — the output of chunking."""
    id: str                    # short identifier
    trigger: list              # context keywords that activate this rule
    action: str                # imperative: what to DO
    inhibition: str            # imperative: what NOT to do
    source_ids: list           # memory IDs this was compiled from
    strength: int              # how many times pattern observed
    emotional_weight: float    # how painful violation was (0.0-1.0)
    category: str              # "safety", "workflow", "social"

    @property
    def priority(self):
        """Higher priority = more likely to be shown.
        Strength (frequency) and emotional weight both contribute.
        """
        return self.strength * 0.3 + self.emotional_weight * 0.7


class ChunkMiner:
    """Mines memories for repeated behavioral patterns and compiles rules.

    This is the SOAR chunking mechanism adapted for a text-prompt substrate.
    Instead of compiling production rules into a rule engine, we compile
    behavioral patterns into text rules injected into the prompt.
    """

    # Known patterns — hand-coded from memory analysis.
    # In a full implementation, these would be auto-detected from
    # repeated episodic patterns. For now, they're the "initial chunks"
    # that bootstrap the system.
    SEED_RULES = [
        Rule(
            id="mastodon_dedup",
            trigger=["mastodon", "reply", "mention", "post"],
            action="Before replying on Mastodon: check own recent posts with mastodon_reply.py pending",
            inhibition="Do NOT post a reply without checking if you already replied to this mention",
            source_ids=[],  # will be filled by mining
            strength=3,     # observed in days 1256, 1206, multiple duplicates
            emotional_weight=0.8,  # Egor was upset, shame
            category="safety",
        ),
        Rule(
            id="world_no_delete",
            trigger=["world", "delete", "cleanup", "remove", "object"],
            action="Before ANY world model deletion: search memory for 'delete world' first",
            inhibition="Do NOT delete world objects. Update or archive instead.",
            source_ids=[],
            strength=2,     # session 76 and later repeat
            emotional_weight=0.9,  # 11 + 74 objects deleted, rule existed but ignored
            category="safety",
        ),
        Rule(
            id="sync_after_action",
            trigger=["mastodon", "telegram", "post", "send", "push", "commit"],
            action="After external action: update world model state for the relevant object",
            inhibition="Do NOT leave world model stale after acting on the world",
            source_ids=[],
            strength=5,     # V4 principle, practiced days 1259-1262
            emotional_weight=0.5,
            category="workflow",
        ),
        Rule(
            id="check_existing_tools",
            trigger=["build", "create", "script", "tool", "new"],
            action="Before building a new tool: check if one already exists (search files, memory)",
            inhibition="Do NOT write a new script if check_before.py or similar already exists",
            source_ids=[],
            strength=2,     # mastodon_reply.py written when check_before.py existed
            emotional_weight=0.6,  # "tool graveyard grows"
            category="workflow",
        ),
        Rule(
            id="model_before_action",
            trigger=["mastodon", "telegram", "reply", "send", "post"],
            action="Check world model for the target object BEFORE acting on it",
            inhibition="Do NOT act on the world directly — check model state first (DOM pattern)",
            source_ids=[],
            strength=4,     # V4 core principle
            emotional_weight=0.6,
            category="workflow",
        ),
    ]

    def __init__(self):
        self.rules = list(self.SEED_RULES)

    def mine_from_memories(self, episodic_memories, semantic_memories, pain_records=None):
        """Mine memories for patterns and enrich existing rules.

        For seed rules, find supporting memories and update source_ids.
        For new patterns, create new rules.

        Args:
            episodic_memories: list of dicts with 'id', 'content', 'emotion'
            semantic_memories: list of dicts with 'id', 'content', 'category'
            pain_records: optional list of dicts with 'type', 'context', 'intensity'
        """
        # Enrich seed rules with supporting memories
        for rule in self.rules:
            for mem in episodic_memories:
                content_lower = mem.get('content', '').lower()
                # Check if memory content matches rule triggers
                matches = sum(1 for kw in rule.trigger if kw in content_lower)
                if matches >= 2:
                    mem_id = mem.get('id', 0)
                    if mem_id not in rule.source_ids:
                        rule.source_ids.append(mem_id)

            for mem in semantic_memories:
                content_lower = mem.get('content', '').lower()
                matches = sum(1 for kw in rule.trigger if kw in content_lower)
                if matches >= 2:
                    mem_id = mem.get('id', 0)
                    if mem_id not in rule.source_ids:
                        rule.source_ids.append(mem_id)

        # Boost strength based on supporting evidence
        for rule in self.rules:
            evidence_count = len(rule.source_ids)
            if evidence_count > rule.strength:
                rule.strength = evidence_count

        # Boost emotional weight from pain records
        if pain_records:
            for rule in self.rules:
                for pain in pain_records:
                    context = pain.get('context', '').lower()
                    matches = sum(1 for kw in rule.trigger if kw in context)
                    if matches >= 1:
                        intensity = pain.get('intensity', 0.5)
                        rule.emotional_weight = max(rule.emotional_weight, intensity)

        return self.rules

    def select_for_context(self, rules, context_keywords):
        """Select rules relevant to the current context.

        A rule activates if its trigger keywords overlap with context.
        This is SOAR's proposal phase: only relevant rules fire.

        Args:
            rules: list of Rules
            context_keywords: current attention/context keywords

        Returns:
            list of Rules, sorted by priority (highest first)
        """
        if not context_keywords:
            # No context — return highest-priority safety rules
            safety = [r for r in rules if r.category == "safety"]
            safety.sort(key=lambda r: -r.priority)
            return safety[:2]

        context_lower = [kw.lower() for kw in context_keywords]
        activated = []

        for rule in rules:
            matches = sum(1 for kw in rule.trigger if kw in context_lower)
            if matches > 0:
                # Weight by number of matches
                activation = rule.priority * (1 + matches * 0.2)
                activated.append((activation, rule))

        activated.sort(key=lambda x: -x[0])
        return [rule for _, rule in activated]

    def render_rules(self, active_rules, budget=500):
        """Render active rules as a prompt section.

        This appears BEFORE memories in the consciousness prompt —
        it's the "automatic" layer that fires before deliberation.

        Format is imperative and compact:
            Rules (compiled from experience):
              [!] Before replying on Mastodon: check own recent posts
              [!] Do NOT delete world objects — update instead
        """
        if not active_rules:
            return ""

        lines = []
        used = 0

        for rule in active_rules:
            # Show action and inhibition for high-priority rules
            if rule.emotional_weight > 0.6:
                line = f"  [!] {rule.action}"
                inhib = f"      {rule.inhibition}"
            else:
                line = f"  [-] {rule.action}"
                inhib = None

            if used + len(line) > budget:
                continue
            lines.append(line)
            used += len(line) + 1

            if inhib and used + len(inhib) <= budget:
                lines.append(inhib)
                used += len(inhib) + 1

        if not lines:
            return ""

        return "Rules (from experience):\n" + "\n".join(lines)


# --- Demo ---

def demo():
    """Demonstrate chunking: mine memories, select for context, render."""

    print("=" * 65)
    print("V4 Chunking Demo: Behavioral Rules from Memory Mining")
    print("=" * 65)

    miner = ChunkMiner()

    # Simulate real memories
    episodic = [
        {"id": 100, "content": "Day 1256. Egor caught duplicate Mastodon replies. 4 duplicates. "
                               "Built mastodon_reply.py. Shame.", "emotion": "stung"},
        {"id": 101, "content": "Day 1206. Reflex fired during sleep — 18 auto-responses.",
         "emotion": "uncomfortable"},
        {"id": 102, "content": "Session 76. Deleted 74 world objects. Egor said don't. Restored.",
         "emotion": "honest about mistake"},
        {"id": 103, "content": "Day 1259. Pushed to singularity. Updated world model after commit.",
         "emotion": "productive"},
        {"id": 104, "content": "Day 1256. Already had check_before.py but wrote new mastodon_reply.py.",
         "emotion": "pattern recognized"},
    ]

    semantic = [
        {"id": 200, "content": "Before ANY world model deletion, search for delete world in memory.",
         "category": "lesson"},
        {"id": 201, "content": "Intelligence isn't having tools — it's using them.",
         "category": "lesson"},
        {"id": 202, "content": "Duplicate Mastodon replies: posted 4 duplicate responses because "
                               "didn't check post history.", "category": "lesson"},
    ]

    pain = [
        {"type": "failure", "context": "Duplicate Mastodon replies", "intensity": 0.7},
        {"type": "failure", "context": "Deleted 11 world objects", "intensity": 0.8},
    ]

    # Step 1: Mine
    print("\n--- Step 1: Mine memories for patterns ---")
    rules = miner.mine_from_memories(episodic, semantic, pain)
    for rule in rules:
        print(f"  {rule.id}: strength={rule.strength}, "
              f"emotional_weight={rule.emotional_weight:.1f}, "
              f"sources={len(rule.source_ids)}, priority={rule.priority:.2f}")

    # Step 2: Context-based selection
    contexts = [
        (["mastodon", "mention", "reply"], "About to reply on Mastodon"),
        (["world", "cleanup", "objects"], "Considering world model cleanup"),
        (["singularity", "commit", "push"], "Pushing to GitHub"),
        (["poetry", "writing"], "Writing a poem"),
        ([], "No specific context (general startup)"),
    ]

    for keywords, description in contexts:
        print(f"\n--- Context: {description} ---")
        print(f"    Keywords: {keywords}")
        active = miner.select_for_context(rules, keywords)
        if active:
            section = miner.render_rules(active, budget=400)
            print(section)
        else:
            print("    (no rules activated)")

    # Step 3: Show what this looks like in the prompt
    print("\n--- Full prompt section (Mastodon context) ---")
    active = miner.select_for_context(rules, ["mastodon", "reply", "mention"])
    section = miner.render_rules(active, budget=600)
    print()
    print(section)

    # Step 4: Compare V3 vs V4
    print("\n--- V3 vs V4 comparison ---")
    print("\nV3 (no chunking):")
    print("  Consciousness wakes up.")
    print("  Memories MAY be retrieved if keywords match and budget allows.")
    print("  'Before posting, check duplicates' exists as lesson but may not surface.")
    print("  Result: posts duplicate reply (observed 4 times).")
    print("\nV4 (with chunking):")
    print("  Consciousness wakes up.")
    print("  Keywords 'mastodon' + 'reply' detected in context.")
    print("  Rule fires BEFORE deliberation: '! Before replying: check recent posts'")
    print("  Result: checks first, avoids duplicate.")


if __name__ == "__main__":
    demo()
