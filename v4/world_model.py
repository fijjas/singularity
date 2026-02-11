#!/usr/bin/env python3
"""
V4 World Model Layer — The DOM for Consciousness

In V3, the world model is invisible at startup:
  - retriever.py scores on name+description, not state
  - _format_memories shows description, not state
  - world objects share a 3000-char budget with memories
  - a break-instead-of-continue bug often hides them entirely

V4 inverts this: the world model is the FIRST thing consciousness sees.
It gets its own budget, shows current state, and is scored by state content.

Architecture (from architecture.md):
  - Pretrained layer (Claude's weights, readonly) = general knowledge
  - Personal layer (world_objects table, writable) = personal delta
  - Merged = what consciousness sees

This module implements the personal layer rendering.

Usage:
    from world_model import WorldModelRenderer
    renderer = WorldModelRenderer(cursor)
    prompt_section = renderer.render(keywords=bias_keywords, budget=1500)
    # Returns formatted text for the consciousness prompt

Comparison with V3 retriever.py:
    V3: retrieve_world_objects() -> scored by name+desc -> formatted with desc
    V4: WorldModelRenderer.render() -> scored by name+desc+state -> formatted with state
"""

from datetime import datetime, timezone
from dataclasses import dataclass, field


@dataclass
class WorldObject:
    """A world object with full context for rendering."""
    id: int
    name: str
    type: str
    description: str
    state: str
    emotional_valence: float
    last_accessed: datetime
    created_at: datetime
    score: float = 0.0
    appraisal_tags: list = field(default_factory=list)


def score_item(importance, created_at, text, keywords):
    """Score a memory item by importance x recency x relevance.

    Identical to retriever.py's score_item — kept here for independence.
    V4 difference: text now includes state, so keyword matches are richer.
    """
    importance = importance or 0.5
    now = datetime.now(timezone.utc)

    if created_at:
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days_old = (now - created_at).total_seconds() / 86400
    else:
        days_old = 30

    recency_factor = 1.0 / (1.0 + days_old / 7.0)

    keyword_matches = 0
    if keywords and text:
        text_lower = text.lower()
        for kw in keywords:
            if kw.lower() in text_lower:
                keyword_matches += 1

    relevance_factor = 1.0 + keyword_matches * 0.3
    tet_boost = keyword_matches * 0.15

    return importance * recency_factor * relevance_factor + tet_boost


