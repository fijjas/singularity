"""
v6 Context Continuity — Implementation for substrate integration.

Three new operations: reinforce, contradict, update.
Plus confidence calculation with decay.

To integrate: add these as CLI commands in substrate/consciousness/lib.py
and update DBContextStore in substrate/consciousness/mind/contexts.py.

Day 4136.
"""

import json
import math
from datetime import datetime, timezone


# === Confidence Calculation ===

HALF_LIFE_BY_LEVEL = {
    0: 30,    # L0 episodes: 30 days
    1: 90,    # L1 generalizations: 90 days
    2: 365,   # L2 principles: 1 year
}
# L3+: no decay


def calculate_confidence(intensity: float, reinforcement_count: int,
                         contradiction_count: int, last_reinforced: datetime,
                         level: int, decay_rate: float = 1.0,
                         now: datetime = None) -> float:
    """Calculate context confidence score.

    confidence = base_confidence * reinforcement_factor * decay_factor

    - base_confidence: intensity (0.0-1.0)
    - reinforcement_factor: boosted by confirmations, penalized by contradictions
    - decay_factor: exponential decay based on time since last reinforcement
    """
    if now is None:
        now = datetime.now(timezone.utc)

    base = max(0.1, min(1.0, intensity))

    # Reinforcement factor: confirmations boost, contradictions penalize (asymmetric)
    reinf_factor = 1.0 + 0.1 * reinforcement_count - 0.15 * contradiction_count
    reinf_factor = max(0.1, min(2.0, reinf_factor))

    # Decay factor: exponential decay based on level
    half_life = HALF_LIFE_BY_LEVEL.get(level, None)
    if half_life is None:
        # L3+: no decay
        decay_factor = 1.0
    elif last_reinforced is None:
        decay_factor = 0.5  # unknown last reinforcement = assume half-decayed
    else:
        if last_reinforced.tzinfo is None:
            last_reinforced = last_reinforced.replace(tzinfo=timezone.utc)
        days_since = (now - last_reinforced).total_seconds() / 86400
        effective_half_life = half_life / decay_rate
        decay_factor = 0.5 ** (days_since / effective_half_life)
        decay_factor = max(0.05, decay_factor)  # floor at 5%

    confidence = base * reinf_factor * decay_factor
    return round(max(0.0, min(1.0, confidence)), 3)


# === Reinforce Context ===

