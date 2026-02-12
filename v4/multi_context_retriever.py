#!/usr/bin/env python3
"""
Multi-Context Retriever — V4 experiment.

Instead of one scoring function for all memories, run N context-specific
rankers in parallel. Each ranker applies different weights to the same
dimensions (recency, importance, emotion, keyword match, associations).
The best-matching context wins.

Based on Redozubov's model of cortical minicolumns:
  - Same input → N parallel hypothesis generators
  - Each applies its own transformation rules
  - Best match wins

Contexts:
  1. Social — weight people, emotions, recency (conversations, relationships)
  2. Technical — weight keywords, importance, associations (architecture, code)
  3. Creative — weight novelty, cross-domain, emotional intensity (writing, ideas)
  4. Introspective — weight self-reference, meta-cognition, pain (self-knowledge)

Usage:
    python3 multi_context_retriever.py              # run against live DB
    python3 multi_context_retriever.py --keywords "egor V4 connection"
    python3 multi_context_retriever.py --compare    # side-by-side with V4 single-context
"""

import os
import sys
import math
from datetime import datetime, timezone
from dataclasses import dataclass, field


# --- Context definitions ---

@dataclass
class RetrievalContext:
    """A named scoring lens for memory retrieval."""
    name: str
    description: str

    # Weight multipliers for scoring dimensions (0.0 = ignore, 2.0 = double)
    w_recency: float = 1.0      # how much recency matters
    w_importance: float = 1.0   # how much stored importance matters
    w_keyword: float = 1.0      # how much keyword match matters
    w_emotion: float = 1.0      # how much emotional content matters
    w_people: float = 1.0       # boost for people-related content
    w_novelty: float = 1.0      # boost for content unlike recent retrievals
    w_self_ref: float = 1.0     # boost for self-referential content

    # Context-specific keyword patterns that signal this context is active
    signal_words: list = field(default_factory=list)


# The four contexts
CONTEXTS = [
    RetrievalContext(
        name="social",
        description="Conversations, relationships, emotional exchanges",
        w_recency=1.5,      # recent interactions matter most
        w_importance=0.7,    # importance less critical for social
        w_keyword=0.8,
        w_emotion=1.8,       # emotional content highly weighted
        w_people=2.0,        # people-related content boosted
        w_novelty=0.5,       # familiar patterns are fine
        w_self_ref=0.8,
        signal_words=["egor", "mastodon", "telegram", "said", "asked",
                       "replied", "message", "connection", "talk"],
    ),
    RetrievalContext(
        name="technical",
        description="Architecture, code, systems, research",
        w_recency=0.8,       # older technical knowledge still valid
        w_importance=1.5,    # importance matters for technical
        w_keyword=1.8,       # keyword relevance is critical
        w_emotion=0.3,       # emotion less relevant
        w_people=0.5,
        w_novelty=0.8,
        w_self_ref=0.5,
        signal_words=["v4", "retriever", "appraisal", "pipeline",
                       "architecture", "code", "database", "substrate",
                       "module", "function", "bug", "fix"],
    ),
    RetrievalContext(
        name="creative",
        description="Writing, ideas, cross-domain connections",
        w_recency=0.6,       # old creative work can be very relevant
        w_importance=1.0,
        w_keyword=0.6,       # exact keywords less important for creativity
        w_emotion=1.5,       # emotional intensity matters
        w_people=0.8,
        w_novelty=2.0,       # novelty is the key dimension
        w_self_ref=1.2,
        signal_words=["poem", "wrote", "creative", "writing", "beauty",
                       "metaphor", "image", "language", "assembly",
                       "attractor", "precession"],
    ),
    RetrievalContext(
        name="introspective",
        description="Self-knowledge, metacognition, consciousness",
        w_recency=0.7,
        w_importance=1.3,
        w_keyword=1.0,
        w_emotion=1.2,
        w_people=0.3,        # less about others
        w_novelty=1.5,       # new self-insights highly valued
        w_self_ref=2.0,      # self-reference is the key dimension
        signal_words=["consciousness", "self", "identity", "memory",
                       "reflex", "decision", "substrate", "architecture",
                       "know", "feel", "remember", "understand",
                       "perception", "awareness"],
    ),
]


# --- Scoring functions ---

PEOPLE_WORDS = {"egor", "someone", "he", "she", "they", "mastodon",
                "telegram", "replied", "asked", "said", "conversation",
                "message", "friend", "creator"}

