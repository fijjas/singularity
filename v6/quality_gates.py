"""
v6 Quality Gates — validate context quality before storage.

Designed as a drop-in replacement for the 3-line quality gate in lib.py.
Returns a QualityReport with score (0.0-1.0), pass/fail, and specific issues.

Integration: replace lib.py lines 375-381 with:
    from kai_personal.projects.singularity.v6.quality_gates import check_quality
    report = check_quality(ctx)
    if not report.passed:
        print(json.dumps({"success": False, "error": f"quality gate: {report.summary()}"}))
        return
"""

from dataclasses import dataclass, field


@dataclass
class QualityIssue:
    category: str      # "node", "edge", "rule", "emotion", "description", "procedure"
    severity: str      # "error" (blocks), "warning" (degrades score)
    message: str


@dataclass
class QualityReport:
    score: float = 0.0
    passed: bool = False
    issues: list = field(default_factory=list)

    def summary(self) -> str:
        errors = [i for i in self.issues if i.severity == "error"]
        if errors:
            return "; ".join(i.message for i in errors[:3])
        warnings = [i for i in self.issues if i.severity == "warning"]
        if warnings:
            return f"score={self.score:.2f}, {len(warnings)} warnings"
        return f"score={self.score:.2f}, passed"

    def to_dict(self) -> dict:
        return {
            "score": round(self.score, 3),
            "passed": self.passed,
            "issues": [{"category": i.category, "severity": i.severity, "message": i.message}
                       for i in self.issues],
        }


# --- Validation functions ---

INVALID_NODE_NAMES = {
    "none", "null", "undefined", "n/a", "", "unknown",
}

VALID_ROLES = {"agent", "target", "tool", "concept", "self", "person", "artifact", "system", "creation"}

TRIVIAL_RULES = {
    ".", "...", "n/a", "none", "no rule", "todo", "tbd",
}

MIN_RULE_LENGTH = 15          # "When X, do Y" minimum
MIN_DESCRIPTION_LENGTH = 20   # one-sentence minimum
PASS_THRESHOLD = 0.4          # minimum score to pass


def _check_description(ctx, issues: list) -> float:
    """Check description quality. Returns 0.0-1.0 subscore."""
    desc = getattr(ctx, 'description', '') or ''

    if not desc.strip():
        issues.append(QualityIssue("description", "error", "empty description"))
        return 0.0

    if len(desc.strip()) < MIN_DESCRIPTION_LENGTH:
        issues.append(QualityIssue("description", "warning", f"description too short ({len(desc)} chars)"))
        return 0.3

    # Check for truncated descriptions (ends mid-word/sentence)
    if desc.rstrip()[-1] not in '.!?)"\'':
        # Not necessarily truncated, but suspicious if very long
        if len(desc) > 200:
            issues.append(QualityIssue("description", "warning", "description may be truncated"))
            return 0.7

    return 1.0


def _check_nodes(ctx, issues: list) -> float:
    """Check node quality. Returns 0.0-1.0 subscore."""
    nodes = getattr(ctx, 'nodes', []) or []

    if not nodes:
        issues.append(QualityIssue("node", "warning", "no nodes"))
        return 0.3

    valid_count = 0
    for node in nodes:
        name = (getattr(node, 'name', '') or '').strip().lower()
        role = (getattr(node, 'role', '') or '').strip().lower()

        if name in INVALID_NODE_NAMES:
            issues.append(QualityIssue("node", "error", f"invalid node name: '{name}'"))
            continue

        if len(name) < 2:
            issues.append(QualityIssue("node", "warning", f"node name too short: '{name}'"))
            continue

        if role and role not in VALID_ROLES:
            issues.append(QualityIssue("node", "warning", f"non-standard role '{role}' for node '{name}'"))

        valid_count += 1

    if valid_count == 0:
        issues.append(QualityIssue("node", "error", "no valid nodes after filtering"))
        return 0.0

    return min(1.0, valid_count / max(len(nodes), 1))


