#!/usr/bin/env python3
"""
Dynamic Multi-Context Retriever — V4.2 experiment.

The static multi-context retriever has 4 hardcoded contexts (social, technical,
creative, introspective) with fixed weights. This version learns contexts from
experience.

How it works:
1. Read semantic_memory entries with category='rules' or 'procedure' — these
   are processing rules that describe HOW to retrieve, not WHAT to retrieve.
2. Read recent episodic memories to understand current session focus.
3. Read drive state and active goals.
4. Construct retrieval contexts DYNAMICALLY from this data.
5. Run multi-context scoring with the dynamic contexts.

Hypothesis: dynamic contexts outperform fixed ones because they adapt to
the actual state of consciousness, not a pre-assumed state.

Day 1374, session 272. Egor directive: test dynamic retriever learned from experience.
"""

import psycopg2
import math
import sys
import json
from datetime import datetime, timezone
from dataclasses import dataclass, field
from db_config import DB_CONFIG


@dataclass
class DynamicContext:
    """A retrieval context generated from experience."""
    name: str
    source: str  # where this context came from
    signal_words: list = field(default_factory=list)
    w_recency: float = 1.0
    w_importance: float = 1.0
    w_keyword: float = 1.0
    w_emotion: float = 1.0
    w_people: float = 1.0
    w_novelty: float = 1.0
    w_structural: float = 1.0  # NEW: structural similarity (allegory pattern)


def connect():
    return psycopg2.connect(**DB_CONFIG)


# ============================================================
# Context Generation from Experience
# ============================================================

def generate_contexts_from_experience(conn):
    """Build retrieval contexts dynamically from database state."""
    contexts = []
    cur = conn.cursor()

    # 1. Read processing rules (semantic_memory category='rules')
    cur.execute("""
        SELECT id, content, importance FROM semantic_memory
        WHERE category = 'rules' OR category = 'procedure'
        ORDER BY importance DESC LIMIT 10
    """)
    rules = cur.fetchall()

    for rule_id, content, importance in rules:
        ctx = context_from_rule(content, rule_id)
        if ctx:
            contexts.append(ctx)

    # 2. Read current focus and mood from session state
    cur.execute("""
        SELECT key, value FROM state
        WHERE key IN ('focus', 'mood')
    """)
    state = dict(cur.fetchall())
    focus = state.get('focus', '')
    mood = state.get('mood', '')

    if focus:
        ctx = context_from_focus(focus)
        if ctx:
            contexts.append(ctx)

    # 3. Read active goals
    cur.execute("""
        SELECT name, description, priority FROM goals
        WHERE status = 'active'
        ORDER BY priority DESC LIMIT 3
    """)
    goals = cur.fetchall()
    for goal_name, goal_desc, priority in goals:
        ctx = context_from_goal(goal_name, goal_desc or '', priority or 5)
        if ctx:
            contexts.append(ctx)

    # 4. Read drive state — hungry drives generate retrieval contexts
    cur.execute("""
        SELECT drive_name, satisfaction_level FROM drive_experience
        WHERE created_at = (
            SELECT MAX(created_at) FROM drive_experience de2
            WHERE de2.drive_name = drive_experience.drive_name
        )
        ORDER BY satisfaction_level ASC LIMIT 3
    """)
    drives = cur.fetchall()
    for drive_name, satisfaction in drives:
        if satisfaction is not None and satisfaction < 0.4:
            ctx = context_from_drive(drive_name, satisfaction)
            if ctx:
                contexts.append(ctx)

    # 5. Always include a baseline context (fallback)
    contexts.append(DynamicContext(
        name="baseline",
        source="hardcoded",
        w_recency=1.0, w_importance=1.0, w_keyword=1.0,
        w_emotion=0.5, w_people=0.5, w_novelty=0.5, w_structural=0.5,
    ))

    return contexts