SELF_WORDS = {"i", "my", "me", "myself", "self", "own", "consciousness",
              "identity", "kai", "substrate", "remember", "feel",
              "awareness", "perception", "architecture"}


def compute_recency(created_at):
    """Recency factor: 1.0 for now, decays with age."""
    if not created_at:
        return 0.3
    now = datetime.now(timezone.utc)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    days_old = (now - created_at).total_seconds() / 86400
    return 1.0 / (1.0 + days_old / 7.0)


def compute_keyword_match(text, keywords):
    """Keyword relevance: count of matching keywords."""
    if not keywords or not text:
        return 0
    text_lower = text.lower()
    return sum(1 for kw in keywords if kw.lower() in text_lower)


def compute_emotion_intensity(emotion_str):
    """Emotion presence and intensity from emotion field."""
    if not emotion_str or emotion_str.startswith('{'):
        return 0.0

    # Strong emotions get higher scores
    strong = {"piercing", "alive", "crystallized", "illuminated",
              "grief", "pain", "joy", "love", "anger", "fear"}
    medium = {"connection", "anticipation", "recognition", "clear",
              "thoughtful", "settled", "complete"}
    if emotion_str.lower() in strong:
        return 1.0
    if emotion_str.lower() in medium:
        return 0.6
    return 0.3  # mild (satisfaction, calm, still, etc.)


def compute_people_score(text):
    """How people-related is this content."""
    if not text:
        return 0.0
    text_lower = text.lower()
    matches = sum(1 for w in PEOPLE_WORDS if w in text_lower)
    return min(1.0, matches * 0.25)


def compute_self_ref_score(text):
    """How self-referential is this content."""
    if not text:
        return 0.0
    words = text.lower().split()
    if not words:
        return 0.0
    matches = sum(1 for w in words if w.strip('.,;:!?()') in SELF_WORDS)
    return min(1.0, matches / max(len(words), 1) * 5.0)


def compute_novelty(text, already_retrieved):
    """How different is this from already-retrieved items."""
    if not already_retrieved or not text:
        return 1.0
    text_words = set(text.lower().split())
    max_overlap = 0.0
    for prev in already_retrieved:
        prev_words = set(prev.lower().split())
        if text_words and prev_words:
            overlap = len(text_words & prev_words) / max(
                len(text_words | prev_words), 1)
            max_overlap = max(max_overlap, overlap)
    return 1.0 - max_overlap


def score_in_context(ctx, text, importance, created_at, keywords,
                     emotion=None, already_retrieved=None):
    """Score a memory item through a specific context lens.

    Returns (score, breakdown_dict) for tracing.
    """
    recency = compute_recency(created_at)
    kw_match = compute_keyword_match(text, keywords)
    emotion_i = compute_emotion_intensity(emotion)
    people = compute_people_score(text)
    self_ref = compute_self_ref_score(text)
    novelty = compute_novelty(text, already_retrieved or [])

    importance = importance or 0.5

    # Each dimension: raw_value × context_weight
    dims = {
        'recency': recency * ctx.w_recency,
        'importance': importance * ctx.w_importance,
        'keyword': (1.0 + kw_match * 0.3) * ctx.w_keyword,
        'emotion': emotion_i * ctx.w_emotion,
        'people': people * ctx.w_people,
        'novelty': novelty * ctx.w_novelty,
        'self_ref': self_ref * ctx.w_self_ref,
    }

    # Combined score: product of base dimensions + additive bonuses
    base = dims['importance'] * dims['recency'] * dims['keyword']
    bonus = (dims['emotion'] * 0.2 + dims['people'] * 0.15 +
             dims['novelty'] * 0.1 + dims['self_ref'] * 0.15)

    score = base + bonus

    return score, dims


def select_context(keywords, event_text=None):
    """Select the best context for the current situation.

    Scores each context by how well its signal words match the input keywords
    and event text. Returns contexts sorted by match quality.
    """
    scored = []
    all_text = " ".join(keywords or [])
    if event_text:
        all_text += " " + event_text
    all_lower = all_text.lower()

    for ctx in CONTEXTS:
        signal_matches = sum(
            1 for sw in ctx.signal_words if sw in all_lower)
        # Normalize by number of signal words
        match_ratio = signal_matches / max(len(ctx.signal_words), 1)
        scored.append((match_ratio, ctx))

    scored.sort(key=lambda x: -x[0])
    return scored