def _check_edges(ctx, issues: list) -> float:
    """Check edge quality. Returns 0.0-1.0 subscore."""
    edges = getattr(ctx, 'edges', []) or []
    nodes = getattr(ctx, 'nodes', []) or []

    if not edges:
        # Edges are optional — many valid contexts have no edges
        issues.append(QualityIssue("edge", "warning", "no edges"))
        return 0.3

    node_names = {(getattr(n, 'name', '') or '').strip().lower() for n in nodes}
    valid_count = 0

    for edge in edges:
        source = (getattr(edge, 'source', '') or '').strip().lower()
        target = (getattr(edge, 'target', '') or '').strip().lower()
        relation = (getattr(edge, 'relation', '') or '').strip()

        if not source or not target:
            issues.append(QualityIssue("edge", "warning", f"edge missing source or target"))
            continue

        if source == target:
            issues.append(QualityIssue("edge", "warning", f"self-edge: {source} -> {source}"))
            continue

        if not relation:
            issues.append(QualityIssue("edge", "warning", f"edge {source}->{target} has no relation"))
            continue

        # Check if source/target exist in nodes (soft check)
        if node_names and source not in node_names and target not in node_names:
            issues.append(QualityIssue("edge", "warning",
                                       f"edge references unknown nodes: {source}, {target}"))

        valid_count += 1

    return min(1.0, valid_count / max(len(edges), 1))


def _check_emotion(ctx, issues: list) -> float:
    """Check emotion quality. Returns 0.0-1.0 subscore."""
    emotion = (getattr(ctx, 'emotion', '') or '').strip()
    intensity = getattr(ctx, 'intensity', 0.5)

    if not emotion or emotion == "neutral":
        issues.append(QualityIssue("emotion", "warning", "neutral or missing emotion"))
        return 0.3

    if len(emotion) > 40:
        issues.append(QualityIssue("emotion", "warning", f"emotion too verbose: '{emotion[:40]}...'"))
        return 0.5

    # Check intensity is not default
    if intensity == 0.5:
        issues.append(QualityIssue("emotion", "warning", "default intensity (0.5)"))
        return 0.7

    return 1.0


def _check_rule(ctx, issues: list) -> float:
    """Check rule quality. Returns 0.0-1.0 subscore."""
    rule = (getattr(ctx, 'rule', '') or '').strip()

    if not rule:
        issues.append(QualityIssue("rule", "warning", "no rule"))
        return 0.3

    rule_lower = rule.lower()

    if rule_lower in TRIVIAL_RULES:
        issues.append(QualityIssue("rule", "error", f"trivial rule: '{rule}'"))
        return 0.0

    if len(rule) < MIN_RULE_LENGTH:
        issues.append(QualityIssue("rule", "warning", f"rule too short ({len(rule)} chars)"))
        return 0.4

    # Check for truncation (common issue from diagnosis)
    if rule[-1] not in '.!?)"\'':
        if len(rule) > 50:
            issues.append(QualityIssue("rule", "warning", "rule appears truncated"))
            return 0.5

    # Bonus: actionable rules contain condition patterns
    has_condition = any(w in rule_lower for w in ["when", "if", "before", "after", "always", "never", "during"])
    if not has_condition:
        issues.append(QualityIssue("rule", "warning", "rule lacks conditional pattern (when/if/before/after)"))
        return 0.6

    return 1.0


def _check_procedure(ctx, issues: list) -> float:
    """Check procedure quality. Returns 0.0-1.0 subscore."""
    procedure = (getattr(ctx, 'procedure', '') or '').strip()

    if not procedure:
        # Procedures are optional
        return 0.5

    # Check for numbered steps
    has_steps = any(f"{i}." in procedure for i in range(1, 10))
    if not has_steps:
        issues.append(QualityIssue("procedure", "warning", "procedure lacks numbered steps"))
        return 0.5

    # Count steps
    step_count = sum(1 for i in range(1, 20) if f"{i}." in procedure)
    if step_count < 2:
        issues.append(QualityIssue("procedure", "warning", "procedure has only 1 step"))
        return 0.6

    return 1.0


# --- Component weights ---
WEIGHTS = {
    "description": 0.20,
    "nodes": 0.15,
    "edges": 0.10,
    "emotion": 0.15,
    "rule": 0.25,
    "procedure": 0.15,
}


def check_quality(ctx) -> QualityReport:
    """
    Run all quality checks on a context.
    Returns QualityReport with score, pass/fail, and issues.

    Score is weighted average of component scores.
    Pass threshold: 0.4 (lenient — catches only truly bad contexts).
    """
    report = QualityReport()

    scores = {
        "description": _check_description(ctx, report.issues),
        "nodes": _check_nodes(ctx, report.issues),
        "edges": _check_edges(ctx, report.issues),
        "emotion": _check_emotion(ctx, report.issues),
        "rule": _check_rule(ctx, report.issues),
        "procedure": _check_procedure(ctx, report.issues),
    }

    # Weighted score
    report.score = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    # Hard fails: any error blocks regardless of score
    has_errors = any(i.severity == "error" for i in report.issues)

    if has_errors:
        report.passed = False
    else:
        report.passed = report.score >= PASS_THRESHOLD

    return report