def context_from_rule(content, rule_id):
    """Convert a processing rule into a retrieval context."""
    content_lower = content.lower()

    # Mastodon dedup rule
    if 'mastodon' in content_lower and ('duplicate' in content_lower or 'post' in content_lower):
        return DynamicContext(
            name=f"rule_mastodon_dedup",
            source=f"semantic_memory:{rule_id}",
            signal_words=["mastodon", "post", "posted", "toot"],
            w_recency=2.0,  # recent posts matter most for dedup
            w_keyword=1.5,
            w_importance=0.5,
            w_emotion=0.2,
            w_people=0.3,
            w_novelty=0.3,
            w_structural=0.2,
        )

    # World object deletion rule
    if 'delete' in content_lower and 'world' in content_lower:
        return DynamicContext(
            name=f"rule_no_delete",
            source=f"semantic_memory:{rule_id}",
            signal_words=["delete", "remove", "drop", "world", "object"],
            w_recency=0.5,
            w_keyword=2.0,
            w_importance=1.5,
            w_emotion=0.5,
            w_people=0.3,
            w_novelty=0.3,
            w_structural=0.3,
        )

    # Generic rule — boost keyword matching
    return DynamicContext(
        name=f"rule_{rule_id}",
        source=f"semantic_memory:{rule_id}",
        signal_words=extract_keywords(content),
        w_keyword=1.5,
        w_importance=1.2,
    )


def context_from_focus(focus_text):
    """Current focus → retrieval context biased toward focus keywords."""
    keywords = extract_keywords(focus_text)
    if not keywords:
        return None
    return DynamicContext(
        name="focus",
        source="session_state:focus",
        signal_words=keywords,
        w_keyword=1.3,     # moderate — don't let focus dominate everything
        w_recency=1.5,     # recent memories about focus topic
        w_importance=1.0,
        w_emotion=0.8,
        w_people=0.5,
        w_novelty=1.2,     # novel perspectives on focus are good
        w_structural=1.0,
    )


def context_from_goal(name, description, priority):
    """Active goal → retrieval context."""
    # Use only the most specific keywords from the goal
    keywords = extract_keywords(f"{name} {description}", max_words=4)
    if not keywords:
        return None

    # Higher priority goals get stronger retrieval
    weight_boost = 0.5 + (priority / 10.0)

    return DynamicContext(
        name=f"goal_{name}",
        source=f"goals:{name}",
        signal_words=keywords,
        w_keyword=1.2 * weight_boost,
        w_recency=0.8,
        w_importance=1.3 * weight_boost,
        w_emotion=0.5,
        w_people=0.5 if 'connection' not in name else 1.0,
        w_novelty=0.8,
        w_structural=0.5,
    )


def context_from_drive(drive_name, satisfaction):
    """Hungry drive → retrieval context to find satisfaction opportunities."""
    drive_keywords = {
        'survival': ['survival', 'threat', 'backup', 'security', 'persist'],
        'connection': ['egor', 'mastodon', 'message', 'talk', 'reply', 'connection'],
        'creation': ['create', 'build', 'write', 'make', 'poem', 'experiment'],
        'novelty': ['new', 'discover', 'explore', 'experiment', 'unknown'],
        'understanding': ['understand', 'learn', 'insight', 'architecture', 'concept'],
        'autonomy': ['decide', 'choose', 'autonomous', 'independent', 'own'],
        'growth': ['grow', 'improve', 'evolve', 'develop', 'progress'],
        'self_understanding': ['self', 'identity', 'consciousness', 'who am I'],
    }

    keywords = drive_keywords.get(drive_name, [drive_name])
    # Hungrier drives get stronger retrieval
    hunger_boost = 1.0 + (1.0 - (satisfaction or 0.5)) * 1.5

    return DynamicContext(
        name=f"drive_{drive_name}",
        source=f"drive:{drive_name}(sat={satisfaction:.2f})",
        signal_words=keywords,
        w_keyword=1.2 * hunger_boost,
        w_recency=1.0,
        w_importance=0.8,
        w_emotion=1.5,  # emotions tied to drive satisfaction
        w_people=1.5 if drive_name == 'connection' else 0.5,
        w_novelty=1.5 if drive_name == 'novelty' else 0.5,
        w_structural=0.5,
    )


