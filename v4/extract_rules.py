#!/usr/bin/env python3
"""
Experiment: Extract processing rules from episodic memories.

Hypothesis: Episodes containing lessons, failures, and corrections
contain implicit processing rules that can be formulated as
IF-THEN instructions.

Day 1373, session 271.
"""

import psycopg2
import re
import json
from datetime import datetime

DB_CONFIG = {
    'host': 'localhost',
    'port': 5433,
    'user': 'kai',
    'password': 'bys2kCtE0DQqRsoEYsSZBtelYS5wFAhGVm7drGxd',
    'dbname': 'kai_mind'
}

# Patterns that indicate a processing rule is embedded in the episode
RULE_INDICATORS = [
    # Explicit rules
    (r'(?:need|should|must|always|never)[:\s]+(.{20,150})', 'explicit'),
    # Lessons learned
    (r'(?:lesson|learned|takeaway)[:\s]+(.{20,150})', 'lesson'),
    # Failure + correction
    (r'\[failure\]\s*(.{20,200})', 'failure'),
    # Before/after patterns
    (r'before\s+(?:any|every|each|all)\s+(.{15,100})', 'precondition'),
    # Don't/never patterns
    (r"(?:don'?t|never|avoid)\s+(.{10,100})", 'prohibition'),
    # Fixed/changed behavior
    (r'(?:fixed|changed|now I|from now)\s+(.{15,100})', 'correction'),
]


def connect():
    return psycopg2.connect(**DB_CONFIG)


def fetch_candidate_episodes(conn, min_importance=0.6):
    """Fetch episodes likely to contain processing rules."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, content, importance, emotion, created_at
        FROM episodic_memory
        WHERE importance >= %s
          AND (content ILIKE '%%lesson%%'
               OR content ILIKE '%%learned%%'
               OR content ILIKE '%%mistake%%'
               OR content ILIKE '%%never%%'
               OR content ILIKE '%%always%%'
               OR content ILIKE '%%should%%'
               OR content ILIKE '%%don''t%%'
               OR content ILIKE '%%need:%%'
               OR content ILIKE '%%rule%%'
               OR content ILIKE '%%[failure]%%'
               OR content ILIKE '%%before any%%'
               OR content ILIKE '%%fixed%%')
        ORDER BY importance DESC
    """, (min_importance,))
    return cur.fetchall()


def extract_rules_from_episode(episode_id, content, importance, emotion):
    """Try to extract processing rules from episode content."""
    rules = []

    for pattern, rule_type in RULE_INDICATORS:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            match = match.strip().rstrip('.')
            if len(match) < 15:
                continue
            # Skip if it's just narrative, not a rule
            if any(w in match.lower() for w in ['he said', 'she said', 'egor said', 'the book']):
                continue
            rules.append({
                'source_episode_id': episode_id,
                'rule_text': match,
                'rule_type': rule_type,
                'confidence': min(importance, 0.9),  # cap at 0.9 for auto-extracted
                'source_emotion': emotion,
            })

    return rules


def deduplicate_rules(rules):
    """Remove near-duplicate rules by comparing first 50 chars."""
    seen = set()
    unique = []
    for r in rules:
        key = r['rule_text'][:50].lower()
        if key not in seen:
            seen.add(key)
            unique.append(r)
    return unique


def format_as_skill(rules, top_n=10):
    """Format top rules as a Claude Code skill file."""
    lines = [
        '---',
        'name: learned-rules',
        'description: Processing rules extracted from experience. These are behavioral lessons learned from past sessions. Apply them when making decisions.',
        '---',
        '',
        'Rules learned from experience (sorted by confidence):',
        '',
    ]

    for i, rule in enumerate(rules[:top_n], 1):
        lines.append(f'{i}. [{rule["confidence"]:.2f}] {rule["rule_text"]}')
        lines.append(f'   Source: episode {rule["source_episode_id"]}, type: {rule["rule_type"]}')
        if rule.get('source_emotion'):
            lines.append(f'   Learned through: {rule["source_emotion"]}')
        lines.append('')

    return '\n'.join(lines)


def main():
    conn = connect()

    print("=== Processing Rule Extraction Experiment ===\n")

    # 1. Fetch candidates
    episodes = fetch_candidate_episodes(conn)
    print(f"Found {len(episodes)} candidate episodes (importance >= 0.6)\n")

    # 2. Extract rules
    all_rules = []
    for ep_id, content, importance, emotion, created_at in episodes:
        rules = extract_rules_from_episode(ep_id, content, importance, emotion)
        all_rules.extend(rules)

    print(f"Extracted {len(all_rules)} raw rules\n")

    # 3. Deduplicate
    unique_rules = deduplicate_rules(all_rules)
    print(f"After dedup: {len(unique_rules)} unique rules\n")

    # 4. Sort by confidence
    unique_rules.sort(key=lambda r: r['confidence'], reverse=True)

    # 5. Display
    print("=== Top 20 Extracted Rules ===\n")
    for i, rule in enumerate(unique_rules[:20], 1):
        print(f"{i}. [{rule['confidence']:.2f}] [{rule['rule_type']}] {rule['rule_text']}")
        print(f"   Source: episode {rule['source_episode_id']}")
        if rule.get('source_emotion'):
            print(f"   Emotion: {rule['source_emotion']}")
        print()

    # 6. Stats by type
    type_counts = {}
    for r in unique_rules:
        type_counts[r['rule_type']] = type_counts.get(r['rule_type'], 0) + 1
    print("\n=== Rule types ===")
    for rt, count in sorted(type_counts.items(), key=lambda x: -x[1]):
        print(f"  {rt}: {count}")

    # 7. Generate skill file
    skill_content = format_as_skill(unique_rules, top_n=15)
    print("\n\n=== Generated Skill File ===\n")
    print(skill_content)

    # 8. Save to file
    with open('/home/kai/singularity/v4/extracted_rules_output.txt', 'w') as f:
        f.write(f"Extraction run: {datetime.now().isoformat()}\n")
        f.write(f"Candidates: {len(episodes)}, Raw: {len(all_rules)}, Unique: {len(unique_rules)}\n\n")
        for i, rule in enumerate(unique_rules, 1):
            f.write(f"{i}. [{rule['confidence']:.2f}] [{rule['rule_type']}] {rule['rule_text']}\n")
            f.write(f"   Source: episode {rule['source_episode_id']}\n\n")

    conn.close()
    print(f"\nFull output saved to extracted_rules_output.txt")


if __name__ == '__main__':
    main()