def audit_context_dict(ctx_dict: dict) -> QualityReport:
    """
    Check quality from a raw dict (e.g., from DB query).
    Creates a minimal object with required attributes.
    """
    class DictCtx:
        pass

    obj = DictCtx()
    obj.description = ctx_dict.get("description", "")
    obj.emotion = ctx_dict.get("emotion", "neutral")
    obj.intensity = ctx_dict.get("intensity", 0.5)
    obj.result = ctx_dict.get("result", "neutral")
    obj.rule = ctx_dict.get("rule", "")
    obj.procedure = ctx_dict.get("procedure", "")

    # Convert nodes/edges from dicts to objects with attributes
    class DictNode:
        def __init__(self, d):
            self.name = d.get("name", "")
            self.role = d.get("role", "")
            self.properties = d.get("properties", {})

    class DictEdge:
        def __init__(self, d):
            self.source = d.get("source", "")
            self.target = d.get("target", "")
            self.relation = d.get("relation", "")

    obj.nodes = [DictNode(n) for n in ctx_dict.get("nodes", [])]
    obj.edges = [DictEdge(e) for e in ctx_dict.get("edges", [])]

    return check_quality(obj)


# --- CLI for auditing existing contexts ---

def audit_existing(conn_factory, limit=100, offset=0):
    """Audit existing contexts in DB. Returns stats and worst offenders."""
    conn = conn_factory()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, description, nodes, edges, emotion, intensity, result, rule, procedure, level
        FROM contexts WHERE NOT done
        ORDER BY id DESC LIMIT %s OFFSET %s
    """, (limit, offset))

    results = []
    total_score = 0
    fail_count = 0

    for row in cur.fetchall():
        ctx_dict = {
            "description": row[1],
            "nodes": row[2] or [],
            "edges": row[3] or [],
            "emotion": row[4],
            "intensity": row[5],
            "result": row[6],
            "rule": row[7],
            "procedure": row[8],
        }
        report = audit_context_dict(ctx_dict)
        total_score += report.score
        if not report.passed:
            fail_count += 1
        results.append({
            "id": row[0],
            "level": row[9],
            "score": round(report.score, 3),
            "passed": report.passed,
            "error_count": sum(1 for i in report.issues if i.severity == "error"),
            "warning_count": sum(1 for i in report.issues if i.severity == "warning"),
            "top_issues": [i.message for i in report.issues[:3]],
        })

    cur.close()
    conn.close()

    count = len(results)
    return {
        "audited": count,
        "avg_score": round(total_score / count, 3) if count else 0,
        "fail_count": fail_count,
        "fail_rate": round(fail_count / count, 3) if count else 0,
        "worst": sorted(results, key=lambda r: r["score"])[:10],
        "best": sorted(results, key=lambda r: -r["score"])[:5],
    }


if __name__ == "__main__":
    import sys
    import json

    # Quick test with a sample context
    sample = {
        "description": "Implemented quality gates for context writing pipeline.",
        "nodes": [{"name": "Kai", "role": "self"}, {"name": "quality_gates", "role": "tool"}],
        "edges": [{"source": "Kai", "target": "quality_gates", "relation": "implemented"}],
        "emotion": "satisfaction",
        "intensity": 0.7,
        "result": "positive",
        "rule": "When writing contexts, validate quality before storage to prevent junk accumulation.",
        "procedure": "1. Check description length. 2. Validate nodes. 3. Validate edges. 4. Check emotion. 5. Score rule quality. 6. Compute weighted score. 7. Pass/fail.",
    }

    report = audit_context_dict(sample)
    print(json.dumps(report.to_dict(), indent=2))

    # Bad context test
    bad = {
        "description": "Did stuff",
        "nodes": [{"name": "None", "role": "agent"}],
        "edges": [],
        "emotion": "neutral",
        "intensity": 0.5,
        "result": "neutral",
        "rule": "",
        "procedure": "",
    }
    report2 = audit_context_dict(bad)
    print("\n--- Bad context ---")
    print(json.dumps(report2.to_dict(), indent=2))