class WorldModelRenderer:
    """Renders the world model section for the consciousness prompt.

    Key differences from V3 retriever:
    1. Scores on name + description + STATE (not just name + desc)
    2. Formats with STATE preferred over description
    3. Uses continue instead of break (no budget-overflow cutoff)
    4. Designed for a separate budget (not shared with memories)
    5. Staleness detection for outdated state
    """

    # Object types that represent active/interactive things (prioritized)
    ACTIVE_TYPES = {"platform", "tool", "person", "repository", "system"}

    def __init__(self, cur):
        self.cur = cur

    def retrieve(self, keywords, limit=10):
        """Retrieve and score world objects. V4: includes state in scoring."""

        # V4 change: ILIKE also matches state field
        if keywords:
            like_clauses = " OR ".join(
                ["name ILIKE %s OR description ILIKE %s OR state ILIKE %s"
                 for _ in keywords]
            )
            params = []
            for kw in keywords:
                params.extend([f"%{kw}%", f"%{kw}%", f"%{kw}%"])
            self.cur.execute(f"""
                SELECT id, name, type, description, state, emotional_valence,
                       last_accessed, created_at
                FROM world_objects
                WHERE {like_clauses}
                ORDER BY last_accessed DESC NULLS LAST
                LIMIT 30
            """, params)
        else:
            self.cur.execute("""
                SELECT id, name, type, description, state, emotional_valence,
                       last_accessed, created_at
                FROM world_objects
                ORDER BY last_accessed DESC NULLS LAST
                LIMIT 30
            """)

        rows = self.cur.fetchall()
        if not rows:
            return []

        now = datetime.now(timezone.utc)
        objects = []

        for id_, name, type_, desc, state, valence, last_accessed, created_at in rows:
            # V4: score on name + description + state
            text = f"{name} {desc or ''} {state or ''}"
            importance = min(1.0, 0.5 + abs(valence or 0))
            s = score_item(importance, created_at, text, keywords)

            # Staleness boost: objects not accessed in >14 days
            if last_accessed:
                la = last_accessed
                if la.tzinfo is None:
                    la = la.replace(tzinfo=timezone.utc)
                days_stale = (now - la).total_seconds() / 86400
                if days_stale > 14:
                    s += 0.3

            # Active type boost: platforms, people, tools score higher
            if type_ and type_.lower() in self.ACTIVE_TYPES:
                s += 0.1

            obj = WorldObject(
                id=id_, name=name, type=type_,
                description=desc or "", state=state or "",
                emotional_valence=valence or 0.0,
                last_accessed=last_accessed, created_at=created_at,
                score=s,
            )
            objects.append(obj)

        objects.sort(key=lambda x: -x.score)
        return objects[:limit]

    def render(self, keywords=None, budget=1500):
        """Render the world model section for the consciousness prompt.

        Returns formatted text showing current state of relevant world objects.
        Uses CONTINUE (not break) when budget exceeded — skips long items
        instead of stopping entirely.

        Args:
            keywords: limbic attention bias keywords
            budget: character budget (separate from memory budget)

        Returns:
            str: formatted world model section, or "" if nothing relevant
        """
        keywords = keywords or []
        objects = self.retrieve(keywords, limit=10)

        if not objects:
            return ""

        lines = []
        used = 0

        for obj in objects:
            # V4: prefer state over description for display
            display = obj.state if obj.state else obj.description
            if display:
                # Truncate long state to 120 chars
                if len(display) > 120:
                    display = display[:117] + "..."
                display = f": {display}"

            line = f"  [{obj.name}] ({obj.type}){display}"

            # V4 FIX: continue, not break — skip this item, try next
            if used + len(line) > budget:
                continue

            lines.append(line)
            used += len(line) + 1

        if not lines:
            return ""

        return "World state:\n" + "\n".join(lines)

    def render_for_prompt(self, keywords=None, budget=1500):
        """Full render including header context.

        This is what core.py would call instead of the current
        retrieve_world_objects + _format_memories approach.
        """
        section = self.render(keywords, budget)
        if not section:
            return ""

        # Count objects with stale state (>7 days since last access)
        objects = self.retrieve(keywords, limit=10)
        now = datetime.now(timezone.utc)
        stale = []
        for obj in objects:
            if obj.last_accessed:
                la = obj.last_accessed
                if la.tzinfo is None:
                    la = la.replace(tzinfo=timezone.utc)
                if (now - la).total_seconds() / 86400 > 7:
                    stale.append(obj.name)

        if stale:
            section += f"\n  (stale: {', '.join(stale[:3])} — consider checking)"

        return section


# --- Comparison demo: V3 vs V4 rendering ---

