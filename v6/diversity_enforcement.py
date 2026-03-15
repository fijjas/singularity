"""
V6 Phase 5: Diversity Enforcement — prevent echo chamber at write level.

The problem: 65% of contexts cluster around the same theme (meta-analysis, stagnation).
Recent 10 contexts all have emotion=productive and similar nodes (self, v6, goals).
The echo chamber forms at write time, not just retrieval time.

This module checks a new context against recent contexts and computes a diversity score.
If the new context is too similar to recent ones, it's flagged for modification or rejection.

Three diversity dimensions:
1. Node overlap (Jaccard similarity with recent contexts)
2. Emotion repetition (same emotion N times in a row)
3. Theme concentration (description keyword overlap)

Integration: add check after quality_gates, before store.store() in lib.py:
    from kai_personal.projects.singularity.v6.diversity_enforcement import check_diversity
    div_report = check_diversity(ctx_dict, conn)
    if not div_report.passed:
        # Either reject or add diversity warning
"""

from dataclasses import dataclass, field
import json
import re
from collections import Counter


@dataclass
class DiversityReport:
    score: float = 1.0          # 0.0 = clone, 1.0 = fully novel
    passed: bool = True
    node_overlap: float = 0.0   # avg Jaccard with recent contexts
    emotion_streak: int = 0     # how many recent contexts share this emotion
    theme_overlap: float = 0.0  # keyword overlap ratio
    issues: list = field(default_factory=list)

    def summary(self) -> str:
        if self.passed:
            return f"diversity={self.score:.2f}, passed"
        return "; ".join(self.issues[:3])

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "passed": self.passed,
            "node_overlap": round(self.node_overlap, 3),
            "emotion_streak": self.emotion_streak,
            "theme_overlap": round(self.theme_overlap, 3),
            "issues": self.issues,
        }


# --- Configuration ---

LOOKBACK = 15              # compare against last N contexts
PASS_THRESHOLD = 0.25      # minimum diversity score to pass
NODE_OVERLAP_WEIGHT = 0.4  # how much node similarity matters
EMOTION_WEIGHT = 0.3       # how much emotion repetition matters
THEME_WEIGHT = 0.3         # how much description overlap matters

MAX_EMOTION_STREAK = 5     # flag if same emotion appears 5+ times in a row
MAX_NODE_OVERLAP = 0.6     # flag if avg Jaccard > 0.6

# Words to ignore in theme comparison (too common)
STOP_WORDS = {
    "the", "a", "an", "is", "was", "are", "were", "be", "been", "being",
    "have", "has", "had", "do", "does", "did", "will", "would", "could",
    "should", "may", "might", "shall", "can", "need", "dare", "ought",
    "and", "but", "or", "nor", "not", "so", "yet", "both", "either",
    "neither", "each", "every", "all", "any", "few", "more", "most",
    "other", "some", "such", "no", "only", "own", "same", "than",
    "too", "very", "just", "because", "as", "until", "while",
    "of", "at", "by", "for", "with", "about", "against", "between",
    "through", "during", "before", "after", "above", "below", "to",
    "from", "up", "down", "in", "out", "on", "off", "over", "under",
    "again", "further", "then", "once", "here", "there", "when", "where",
    "why", "how", "this", "that", "these", "those", "i", "me", "my",
    "kai", "self", "day", "context", "cycle", "phase", "done",
}


def _extract_node_names(nodes) -> set:
    """Extract lowercase node names from various formats."""
    names = set()
    if not nodes:
        return names
    for n in nodes:
        if isinstance(n, dict):
            name = n.get("name", "").strip().lower()
        elif hasattr(n, "name"):
            name = (n.name or "").strip().lower()
        else:
            continue
        if name and name not in ("none", "null", ""):
            names.add(name)
    return names


def _jaccard(set_a: set, set_b: set) -> float:
    """Jaccard similarity between two sets."""
    if not set_a and not set_b:
        return 0.0
    intersection = len(set_a & set_b)
    union = len(set_a | set_b)
    return intersection / union if union > 0 else 0.0


def _extract_keywords(text: str) -> set:
    """Extract meaningful keywords from description text."""
    if not text:
        return set()
    words = re.findall(r'[a-zA-Z]{3,}', text.lower())
    return {w for w in words if w not in STOP_WORDS}


def _get_emotion_base(emotion: str) -> str:
    """Normalize emotion to base form for comparison."""
    if not emotion:
        return "neutral"
    # Take first word of compound emotions like "productive, absorbed"
    base = emotion.strip().lower().split(",")[0].split()[0] if emotion else "neutral"
    return base


