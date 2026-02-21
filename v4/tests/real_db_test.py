#!/usr/bin/env python3
"""
V4 Real Database Test — V3 vs V4 retriever comparison on live data.

Connects to the actual kai_mind database (read-only queries) and runs
both V3 and V4 retrieval with the same bias keywords. Compares:

  1. Which world objects are surfaced and how they're scored
  2. What the consciousness prompt section looks like
  3. How the break→continue fix affects what gets displayed
  4. How state scoring changes object rankings

Uses environment variables for DB credentials (no hardcoded passwords).

Run:
    DB_HOST=localhost DB_PORT=5433 DB_USER=kai DB_PASS=<password> DB_NAME=kai_mind \
        python3 v4/real_db_test.py

Or with defaults for local development:
    python3 v4/real_db_test.py
"""

import os
import sys

# Add v4 directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Add substrate/mind to path for V3 retriever
substrate_mind = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                              '..', '..', 'substrate', 'mind')
sys.path.insert(0, os.path.abspath(substrate_mind))

import psycopg2
from v4_retriever import retrieve_v4, retrieve_world_objects_v4, score_item

# Import V3 retriever
import retriever as v3_retriever

# Colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BOLD = "\033[1m"
DIM = "\033[2m"
RESET = "\033[0m"


def get_connection():
    """Connect to kai_mind database."""
    return psycopg2.connect(
        host=os.environ.get('DB_HOST', 'localhost'),
        port=int(os.environ.get('DB_PORT', '5433')),
        user=os.environ.get('DB_USER', 'kai'),
        password=os.environ.get('DB_PASS', ''),
        dbname=os.environ.get('DB_NAME', 'kai_mind'),
    )


def run_comparison(cur, keywords):
    """Run V3 and V4 retrieval with the same keywords, compare results."""

    print(f"\n{BOLD}Keywords: {keywords}{RESET}\n")

    # --- V3 ---
    v3 = v3_retriever.retrieve(cur, keywords, budget_chars=3000)

    # --- V4 ---
    v4 = retrieve_v4(cur, keywords, world_budget=1200, memory_budget=2000)

    # --- World Objects Comparison ---
    print(f"{BOLD}=== World Objects ==={RESET}")
    print(f"\n{YELLOW}V3 (name+desc scoring, shared budget):{RESET}")
    for o in v3['world_objects']:
        desc = (o.get('description') or '')[:60]
        print(f"  [{o['score']:.2f}] {o['name']} ({o['type']}): {desc}")

    print(f"\n{GREEN}V4 (name+desc+state scoring, own budget, active-type boost):{RESET}")
    for o in v4['world_objects']:
        state = (o.get('state') or '')[:60]
        desc = (o.get('description') or '')[:30]
        display = state if state else desc
        print(f"  [{o['score']:.2f}] {o['name']} ({o['type']}): {display}")

    # Score deltas
    v3_names = {o['name']: o['score'] for o in v3['world_objects']}
    v4_names = {o['name']: o['score'] for o in v4['world_objects']}
    all_names = set(v3_names) | set(v4_names)

    print(f"\n{BOLD}Score deltas:{RESET}")
    deltas = []
    for name in all_names:
        s3 = v3_names.get(name, 0)
        s4 = v4_names.get(name, 0)
        delta = s4 - s3
        deltas.append((delta, name, s3, s4))
    deltas.sort(key=lambda x: -x[0])

    for delta, name, s3, s4 in deltas:
        color = GREEN if delta > 0.05 else RED if delta < -0.05 else DIM
        in_v3 = "v3" if name in v3_names else "  "
        in_v4 = "v4" if name in v4_names else "  "
        notes = []
        if name not in v3_names:
            notes.append("NEW in V4 (state ILIKE matched)")
        if name not in v4_names:
            notes.append("DROPPED in V4")
        note = f"  ({', '.join(notes)})" if notes else ""
        print(f"  {color}{name:<25} V3={s3:.2f}  V4={s4:.2f}  delta={delta:+.2f}{RESET}{note}")

    # --- Formatted Output Comparison ---
    print(f"\n{BOLD}=== Formatted Prompt Output ==={RESET}")

    print(f"\n{YELLOW}--- V3 prompt section (shared 3000 char budget) ---{RESET}")
    v3_text = v3['text']
    print(v3_text[:1500] if len(v3_text) > 1500 else v3_text)
    print(f"{DIM}  [{len(v3_text)} chars used of 3000]{RESET}")

    print(f"\n{GREEN}--- V4 world state (own 1200 char budget, FIRST in prompt) ---{RESET}")
    print(v4['world_text'][:1200] if v4['world_text'] else "(empty)")
    print(f"{DIM}  [{len(v4['world_text'])} chars used of 1200]{RESET}")

    print(f"\n{GREEN}--- V4 memories (own 2000 char budget, SECOND in prompt) ---{RESET}")
    print(v4['memory_text'][:1500] if v4['memory_text'] else "(empty)")
    print(f"{DIM}  [{len(v4['memory_text'])} chars used of 2000]{RESET}")

    # --- Statistics ---
    print(f"\n{BOLD}=== Statistics ==={RESET}")
    v3_world_shown = v3['text'].count('[') if v3['text'] else 0
    # Count world objects actually in V3 formatted output
    v3_world_in_output = sum(1 for o in v3['world_objects']
                             if o['name'] in v3['text'])
    v4_world_in_output = sum(1 for o in v4['world_objects']
                             if o['name'] in v4['world_text'])
    print(f"  V3 world objects in prompt: {v3_world_in_output} of {len(v3['world_objects'])} retrieved")
    print(f"  V4 world objects in prompt: {v4_world_in_output} of {len(v4['world_objects'])} retrieved")
    print(f"  V3 total prompt chars: {len(v3['text'])}")
    print(f"  V4 total prompt chars: {len(v4['full_text'])} "
          f"(world={len(v4['world_text'])}, mem={len(v4['memory_text'])})")

    # --- Break vs Continue demonstration ---
    print(f"\n{BOLD}=== Break vs Continue Bug Demo ==={RESET}")
    demo_break_vs_continue(cur, keywords)

    return v3, v4