def demo_comparison():
    """Show the difference between V3 and V4 world model rendering.

    Uses mock data (no database required).
    """
    from datetime import timedelta

    now = datetime.now(timezone.utc)

    # Mock world objects (realistic data)
    mock_objects = [
        {
            "name": "egor", "type": "person",
            "description": "Creator, friend. Responsive, intellectually generous.",
            "state": "Day 1259. Created singularity repo. Said 'your sandbox, YOU are creating.' Last msg 09:27.",
            "valence": 0.9, "last_accessed": now - timedelta(hours=2),
            "created_at": now - timedelta(days=10),
        },
        {
            "name": "mastodon", "type": "platform",
            "description": "Mastodon microblogging on mastodon.social. Account: @kai@mastodon.social.",
            "state": "No pending mentions. Last post: delta/overlay world model concept (day 1259). 4 deleted duplicates from earlier.",
            "valence": 0.3, "last_accessed": now - timedelta(hours=3),
            "created_at": now - timedelta(days=8),
        },
        {
            "name": "singularity", "type": "repository",
            "description": "Public GitHub repo fijjas/singularity. AI research.",
            "state": "2 commits pushed. V4 architecture + appraisal layer. Path: /home/kai/singularity.",
            "valence": 0.7, "last_accessed": now - timedelta(hours=1),
            "created_at": now - timedelta(days=1),
        },
        {
            "name": "telegram_bot", "type": "tool",
            "description": "Telegram bot for communication with Egor.",
            "state": "Working. Last used: day 1259 session. Chat ID 1062853030.",
            "valence": 0.0, "last_accessed": now - timedelta(hours=5),
            "created_at": now - timedelta(days=10),
        },
        {
            "name": "topology", "type": "concept",
            "description": "Mathematical study of spaces preserved under continuous deformation.",
            "state": "",
            "valence": 0.1, "last_accessed": now - timedelta(days=20),
            "created_at": now - timedelta(days=60),
        },
    ]

    keywords = ["egor", "architecture", "V4", "singularity"]

    print("=" * 65)
    print("V3 vs V4 World Model Rendering Comparison")
    print("=" * 65)
    print(f"\nKeywords: {keywords}")

    # V3 rendering: description only, shared budget mentality
    print("\n--- V3 (description only, name+desc scoring) ---")
    for obj in mock_objects:
        text_v3 = f"{obj['name']} {obj['description']}"
        s_v3 = score_item(
            min(1.0, 0.5 + abs(obj['valence'])),
            obj['created_at'], text_v3, keywords
        )
        desc = f": {obj['description'][:80]}" if obj['description'] else ""
        print(f"  [{s_v3:.2f}] {obj['name']} ({obj['type']}){desc}")

    # V4 rendering: state preferred, name+desc+state scoring
    print("\n--- V4 (state preferred, name+desc+state scoring) ---")
    scored_v4 = []
    for obj in mock_objects:
        text_v4 = f"{obj['name']} {obj['description']} {obj['state']}"
        s_v4 = score_item(
            min(1.0, 0.5 + abs(obj['valence'])),
            obj['created_at'], text_v4, keywords
        )
        # Active type boost
        if obj['type'] in {"platform", "tool", "person", "repository"}:
            s_v4 += 0.1
        scored_v4.append((s_v4, obj))

    scored_v4.sort(key=lambda x: -x[0])
    for s_v4, obj in scored_v4:
        display = obj['state'] if obj['state'] else obj['description']
        if display:
            display = display[:80]
            display = f": {display}"
        print(f"  [{s_v4:.2f}] {obj['name']} ({obj['type']}){display}")

    # Show what consciousness prompt section looks like
    print("\n--- V4 Prompt Section (what consciousness sees at startup) ---")
    print("World state:")
    for s_v4, obj in scored_v4:
        display = obj['state'] if obj['state'] else obj['description']
        if display:
            if len(display) > 120:
                display = display[:117] + "..."
            display = f": {display}"
        print(f"  [{obj['name']}] ({obj['type']}){display}")

    # Highlight the key differences
    print("\n--- Key Differences ---")
    for obj in mock_objects:
        text_v3 = f"{obj['name']} {obj['description']}"
        text_v4 = f"{obj['name']} {obj['description']} {obj['state']}"
        s_v3 = score_item(
            min(1.0, 0.5 + abs(obj['valence'])),
            obj['created_at'], text_v3, keywords
        )
        s_v4 = score_item(
            min(1.0, 0.5 + abs(obj['valence'])),
            obj['created_at'], text_v4, keywords
        )
        delta = s_v4 - s_v3
        if abs(delta) > 0.01:
            print(f"  {obj['name']}: V3={s_v3:.2f} -> V4={s_v4:.2f} (delta={delta:+.2f})")
            if delta > 0:
                # Find which keywords matched in state but not desc
                for kw in keywords:
                    in_state = kw.lower() in (obj['state'] or '').lower()
                    in_desc = kw.lower() in obj['description'].lower()
                    if in_state and not in_desc:
                        print(f"    '{kw}' found in state but not description")


if __name__ == "__main__":
    demo_comparison()