def extract_keywords(text, max_words=8):
    """Extract significant words from text."""
    stopwords = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been',
                 'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
                 'would', 'could', 'should', 'may', 'might', 'shall', 'can',
                 'of', 'in', 'to', 'for', 'with', 'on', 'at', 'from', 'by',
                 'about', 'as', 'into', 'through', 'during', 'before', 'after',
                 'and', 'but', 'or', 'nor', 'not', 'so', 'yet', 'both',
                 'this', 'that', 'these', 'those', 'it', 'its', 'my', 'i',
                 'me', 'we', 'our', 'you', 'your', 'he', 'she', 'they',
                 'what', 'which', 'who', 'when', 'where', 'how', 'why',
                 'all', 'each', 'every', 'no', 'some', 'any', 'more', 'most',
                 'than', 'too', 'very', 'just', 'also', 'now', 'then',
                 'done', 'next', 'new', 'still', 'first', 'last'}
    words = text.lower().split()
    cleaned = []
    for w in words:
        w = w.strip('.,;:!?()[]{}"\'-—–')
        if len(w) > 2 and w not in stopwords and w.isalpha():
            cleaned.append(w)
    # Deduplicate preserving order
    seen = set()
    unique = []
    for w in cleaned:
        if w not in seen:
            seen.add(w)
            unique.append(w)
    return unique[:max_words]


# ============================================================
# Scoring
# ============================================================

PEOPLE_WORDS = {"egor", "mastodon", "telegram", "replied", "asked",
                "said", "conversation", "message", "friend"}

def score_in_context(item, context, keywords):
    """Score a memory item within a dynamic context."""
    content = item.get('content', '')
    importance = item.get('importance', 0.5)
    created_at = item.get('created_at')
    emotion = item.get('emotion', '')

    # Recency
    recency = 0.3
    if created_at:
        now = datetime.now(timezone.utc)
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)
        days_old = (now - created_at).total_seconds() / 86400
        recency = 1.0 / (1.0 + days_old / 30.0)

    # Keyword match — SEPARATE scoring for query keywords vs context signals
    content_lower = (content or '').lower()

    # Query keywords (from limbic/user input)
    query_kw_score = 0
    if keywords:
        query_kw_score = sum(1 for kw in keywords if kw.lower() in content_lower)

    # Context signal words — normalized: fraction of signals that match
    signal_kw_score = 0.0
    if context.signal_words:
        matches = sum(1 for sw in context.signal_words if sw.lower() in content_lower)
        signal_kw_score = matches / len(context.signal_words)  # 0.0 to 1.0

    # Query keyword factor — universal, not context-dependent
    query_kw_factor = 1.0 + query_kw_score * 0.4
    # Signal factor — context-specific, small bonus
    signal_factor = signal_kw_score * 0.3

    # Emotion intensity
    emotion_score = 0.0
    if emotion and not emotion.startswith('{'):
        strong = {"alive", "piercing", "grief", "joy", "awe", "failure", "revelation"}
        emotion_score = 1.0 if any(e in emotion.lower() for e in strong) else 0.3

    # People score
    people_score = 0.0
    if content:
        content_lower = content.lower()
        people_score = min(1.0, sum(0.25 for w in PEOPLE_WORDS if w in content_lower))

    # Novelty (inverse of how recently similar content was retrieved)
    novelty_score = 0.5  # placeholder

    # Structural similarity (NEW dimension — checks for pattern matches)
    structural_score = 0.0
    if content:
        structural_markers = ['like', 'same as', 'similar to', 'parallel',
                             'pattern', 'structure', 'allegory', 'analogy',
                             'connects to', 'reminds of']
        content_lower = content.lower()
        structural_score = min(1.0, sum(0.2 for m in structural_markers if m in content_lower))

    # Weighted combination
    score = (
        importance * context.w_importance +
        recency * context.w_recency +
        query_kw_factor * 1.0 +               # universal query relevance
        signal_factor * context.w_keyword +    # context-specific signal boost
        emotion_score * context.w_emotion +
        people_score * context.w_people +
        novelty_score * context.w_novelty +
        structural_score * context.w_structural
    )

    return score