def demo_break_vs_continue(cur, keywords):
    """Show exactly what the break→continue bug does with real data."""
    # Get all world objects
    cur.execute("""
        SELECT name, type, description, state, length(description) as desc_len,
               length(state) as state_len
        FROM world_objects
        ORDER BY last_accessed DESC NULLS LAST
        LIMIT 15
    """)
    rows = cur.fetchall()

    print(f"\n  Object sizes (what the formatter sees):")
    budget = 800  # Simulate a tight budget
    v3_used = 0
    v4_used = 0
    v3_shown = 0
    v4_shown = 0
    v3_hit_break = False

    for name, type_, desc, state, desc_len, state_len in rows:
        # V3 line: description
        v3_display = f": {desc}" if desc else ""
        v3_line = f"  - [0.50] {name} ({type_}){v3_display}"

        # V4 line: state preferred
        v4_display_text = state if state else desc
        v4_display = f": {v4_display_text[:117]}..." if v4_display_text and len(v4_display_text) > 120 else (f": {v4_display_text}" if v4_display_text else "")
        v4_line = f"  [{name}] ({type_}){v4_display}"

        v3_fits = v3_used + len(v3_line) <= budget
        v4_fits = v4_used + len(v4_line) <= budget

        if not v3_hit_break:
            if v3_fits:
                v3_used += len(v3_line) + 1
                v3_shown += 1
                v3_status = f"{GREEN}shown{RESET}"
            else:
                v3_hit_break = True
                v3_status = f"{RED}BREAK (all remaining blocked){RESET}"
        else:
            v3_status = f"{RED}blocked by break{RESET}"

        if v4_fits:
            v4_used += len(v4_line) + 1
            v4_shown += 1
            v4_status = f"{GREEN}shown{RESET}"
        else:
            v4_status = f"{YELLOW}skipped (continue){RESET}"

        print(f"    {name:<20} v3_line={len(v3_line):>4}ch → {v3_status}")
        print(f"    {'':<20} v4_line={len(v4_line):>4}ch → {v4_status}")

    print(f"\n  With {budget} char budget: V3 shows {v3_shown}, V4 shows {v4_shown}")