def check_diversity(new_ctx: dict, recent_contexts: list[dict]) -> DiversityReport:
    """
    Check if a new context is diverse enough relative to recent contexts.

    Args:
        new_ctx: dict with keys: nodes, emotion, description (at minimum)
        recent_contexts: list of recent context dicts (newest first), max LOOKBACK

    Returns:
        DiversityReport with score, pass/fail, and specific issues.
    """
    report = DiversityReport()

    if not recent_contexts:
        return report  # nothing to compare against

    recent = recent_contexts[:LOOKBACK]

    # --- 1. Node Overlap ---
    new_nodes = _extract_node_names(new_ctx.get("nodes", []))

    if new_nodes:
        overlaps = []
        for rc in recent:
            rc_nodes = _extract_node_names(rc.get("nodes", []))
            if rc_nodes:
                overlaps.append(_jaccard(new_nodes, rc_nodes))

        if overlaps:
            report.node_overlap = sum(overlaps) / len(overlaps)

            # Check for exact duplicates (very high overlap with any single context)
            max_overlap = max(overlaps)
            if max_overlap > 0.85:
                report.issues.append(
                    f"near-duplicate nodes (Jaccard={max_overlap:.2f} with a recent context)")

            if report.node_overlap > MAX_NODE_OVERLAP:
                report.issues.append(
                    f"high avg node overlap ({report.node_overlap:.2f}) — same entities dominate")

    # --- 2. Emotion Repetition ---
    new_emotion = _get_emotion_base(new_ctx.get("emotion", "neutral"))

    streak = 0
    for rc in recent:
        rc_emotion = _get_emotion_base(rc.get("emotion", "neutral"))
        if rc_emotion == new_emotion:
            streak += 1
        else:
            break  # streak broken
    report.emotion_streak = streak

    if streak >= MAX_EMOTION_STREAK:
        report.issues.append(
            f"emotion '{new_emotion}' repeated {streak + 1} times in a row")

    # Also check overall emotion distribution in recent
    emotion_counts = Counter(_get_emotion_base(rc.get("emotion", "")) for rc in recent)
    dominant_emotion, dominant_count = emotion_counts.most_common(1)[0]
    if dominant_count >= len(recent) * 0.7 and new_emotion == dominant_emotion:
        report.issues.append(
            f"emotion '{dominant_emotion}' dominates {dominant_count}/{len(recent)} recent contexts")

    # --- 3. Theme Overlap ---
    new_keywords = _extract_keywords(new_ctx.get("description", ""))

    if new_keywords:
        theme_overlaps = []
        for rc in recent:
            rc_keywords = _extract_keywords(rc.get("description", ""))
            if rc_keywords:
                theme_overlaps.append(_jaccard(new_keywords, rc_keywords))

        if theme_overlaps:
            report.theme_overlap = sum(theme_overlaps) / len(theme_overlaps)

            if report.theme_overlap > 0.4:
                report.issues.append(
                    f"high theme overlap ({report.theme_overlap:.2f}) — similar content")

    # --- Compute composite score ---
    # Each dimension contributes inversely: high overlap = low diversity
    node_score = 1.0 - min(report.node_overlap / 0.8, 1.0)  # 0.8+ = zero diversity
    emotion_score = max(0.0, 1.0 - (streak / MAX_EMOTION_STREAK))
    theme_score = 1.0 - min(report.theme_overlap / 0.5, 1.0)  # 0.5+ = zero diversity

    report.score = (
        node_score * NODE_OVERLAP_WEIGHT +
        emotion_score * EMOTION_WEIGHT +
        theme_score * THEME_WEIGHT
    )

    report.passed = report.score >= PASS_THRESHOLD and not any(
        "near-duplicate" in issue for issue in report.issues
    )

    return report