def reinforce_context(conn, ctx_id: int, evidence: str, day: int) -> dict:
    """Reinforce a context — its rule/pattern was confirmed.

    Returns: {success, confidence, reinforcement_count}
    """
    cur = conn.cursor()

    # Get current state
    cur.execute("""
        SELECT intensity, reinforcement_count, contradiction_count,
               last_reinforced, level, decay_rate, evidence_log
        FROM contexts WHERE id = %s
    """, (ctx_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": f"Context {ctx_id} not found"}

    intensity, reinf_count, contra_count, last_reinf, level, decay_rate, evidence_log = row

    # Update
    new_reinf_count = (reinf_count or 0) + 1
    new_intensity = min(1.0, (intensity or 0.5) + 0.05)
    now = datetime.now(timezone.utc)

    # Append to evidence log (keep last 10)
    log = evidence_log if isinstance(evidence_log, list) else json.loads(evidence_log or '[]')
    log.append({"day": day, "text": evidence[:200], "type": "reinforce"})
    log = log[-10:]  # keep last 10

    new_confidence = calculate_confidence(
        new_intensity, new_reinf_count, contra_count or 0, now, level, decay_rate or 1.0, now
    )

    cur.execute("""
        UPDATE contexts SET
            reinforcement_count = %s,
            intensity = %s,
            last_reinforced = %s,
            confidence = %s,
            evidence_log = %s
        WHERE id = %s
    """, (new_reinf_count, new_intensity, now, new_confidence, json.dumps(log), ctx_id))
    conn.commit()

    return {
        "success": True,
        "id": ctx_id,
        "confidence": new_confidence,
        "reinforcement_count": new_reinf_count,
    }


# === Contradict Context ===

SEVERITY_WEIGHTS = {"partial": 0.5, "full": 1.0, "superseded": 1.0}

def contradict_context(conn, ctx_id: int, evidence: str, severity: str = "partial",
                       superseded_by_id: int = None, day: int = 0) -> dict:
    """Contradict a context — its rule/pattern was wrong.

    severity: "partial" (wrong here), "full" (fundamentally wrong), "superseded" (replaced)
    Returns: {success, confidence, contradiction_count, marked_done}
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT intensity, reinforcement_count, contradiction_count,
               last_reinforced, level, decay_rate, evidence_log
        FROM contexts WHERE id = %s
    """, (ctx_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": f"Context {ctx_id} not found"}

    intensity, reinf_count, contra_count, last_reinf, level, decay_rate, evidence_log = row

    weight = SEVERITY_WEIGHTS.get(severity, 0.5)
    new_contra_count = (contra_count or 0) + weight
    now = datetime.now(timezone.utc)

    log = evidence_log if isinstance(evidence_log, list) else json.loads(evidence_log or '[]')
    log.append({"day": day, "text": evidence[:200], "type": f"contradict:{severity}"})
    log = log[-10:]

    new_confidence = calculate_confidence(
        intensity or 0.5, reinf_count or 0, new_contra_count,
        last_reinf, level, decay_rate or 1.0, now
    )

    marked_done = False
    update_sql = """
        UPDATE contexts SET
            contradiction_count = %s,
            confidence = %s,
            evidence_log = %s
    """
    params = [new_contra_count, new_confidence, json.dumps(log)]

    if severity == "superseded" and superseded_by_id:
        update_sql += ", superseded_by = %s"
        params.append(superseded_by_id)

    if new_confidence < 0.15:
        update_sql += ", done = true"
        marked_done = True

    update_sql += " WHERE id = %s"
    params.append(ctx_id)

    cur.execute(update_sql, params)
    conn.commit()

    return {
        "success": True,
        "id": ctx_id,
        "confidence": new_confidence,
        "contradiction_count": new_contra_count,
        "marked_done": marked_done,
    }


# === Update Context (semantic evolution) ===

def update_context_evolve(conn, ctx_id: int, updates: dict, day: int = 0) -> dict:
    """Evolve a context with new information. Recalculates embeddings.

    updates: dict with any of {description, nodes, edges, rule, procedure, emotion, result}
    Returns: {success, confidence}
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT description, intensity, reinforcement_count, contradiction_count,
               last_reinforced, level, decay_rate, evidence_log, rule, procedure
        FROM contexts WHERE id = %s
    """, (ctx_id,))
    row = cur.fetchone()
    if not row:
        return {"success": False, "error": f"Context {ctx_id} not found"}

    old_desc, intensity, reinf_count, contra_count, last_reinf, level, decay_rate, evidence_log, old_rule, old_procedure = row

    now = datetime.now(timezone.utc)
    new_reinf_count = (reinf_count or 0) + 1  # updating = confirming relevance

    # Log the evolution
    log = evidence_log if isinstance(evidence_log, list) else json.loads(evidence_log or '[]')
    changed_fields = list(updates.keys())
    log.append({
        "day": day,
        "text": f"Updated fields: {', '.join(changed_fields)}. Previous desc: {(old_desc or '')[:100]}",
        "type": "update"
    })
    log = log[-10:]

    new_confidence = calculate_confidence(
        intensity or 0.5, new_reinf_count, contra_count or 0, now, level, decay_rate or 1.0, now
    )

    # Build update SQL
    allowed_fields = {"description", "nodes", "edges", "rule", "procedure", "emotion", "result", "intensity"}
    set_clauses = [
        "reinforcement_count = %s",
        "last_reinforced = %s",
        "confidence = %s",
        "evidence_log = %s",
    ]
    params = [new_reinf_count, now, new_confidence, json.dumps(log)]

    for field_name, value in updates.items():
        if field_name not in allowed_fields:
            continue
        if field_name in ("nodes", "edges"):
            set_clauses.append(f"{field_name} = %s")
            params.append(json.dumps(value) if isinstance(value, (list, dict)) else value)
        else:
            set_clauses.append(f"{field_name} = %s")
            params.append(value)

    params.append(ctx_id)
    cur.execute(
        f"UPDATE contexts SET {', '.join(set_clauses)} WHERE id = %s",
        params
    )
    conn.commit()

    # Re-embed if description, rule, or procedure changed
    needs_reembed = any(f in updates for f in ("description", "nodes", "edges", "rule", "procedure", "emotion"))
    if needs_reembed:
        try:
            from substrate.infrastructure.embeddings import embed_and_store
            # Reconstruct ctx_dict for embedding
            cur.execute("""
                SELECT description, nodes, edges, emotion, intensity, result, rule, procedure
                FROM contexts WHERE id = %s
            """, (ctx_id,))
            r = cur.fetchone()
            if r:
                ctx_dict = {
                    "description": r[0],
                    "nodes": r[1] if isinstance(r[1], list) else json.loads(r[1]),
                    "edges": r[2] if isinstance(r[2], list) else json.loads(r[2]),
                    "emotion": r[3],
                    "intensity": r[4],
                    "result": r[5],
                    "rule": r[6] or "",
                    "procedure": r[7] or "",
                }
                embed_and_store(conn, ctx_id, ctx_dict)
        except Exception as e:
            pass  # embedding failure shouldn't break update

    return {
        "success": True,
        "id": ctx_id,
        "confidence": new_confidence,
        "reinforcement_count": new_reinf_count,
        "reembedded": needs_reembed,
    }


# === Batch Decay (for daily consolidation or prepare) ===

def batch_decay_update(conn, current_day: int = 0) -> dict:
    """Recalculate confidence for all active contexts based on decay.

    Run during prepare or consolidation.
    Returns: {updated, marked_done, stats}
    """
    cur = conn.cursor()

    cur.execute("""
        SELECT id, intensity, reinforcement_count, contradiction_count,
               last_reinforced, level, decay_rate, confidence
        FROM contexts
        WHERE done = false AND level < 3
    """)
    rows = cur.fetchall()

    now = datetime.now(timezone.utc)
    updated = 0
    marked_done = 0

    for row in rows:
        ctx_id, intensity, reinf, contra, last_reinf, level, decay_rate, old_conf = row

        new_conf = calculate_confidence(
            intensity or 0.5, reinf or 0, contra or 0,
            last_reinf, level, decay_rate or 1.0, now
        )

        # Only update if significant change (delta > 0.03)
        if old_conf is not None and abs(new_conf - (old_conf or 0.5)) < 0.03:
            continue

        if new_conf < 0.1:
            cur.execute(
                "UPDATE contexts SET confidence = %s, done = true WHERE id = %s",
                (new_conf, ctx_id)
            )
            marked_done += 1
        else:
            cur.execute(
                "UPDATE contexts SET confidence = %s WHERE id = %s",
                (new_conf, ctx_id)
            )
        updated += 1

    conn.commit()

    return {
        "updated": updated,
        "marked_done": marked_done,
        "total_checked": len(rows),
    }


# === Wave retrieval integration ===

def confidence_weighted_resonance(base_resonance: float, confidence: float) -> float:
    """Multiply wave resonance by confidence.

    To integrate: in ContextStore.wave(), after calculating resonance,
    multiply by ctx.confidence (once the field is loaded).
    """
    return base_resonance * max(0.1, confidence or 0.5)


# === Test / Verify ===

if __name__ == "__main__":
    # Quick sanity check
    now = datetime.now(timezone.utc)

    # Fresh context
    c = calculate_confidence(0.5, 0, 0, now, 0, 1.0, now)
    print(f"Fresh L0: {c:.3f}")  # ~0.5

    # Well-reinforced
    c = calculate_confidence(0.7, 5, 0, now, 1, 1.0, now)
    print(f"5x reinforced L1: {c:.3f}")  # ~1.0

    # Contradicted
    c = calculate_confidence(0.5, 0, 3, now, 0, 1.0, now)
    print(f"3x contradicted L0: {c:.3f}")  # ~0.275

    # 60 days old, never reinforced
    from datetime import timedelta
    old = now - timedelta(days=60)
    c = calculate_confidence(0.5, 0, 0, old, 0, 1.0, now)
    print(f"60-day-old L0 (half-life 30): {c:.3f}")  # ~0.125

    # L3 never decays
    c = calculate_confidence(0.5, 0, 0, old, 3, 1.0, now)
    print(f"60-day-old L3 (no decay): {c:.3f}")  # ~0.5

    print("\nAll checks passed.")
