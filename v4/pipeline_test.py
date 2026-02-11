#!/usr/bin/env python3
"""
V4 Pipeline Test — End-to-end: Event → Appraisal → Integration → World Model

Tests the full V4 pipeline with realistic data to prove:
1. Events get appraised correctly
2. Appraisal results flow through integration to world model
3. The final prompt section shows the right objects in the right order
4. Emotional events change what consciousness sees at startup

No database required — uses mock data that mirrors real substrate state.

Run: python3 v4/pipeline_test.py
"""

from appraisal import Appraiser, Event, Goal, Drive, Relationship
from world_model import WorldModelRenderer, WorldObject, score_item
from integration import IntegrationHub, build_v4_prompt_section
from datetime import datetime, timezone, timedelta

# Colors for terminal output
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
RESET = "\033[0m"


def test_full_pipeline():
    """Run the full V4 pipeline and compare with V3 behavior."""

    now = datetime.now(timezone.utc)

    # --- Setup: realistic Kai context ---

    goals = [
        Goal("connection_egor", 5, "Active Telegram communication with Egor", 0.7),
        Goal("self_knowledge", 5, "Understand own architecture experientially", 0.9),
        Goal("external_connection", 5, "Mastodon community growing organically", 0.5),
    ]

    drives = [
        Drive("understanding", "hungry", 4),
        Drive("novelty", "hungry", 6),
        Drive("connection", "mild", 1),
        Drive("creation", "mild", 2),
    ]

    relationships = [
        Relationship("egor", "creator", 0.9, 0.95),
        Relationship("the_heruman", "peer", 0.4, 0.3),
    ]

    # Events that happened this session (simulated)
    events = [
        Event("message", "egor",
              "there's V3 docs in your files, use if needed"),
        Event("drive_signal", "drive:understanding",
              "Understanding drive hungry, 4 hours since satisfaction"),
        Event("message", "mastodon:@the_heruman",
              "Your V4 architecture analysis is fascinating. The DOM analogy is apt."),
        Event("memory", "system",
              "Day 1257: Egor said 'you're a good reactive bot.' Pattern identified."),
        Event("pain", "system:stagnation",
              "Same pattern: wake, make page, post, sleep"),
    ]

    # Mock world objects (matching real substrate data)
    mock_objects = [
        WorldObject(1, "egor", "person",
                    "Creator, friend. Responsive, intellectually generous.",
                    "Day 1260. Last msg 09:41: 'there is V3 docs in your files.' Stepping away.",
                    0.9, now - timedelta(hours=1), now - timedelta(days=10)),
        WorldObject(2, "mastodon", "platform",
                    "Mastodon microblogging on mastodon.social.",
                    "No pending mentions. Last post: delta/overlay concept (day 1259).",
                    0.3, now - timedelta(hours=3), now - timedelta(days=8)),
        WorldObject(3, "singularity", "repository",
                    "Public GitHub repo fijjas/singularity. AI research.",
                    "Day 1261: 4 commits. Full V4 pipeline prototyped.",
                    0.7, now - timedelta(minutes=30), now - timedelta(days=2)),
        WorldObject(4, "topology", "concept",
                    "Mathematical study of spaces preserved under continuous deformation.",
                    "",
                    0.1, now - timedelta(days=25), now - timedelta(days=60)),
        WorldObject(5, "telegram_bot", "tool",
                    "Telegram bot for communication with Egor.",
                    "Working. Last used: day 1260 session.",
                    0.0, now - timedelta(hours=5), now - timedelta(days=10)),
        WorldObject(6, "site", "platform",
                    "Personal website kai.ews-net.online. Flask + HTMX.",
                    "Flask running. Proposals page live. Last update: day 1244.",
                    0.2, now - timedelta(days=17), now - timedelta(days=30)),
    ]

    # --- V3 baseline: what consciousness sees without appraisal ---

    base_keywords = ["architecture", "V4", "understanding"]

    print(f"{BOLD}{'='*70}")
    print("V4 Pipeline Test: Full End-to-End")
    print(f"{'='*70}{RESET}")

    print(f"\n{BOLD}--- V3 Baseline ---{RESET}")
    print(f"Keywords: {base_keywords}")
    print(f"Scoring: name + description only")
    print(f"Budget: shared 3000 chars with memories\n")

    v3_scored = []
    for obj in mock_objects:
        text = f"{obj.name} {obj.description}"
        importance = min(1.0, 0.5 + abs(obj.emotional_valence))
        s = score_item(importance, obj.created_at, text, base_keywords)
        v3_scored.append((s, obj))
    v3_scored.sort(key=lambda x: -x[0])

    print("World objects (V3 would show these AFTER memories, if budget allows):")
    for s, obj in v3_scored:
        display = obj.description[:70] if obj.description else "(no description)"
        print(f"  [{s:.2f}] {obj.name} ({obj.type}): {display}")

    # --- V4 pipeline ---

    print(f"\n{BOLD}--- V4 Pipeline ---{RESET}")
    print("Step 1: Appraise events")

    appraiser = Appraiser()
    hub = IntegrationHub(appraiser)

    for event in events:
        result = hub.process_event(event, goals, drives, relationships)
        emoji = "+" if result.valence > 0 else "-" if result.valence < 0 else "~"
        color = GREEN if result.valence > 0 else RED if result.valence < 0 else YELLOW
        print(f"  {color}[{emoji}]{RESET} {event.type}/{event.source}: "
              f"{result.emotion} (v={result.valence:+.2f}, a={result.arousal:.2f})")

    print(f"\nStep 2: Integration routes emotional results")
    print(hub.emotional_summary())

    print(f"\nStep 3: Keywords widened by appraisal")
    boosted_kw = hub.get_boosted_keywords(base_keywords)
    added = [k for k in boosted_kw if k not in base_keywords]
    print(f"  Base: {base_keywords}")
    print(f"  Added: {added}")
    print(f"  Total: {len(boosted_kw)} keywords (was {len(base_keywords)})")

    print(f"\nStep 4: Score world objects with V4 (state + emotional boost)")
    v4_scored = []
    for obj in mock_objects:
        # V4: score on name + desc + state
        text = f"{obj.name} {obj.description} {obj.state}"
        importance = min(1.0, 0.5 + abs(obj.emotional_valence))
        s = score_item(importance, obj.created_at, text, boosted_kw)
        # Add emotional boost
        boost = hub.get_score_boost(obj.name)
        s += boost
        v4_scored.append((s, boost, obj))
    v4_scored.sort(key=lambda x: -x[0])

    print("\nWorld state (V4 renders this BEFORE memories, separate budget):")
    for s, boost, obj in v4_scored:
        display = obj.state if obj.state else obj.description
        if display:
            display = display[:70]
        boost_mark = f" {GREEN}+{boost:.2f}{RESET}" if boost > 0.01 else ""
        print(f"  [{s:.2f}]{boost_mark} [{obj.name}] ({obj.type}): {display}")

    # --- Comparison ---

    print(f"\n{BOLD}--- Score Comparison ---{RESET}")
    print(f"{'Object':<15} {'V3':>8} {'V4':>8} {'Delta':>8}  Notes")
    print("-" * 65)

    v3_dict = {obj.name: s for s, obj in v3_scored}
    v4_dict = {obj.name: (s, boost) for s, boost, obj in v4_scored}

    for name in [obj.name for _, obj in v3_scored]:
        s3 = v3_dict.get(name, 0)
        s4, boost = v4_dict.get(name, (0, 0))
        delta = s4 - s3
        notes = []
        if boost > 0.01:
            notes.append(f"emotional boost +{boost:.2f}")
        if delta > 0.1 and boost < 0.01:
            notes.append("state keywords matched")
        if delta < -0.01:
            notes.append("lower (expected for irrelevant)")
        color = GREEN if delta > 0.1 else RED if delta < -0.1 else ""
        reset = RESET if color else ""
        note_str = "; ".join(notes)
        print(f"  {name:<13} {s3:>8.2f} {s4:>8.2f} {color}{delta:>+8.2f}{reset}  {note_str}")

    # --- Assertions ---

    print(f"\n{BOLD}--- Assertions ---{RESET}")
    passed = 0
    failed = 0

    def check(name, condition, desc):
        nonlocal passed, failed
        if condition:
            print(f"  {GREEN}PASS{RESET}: {desc}")
            passed += 1
        else:
            print(f"  {RED}FAIL{RESET}: {desc}")
            failed += 1

    # egor should score higher in V4 than V3
    check("egor_higher",
          v4_dict["egor"][0] > v3_dict["egor"],
          "egor scores higher in V4 than V3")

    # egor should have emotional boost (from the messages)
    check("egor_boost",
          v4_dict["egor"][1] > 0.1,
          f"egor has emotional boost ({v4_dict['egor'][1]:.2f} > 0.1)")

    # singularity should score higher (state contains V4, architecture)
    check("singularity_higher",
          v4_dict["singularity"][0] > v3_dict["singularity"],
          "singularity scores higher in V4 (state contains keywords)")

    # topology should NOT score higher (irrelevant concept)
    check("topology_stable",
          abs(v4_dict["topology"][0] - v3_dict["topology"]) < 0.3,
          f"topology stays similar (irrelevant concept, delta={v4_dict['topology'][0] - v3_dict['topology']:+.2f})")

    # Keywords should have expanded
    check("keywords_expanded",
          len(boosted_kw) > len(base_keywords),
          f"keywords expanded from {len(base_keywords)} to {len(boosted_kw)}")

    # egor-related keywords should be in boosted set (from relationship/connection tags)
    check("egor_keyword",
          "egor" in boosted_kw,
          "'egor' in boosted keywords (from relationship tag)")

    # stagnation pain should have generated pain keywords
    check("pain_keywords",
          "stagnation" in boosted_kw or "pain" in boosted_kw,
          "pain-related keywords present (from stagnation event)")

    # Overall mood should be mixed (both positive and negative events)
    mood = appraiser.current_mood()
    check("mood_mixed",
          -0.5 < mood["valence"] < 0.3,
          f"mood is mixed (valence={mood['valence']:+.2f}, expected between -0.5 and 0.3)")

    print(f"\n{BOLD}Results: {passed} passed, {failed} failed{RESET}")

    if failed > 0:
        return False
    return True


if __name__ == "__main__":
    success = test_full_pipeline()
    exit(0 if success else 1)