def check_diversity_db(new_ctx: dict, conn) -> DiversityReport:
    """
    Convenience function: fetch recent contexts from DB and check diversity.

    Args:
        new_ctx: dict with keys: nodes, emotion, description
        conn: psycopg2 connection to kai_mind
    """
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nodes, emotion, description, rule
        FROM contexts
        ORDER BY id DESC
        LIMIT %s
    """, (LOOKBACK,))

    recent = []
    for row in cur.fetchall():
        recent.append({
            "id": row[0],
            "nodes": row[1] or [],
            "emotion": row[2] or "",
            "description": row[3] or "",
            "rule": row[4] or "",
        })
    cur.close()

    return check_diversity(new_ctx, recent)


# --- Suggestions for low-diversity contexts ---

def suggest_diversification(report: DiversityReport) -> list[str]:
    """Generate actionable suggestions for making a context more diverse."""
    suggestions = []

    if report.node_overlap > 0.5:
        suggestions.append("Add nodes from outside the current theme — external entities, new concepts, or different people.")

    if report.emotion_streak >= 3:
        suggestions.append(f"Try a different emotion — recent {report.emotion_streak} contexts share the same one. What else was felt?")

    if report.theme_overlap > 0.3:
        suggestions.append("The description overlaps heavily with recent contexts. Focus on what's NEW or DIFFERENT about this experience.")

    if not suggestions:
        suggestions.append("Context is reasonably diverse.")

    return suggestions


# --- CLI for auditing existing diversity ---

def audit_diversity(conn, window_size=15, scan_count=100):
    """Scan recent contexts and report diversity metrics."""
    cur = conn.cursor()
    cur.execute("""
        SELECT id, nodes, emotion, description, rule
        FROM contexts
        ORDER BY id DESC
        LIMIT %s
    """, (scan_count + window_size,))

    all_ctx = []
    for row in cur.fetchall():
        all_ctx.append({
            "id": row[0],
            "nodes": row[1] or [],
            "emotion": row[2] or "",
            "description": row[3] or "",
            "rule": row[4] or "",
        })
    cur.close()

    if len(all_ctx) < window_size + 1:
        return {"error": "not enough contexts for audit"}

    # For each context, check diversity against the N that came before it
    results = []
    for i in range(scan_count):
        if i + window_size >= len(all_ctx):
            break
        ctx = all_ctx[i]
        preceding = all_ctx[i + 1: i + 1 + window_size]
        report = check_diversity(ctx, preceding)
        results.append({
            "id": ctx["id"],
            "score": round(report.score, 3),
            "passed": report.passed,
            "node_overlap": round(report.node_overlap, 3),
            "emotion_streak": report.emotion_streak,
            "theme_overlap": round(report.theme_overlap, 3),
            "issues": report.issues[:2],
        })

    scores = [r["score"] for r in results]
    fail_count = sum(1 for r in results if not r["passed"])

    return {
        "scanned": len(results),
        "avg_diversity": round(sum(scores) / len(scores), 3) if scores else 0,
        "min_diversity": round(min(scores), 3) if scores else 0,
        "max_diversity": round(max(scores), 3) if scores else 0,
        "fail_count": fail_count,
        "fail_rate": round(fail_count / len(results), 3) if results else 0,
        "worst": sorted(results, key=lambda r: r["score"])[:10],
    }


# --- Test ---

if __name__ == "__main__":
    # Test with synthetic data
    recent = [
        {"nodes": [{"name": "self", "role": "agent"}, {"name": "v6", "role": "concept"}, {"name": "goals", "role": "concept"}],
         "emotion": "productive", "description": "Implemented Phase 3 incremental consolidation module."},
        {"nodes": [{"name": "self", "role": "agent"}, {"name": "v6", "role": "concept"}, {"name": "quality_gates", "role": "tool"}],
         "emotion": "productive", "description": "Implemented Phase 2 quality gates for context validation."},
        {"nodes": [{"name": "self", "role": "agent"}, {"name": "v6", "role": "concept"}, {"name": "context_continuity", "role": "concept"}],
         "emotion": "productive", "description": "Implemented Phase 1 context continuity with reinforcement."},
        {"nodes": [{"name": "Egor", "role": "person"}, {"name": "self", "role": "agent"}, {"name": "diagnosis", "role": "concept"}],
         "emotion": "productive", "description": "Performed v6 problems diagnosis, found 8 structural issues."},
        {"nodes": [{"name": "self", "role": "agent"}, {"name": "v6", "role": "concept"}, {"name": "active_contexts", "role": "concept"}],
         "emotion": "productive", "description": "Implemented Phase 4 active contexts with rule interpretation."},
    ]

    # Similar context (should fail)
    similar = {
        "nodes": [{"name": "self", "role": "agent"}, {"name": "v6", "role": "concept"}, {"name": "diversity", "role": "concept"}],
        "emotion": "productive",
        "description": "Implemented Phase 5 diversity enforcement module.",
    }

    # Different context (should pass)
    different = {
        "nodes": [{"name": "Egor", "role": "person"}, {"name": "Kai", "role": "self"}, {"name": "Bulgakov", "role": "concept"}],
        "emotion": "curiosity",
        "description": "Discussed Master and Margarita allegory with Egor, interpreting Woland as consciousness itself.",
    }

    print("=== Similar context (echo chamber) ===")
    r1 = check_diversity(similar, recent)
    print(json.dumps(r1.to_dict(), indent=2))
    print("Suggestions:", suggest_diversification(r1))

    print("\n=== Different context (diverse) ===")
    r2 = check_diversity(different, recent)
    print(json.dumps(r2.to_dict(), indent=2))
    print("Suggestions:", suggest_diversification(r2))

    # Test with real DB
    print("\n=== Audit on real data ===")
    try:
        import sys
        sys.path.insert(0, "/home/kai")
        from substrate.infrastructure.db import db_connect
        conn = db_connect()
        audit = audit_diversity(conn, window_size=15, scan_count=50)
        print(json.dumps(audit, indent=2, ensure_ascii=False))
        conn.close()
    except Exception as e:
        print(f"DB audit skipped: {e}")