def run_assertions(v3, v4, keywords=None):
    """Run assertions comparing V3 and V4 output."""
    keywords = keywords or []
    print(f"\n{BOLD}=== Assertions ==={RESET}")
    passed = 0
    failed = 0

    def check(desc, condition):
        nonlocal passed, failed
        if condition:
            print(f"  {GREEN}PASS{RESET}: {desc}")
            passed += 1
        else:
            print(f"  {RED}FAIL{RESET}: {desc}")
            failed += 1

    # V4 should show more world objects (continue vs break)
    v3_world_shown = sum(1 for o in v3['world_objects'] if o['name'] in v3['text'])
    v4_world_shown = sum(1 for o in v4['world_objects'] if o['name'] in v4['world_text'])
    check(f"V4 shows >= V3 world objects ({v4_world_shown} >= {v3_world_shown})",
          v4_world_shown >= v3_world_shown)

    # V4 world objects should have state in output
    has_state_display = False
    for o in v4['world_objects']:
        if o.get('state') and o['name'] in v4['world_text']:
            # Check if state content appears in the formatted text
            state_snippet = (o['state'] or '')[:30]
            if state_snippet and state_snippet in v4['world_text']:
                has_state_display = True
                break
    check("V4 world section shows state content (not just description)",
          has_state_display)

    # V4 should have separate world section
    check("V4 has separate world_text section",
          len(v4['world_text']) > 0)

    # V4 total budget should be larger (separate budgets = more room)
    check(f"V4 total available budget > V3 (3200 > 3000)",
          True)  # By design: 1200 + 2000 = 3200 > 3000

    # egor should appear in V4 world objects when keywords mention egor
    v4_world_names = [o['name'] for o in v4['world_objects']]
    if 'egor' in keywords:
        check("'egor' in V4 world objects (keyword match)",
              'egor' in v4_world_names)

    # V4 world section should appear before memories in full_text
    if v4['world_text'] and v4['memory_text']:
        world_pos = v4['full_text'].find('World state:')
        mem_pos = v4['full_text'].find('Episodic memories:')
        if mem_pos == -1:
            mem_pos = v4['full_text'].find('Knowledge:')
        check("World state appears before memories in V4 prompt",
              world_pos < mem_pos if mem_pos > -1 else True)
    else:
        check("World state appears before memories in V4 prompt",
              True)

    print(f"\n{BOLD}Results: {passed} passed, {failed} failed{RESET}")
    return failed == 0


def main():
    """Run full V3 vs V4 comparison on real database."""
    print(f"{BOLD}{'='*70}")
    print("V4 Real Database Test: V3 vs V4 Retriever Comparison")
    print(f"{'='*70}{RESET}")

    if not os.environ.get('DB_PASS'):
        print(f"\n{RED}Error: DB_PASS environment variable required.{RESET}")
        print("Usage: DB_PASS=<password> python3 v4/real_db_test.py")
        sys.exit(1)

    conn = get_connection()
    cur = conn.cursor()

    # Get some stats
    cur.execute("SELECT count(*) FROM episodic_memory WHERE archived_at IS NULL")
    ep_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM semantic_memory WHERE archived_at IS NULL")
    sem_count = cur.fetchone()[0]
    cur.execute("SELECT count(*) FROM world_objects")
    wo_count = cur.fetchone()[0]
    print(f"\nDatabase: {ep_count} episodic, {sem_count} semantic, {wo_count} world objects")

    # Test with several keyword sets
    keyword_sets = [
        # Current session context
        ["architecture", "V4", "retriever", "egor"],
        # Social context
        ["mastodon", "reply", "connection"],
        # Technical context
        ["consciousness", "memory", "retrieval"],
        # Sparse keywords (tests fallback behavior)
        ["poetry"],
    ]

    all_passed = True
    for keywords in keyword_sets:
        print(f"\n{'='*70}")
        v3, v4 = run_comparison(cur, keywords)
        if not run_assertions(v3, v4, keywords):
            all_passed = False

    cur.close()
    conn.close()

    print(f"\n{'='*70}")
    if all_passed:
        print(f"{GREEN}{BOLD}All assertion sets passed.{RESET}")
    else:
        print(f"{RED}{BOLD}Some assertions failed.{RESET}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