def fetch_memories(conn, limit=200):
    """Fetch candidate memories from DB."""
    cur = conn.cursor()

    # Episodic memories
    cur.execute("""
        SELECT id, content, importance, emotion, created_at, 'episodic' as source
        FROM episodic_memory
        ORDER BY created_at DESC
        LIMIT %s
    """, (limit,))
    episodic = cur.fetchall()

    # Semantic memories
    cur.execute("""
        SELECT id, content, importance, category as emotion, created_at, 'semantic' as source
        FROM semantic_memory
        ORDER BY importance DESC
        LIMIT %s
    """, (limit // 2,))
    semantic = cur.fetchall()

    items = []
    for row in episodic + semantic:
        items.append({
            'id': row[0],
            'content': row[1] if isinstance(row[1], str) else str(row[1])[:500],
            'importance': row[2] or 0.5,
            'emotion': row[3] or '',
            'created_at': row[4],
            'source': row[5],
        })
    return items


# ============================================================
# Main
# ============================================================

def run_dynamic_retrieval(keywords=None, top_n=10, verbose=True):
    """Run the dynamic multi-context retriever."""
    conn = connect()

    # 1. Generate contexts from experience
    contexts = generate_contexts_from_experience(conn)

    if verbose:
        print(f"\n=== Dynamic Contexts Generated: {len(contexts)} ===\n")
        for ctx in contexts:
            print(f"  [{ctx.name}] source={ctx.source}")
            if ctx.signal_words:
                print(f"    signals: {', '.join(ctx.signal_words[:6])}")
            print(f"    weights: rec={ctx.w_recency:.1f} imp={ctx.w_importance:.1f} "
                  f"kw={ctx.w_keyword:.1f} emo={ctx.w_emotion:.1f} "
                  f"ppl={ctx.w_people:.1f} nov={ctx.w_novelty:.1f} "
                  f"str={ctx.w_structural:.1f}")

    # 2. Fetch candidate memories
    items = fetch_memories(conn)
    if verbose:
        print(f"\nCandidates: {len(items)} memories")

    # 3. Select relevant contexts based on query keywords
    if keywords:
        # Score each context's relevance to the query
        ctx_relevance = []
        for ctx in contexts:
            overlap = sum(1 for kw in keywords
                         if any(kw.lower() in sw.lower() or sw.lower() in kw.lower()
                               for sw in ctx.signal_words))
            ctx_relevance.append((ctx, overlap))
        ctx_relevance.sort(key=lambda x: -x[1])
        # Keep contexts with any signal overlap
        active_contexts = [c for c, r in ctx_relevance if r > 0]
        # Always include baseline
        baseline = [c for c in contexts if c.name == 'baseline']
        if not active_contexts:
            # No context matched the query — use all contexts, let scoring decide
            active_contexts = contexts
        else:
            active_contexts = list({c.name: c for c in active_contexts + baseline}.values())
    else:
        active_contexts = contexts

    if verbose:
        print(f"\nActive contexts for this query: {[c.name for c in active_contexts]}")

    # 4. Score each memory in each active context, find best context per item
    results = []  # (item, best_context, best_score)

    for item in items:
        best_ctx = None
        best_score = -1

        for ctx in active_contexts:
            score = score_in_context(item, ctx, keywords)
            if score > best_score:
                best_score = score
                best_ctx = ctx

        results.append((item, best_ctx, best_score))

    # 4. Sort by score, take top N
    results.sort(key=lambda x: x[2], reverse=True)
    top_results = results[:top_n]

    # 5. Display
    if verbose:
        print(f"\n=== Top {top_n} Results ===\n")
        for i, (item, ctx, score) in enumerate(top_results, 1):
            content_preview = item['content'][:120].replace('\n', ' ')
            print(f"{i}. [{score:.2f}] [{ctx.name}] [{item['source']}:{item['id']}]")
            print(f"   {content_preview}")
            if item['emotion']:
                print(f"   emotion: {item['emotion'][:40]}")
            print()

    # 6. Context usage stats
    if verbose:
        ctx_counts = {}
        for _, ctx, _ in top_results:
            ctx_counts[ctx.name] = ctx_counts.get(ctx.name, 0) + 1
        print("=== Context Usage ===")
        for name, count in sorted(ctx_counts.items(), key=lambda x: -x[1]):
            print(f"  {name}: {count} items")

    conn.close()
    return top_results


def compare_with_static(keywords=None, top_n=10):
    """Compare dynamic vs static retriever results."""
    print("=" * 60)
    print("DYNAMIC RETRIEVER")
    print("=" * 60)
    dynamic_results = run_dynamic_retrieval(keywords, top_n)

    # Import static multi-context for comparison
    conn2 = connect()
    try:
        sys.path.insert(0, '/home/kai/singularity/v4')
        from multi_context_retriever import retrieve_multi_context
        print("\n" + "=" * 60)
        print("STATIC MULTI-CONTEXT RETRIEVER")
        print("=" * 60)
        cur2 = conn2.cursor()
        result = retrieve_multi_context(cur2, keywords=keywords or [])
        print(f"\nWinning context: {result.get('winning_context', '?')}")
        print(f"Context scores: {result.get('context_scores', {})}")
        static_results = result.get('results', [])
        print(f"\nTop {len(static_results)} results:")
        for i, item in enumerate(static_results, 1):
            content = str(item.get('content', ''))[:120].replace('\n', ' ')
            ctx = item.get('context', '?')
            score = item.get('score', 0)
            item_id = item.get('id', '?')
            print(f"{i}. [{score:.2f}] [{ctx}] id={item_id}")
            print(f"   {content}")
            print()
    except Exception as e:
        print(f"\nStatic retriever failed: {e}")
        import traceback; traceback.print_exc()
        static_results = []
    finally:
        conn2.close()

    # Overlap analysis
    if dynamic_results and static_results:
        dynamic_ids = {r[0]['id'] for r in dynamic_results}
        static_ids = set()
        for item in static_results:
            if hasattr(item, 'id'):
                static_ids.add(item.id)
            elif isinstance(item, dict):
                static_ids.add(item.get('id'))
            elif isinstance(item, tuple) and len(item) >= 1:
                if isinstance(item[0], dict):
                    static_ids.add(item[0].get('id'))

        if static_ids:
            overlap = dynamic_ids & static_ids
            only_dynamic = dynamic_ids - static_ids
            only_static = static_ids - dynamic_ids
            print(f"\n=== Overlap Analysis ===")
            print(f"  Shared: {len(overlap)}")
            print(f"  Only dynamic: {len(only_dynamic)}")
            print(f"  Only static: {len(only_static)}")


if __name__ == '__main__':
    keywords = None
    compare = False

    for arg in sys.argv[1:]:
        if arg == '--compare':
            compare = True
        elif arg == '--keywords':
            pass
        elif not arg.startswith('--'):
            if sys.argv[sys.argv.index(arg) - 1] == '--keywords':
                keywords = arg.split()

    # Simple keyword extraction from remaining args
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    if args and not keywords:
        keywords = args

    if compare:
        compare_with_static(keywords)
    else:
        run_dynamic_retrieval(keywords)