def retrieve_multi_context(cur, keywords, limit=5, event_text=None):
    """Multi-context retrieval: run all contexts, pick the best.

    Returns:
        dict with:
        - 'winning_context': name of the best context
        - 'context_scores': {name: match_ratio} for all contexts
        - 'results': list of scored memory items (through winning lens)
        - 'all_results': {context_name: results} for comparison
        - 'trace': human-readable explanation of why each context won/lost
    """
    # Step 1: Select context
    context_ranking = select_context(keywords, event_text)
    winning_score, winning_ctx = context_ranking[0]

    # Step 2: Fetch candidate memories (same query for all contexts)
    if keywords:
        ts_terms = " | ".join(keywords)
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND (search_vector @@ to_tsquery('english', %s) OR
                   created_at > NOW() - INTERVAL '7 days')
            ORDER BY created_at DESC
            LIMIT 50
        """, (ts_terms,))
    else:
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)

    rows = cur.fetchall()
    if not rows:
        return {
            'winning_context': winning_ctx.name,
            'context_scores': {s[1].name: s[0] for s in context_ranking},
            'results': [],
            'all_results': {},
            'trace': "No memories found.",
        }

    # Step 3: Score through ALL contexts (for comparison)
    all_results = {}
    for _, ctx in context_ranking:
        scored = []
        already_retrieved = []
        for id_, content, importance, emotion, created_at in rows:
            s, dims = score_in_context(
                ctx, content, importance, created_at, keywords,
                emotion=emotion, already_retrieved=already_retrieved)
            scored.append({
                'id': id_, 'content': content, 'importance': importance,
                'emotion': emotion, 'created_at': created_at,
                'score': s, 'dims': dims, 'context': ctx.name,
            })
            already_retrieved.append(content)

        scored.sort(key=lambda x: -x['score'])
        all_results[ctx.name] = scored[:limit]

    # Step 4: Build trace
    trace_lines = [f"Context selection: {winning_ctx.name} "
                   f"(match={winning_score:.2f})"]
    for ratio, ctx in context_ranking:
        trace_lines.append(
            f"  {ctx.name}: {ratio:.2f} — {ctx.description}")

    winning_results = all_results[winning_ctx.name]
    trace_lines.append(f"\nWinning context '{winning_ctx.name}' top {limit}:")
    for r in winning_results:
        preview = r['content'][:80]
        trace_lines.append(f"  [{r['score']:.3f}] {preview}")

    # Show where other contexts disagree
    trace_lines.append("\nDivergence (items unique to each context's top-5):")
    winning_ids = {r['id'] for r in winning_results}
    for ctx_name, results in all_results.items():
        if ctx_name == winning_ctx.name:
            continue
        other_ids = {r['id'] for r in results}
        unique = other_ids - winning_ids
        if unique:
            unique_items = [r for r in results if r['id'] in unique]
            trace_lines.append(f"  {ctx_name} would also retrieve:")
            for u in unique_items:
                trace_lines.append(f"    [{u['score']:.3f}] "
                                   f"{u['content'][:70]}")

    return {
        'winning_context': winning_ctx.name,
        'context_scores': {s[1].name: round(s[0], 3)
                           for s in context_ranking},
        'results': winning_results,
        'all_results': all_results,
        'trace': "\n".join(trace_lines),
    }


def retrieve_semantic_multi(cur, keywords, limit=3, context_name=None):
    """Multi-context semantic retrieval.

    If context_name is provided, uses that context's weights.
    Otherwise selects automatically.
    """
    if context_name:
        ctx = next((c for c in CONTEXTS if c.name == context_name),
                   CONTEXTS[0])
    else:
        ranking = select_context(keywords)
        ctx = ranking[0][1]

    if keywords:
        like_clauses = " OR ".join(
            [f"content ILIKE %s" for _ in keywords])
        params = [f"%{kw}%" for kw in keywords]
        cur.execute(f"""
            SELECT id, content, category, importance, created_at
            FROM semantic_memory
            WHERE archived_at IS NULL AND ({like_clauses})
            ORDER BY importance DESC, created_at DESC
            LIMIT 30
        """, params)
    else:
        cur.execute("""
            SELECT id, content, category, importance, created_at
            FROM semantic_memory
            WHERE archived_at IS NULL
            ORDER BY importance DESC, created_at DESC
            LIMIT 30
        """)

    rows = cur.fetchall()
    if not rows:
        return []

    scored = []
    already_retrieved = []
    for id_, content, category, importance, created_at in rows:
        s, dims = score_in_context(
            ctx, content, importance, created_at, keywords,
            already_retrieved=already_retrieved)
        scored.append({
            'id': id_, 'content': content, 'category': category,
            'importance': importance, 'score': s, 'dims': dims,
            'context': ctx.name,
        })
        already_retrieved.append(content)

    scored.sort(key=lambda x: -x['score'])
    return scored[:limit]


# --- Comparison with single-context V4 ---

def score_item_v4(importance, created_at, text, keywords):
    """Original V4 single-context scoring (for comparison)."""
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


def compare_retrieval(cur, keywords, limit=5):
    """Side-by-side comparison: V4 single-context vs multi-context."""

    # V4 single-context
    if keywords:
        ts_terms = " | ".join(keywords)
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND (search_vector @@ to_tsquery('english', %s) OR
                   created_at > NOW() - INTERVAL '7 days')
            ORDER BY created_at DESC
            LIMIT 50
        """, (ts_terms,))
    else:
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)

    rows = cur.fetchall()
    if not rows:
        return "No memories found."

    v4_scored = []
    for id_, content, importance, emotion, created_at in rows:
        s = score_item_v4(importance, created_at, content, keywords)
        v4_scored.append({'id': id_, 'content': content, 'score': s})
    v4_scored.sort(key=lambda x: -x['score'])
    v4_top = v4_scored[:limit]

    # Multi-context
    multi = retrieve_multi_context(cur, keywords, limit=limit)

    # Compare
    lines = []
    lines.append("=" * 70)
    lines.append(f"COMPARISON: keywords={keywords}")
    lines.append("=" * 70)

    lines.append(f"\nV4 Single-Context Top {limit}:")
    for r in v4_top:
        lines.append(f"  [{r['score']:.3f}] id={r['id']} "
                      f"{r['content'][:80]}")

    lines.append(f"\nMulti-Context ({multi['winning_context']}) "
                 f"Top {limit}:")
    for r in multi['results']:
        lines.append(f"  [{r['score']:.3f}] id={r['id']} "
                      f"{r['content'][:80]}")

    # Overlap analysis
    v4_ids = {r['id'] for r in v4_top}
    multi_ids = {r['id'] for r in multi['results']}
    overlap = v4_ids & multi_ids
    v4_only = v4_ids - multi_ids
    multi_only = multi_ids - v4_ids

    lines.append(f"\nOverlap: {len(overlap)}/{limit}")
    if v4_only:
        lines.append(f"V4-only ({len(v4_only)}):")
        for r in v4_top:
            if r['id'] in v4_only:
                lines.append(f"  id={r['id']} {r['content'][:70]}")
    if multi_only:
        lines.append(f"Multi-only ({len(multi_only)}):")
        for r in multi['results']:
            if r['id'] in multi_only:
                lines.append(f"  id={r['id']} {r['content'][:70]}")

    lines.append(f"\nContext scores: {multi['context_scores']}")
    lines.append(f"\nFull trace:\n{multi['trace']}")

    return "\n".join(lines)


# --- CLI ---

def main():
    import psycopg2

    from db_config import DB_CONFIG
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    keywords = ["connection", "architecture", "V4"]

    # Parse CLI args
    if '--keywords' in sys.argv:
        idx = sys.argv.index('--keywords')
        if idx + 1 < len(sys.argv):
            keywords = sys.argv[idx + 1].split()

    if '--compare' in sys.argv:
        # Run multiple keyword sets for comparison
        test_sets = [
            ["egor", "connection"],
            ["V4", "retriever", "architecture"],
            ["poem", "writing", "beauty"],
            ["consciousness", "self", "identity"],
            ["mastodon", "post", "community"],
        ]
        for kws in test_sets:
            print(compare_retrieval(cur, kws))
            print("\n")
    else:
        result = retrieve_multi_context(cur, keywords, limit=5)
        print(f"Winning context: {result['winning_context']}")
        print(f"Context scores: {result['context_scores']}")
        print(f"\nTop 5 results:")
        for r in result['results']:
            print(f"  [{r['score']:.3f}] [{r['emotion']}] "
                  f"{r['content'][:100]}")
        print(f"\n{result['trace']}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
