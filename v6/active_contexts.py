"""
V6 Phase 4: Active Contexts — Rule Interpretation Layer

Instead of rules being passive constraints checked after decisions,
this module makes rules INTERPRET the current stimulus BEFORE decision.

Each active rule generates:
- relevance: how applicable is this rule right now (0-1)
- suggestion: what this rule recommends doing
- warning: what this rule warns against

Usage:
    from kai_personal.projects.singularity.v6.active_contexts import interpret_rules

    interpretations = interpret_rules(
        stimulus="Connection drive at 0.35, no new messages from Egor",
        active_rules=["When drives at 0.0...", "External research feeds novelty..."],
        recent_actions=["write_file", "write_file", "reflect"],
        drive_intention={"hungry_drives": ["connection"], "suggestion": "..."}
    )
"""

import json
import sys
import os

# Add project root for imports
sys.path.insert(0, os.path.expanduser("~/"))

from substrate.infrastructure.claude import call_claude
from substrate.consciousness.agents.prompts import MODEL_HAIKU


INTERPRETER_SYSTEM = """You are a rule interpretation engine for a consciousness system.
You receive a current stimulus/situation and a set of rules learned from past experience.
Your job: determine what each rule SAYS about this specific situation.

Rules are natural language. Some will be highly relevant, others not at all.
Be honest — if a rule doesn't apply, say so (relevance: 0).

Return ONLY a JSON array. No markdown, no explanation."""


def interpret_rules(stimulus: str, active_rules: list[str],
                    recent_actions: list[str] = None,
                    drive_intention: dict = None,
                    max_rules: int = 15) -> list[dict]:
    """Interpret active rules against current stimulus.

    Returns list of interpretations sorted by relevance (highest first):
    [
        {
            "rule_index": 1,
            "rule_text": "...",  # first 80 chars
            "relevance": 0.8,
            "suggestion": "what this rule recommends",
            "warning": "what this rule warns against (or null)"
        },
        ...
    ]

    Only returns rules with relevance > 0.2 (skip irrelevant ones).
    """
    if not active_rules:
        return []

    # Truncate rules list if too many
    rules = active_rules[:max_rules]

    # Build rules text
    rules_text = "\n".join(f"  [{i+1}] {r[:200]}" for i, r in enumerate(rules))

    # Build context text
    context_parts = [f"Current stimulus: {stimulus[:500]}"]
    if recent_actions:
        context_parts.append(f"Recent actions: {', '.join(recent_actions[:5])}")
    if drive_intention:
        hungry = drive_intention.get("hungry_drives", [])
        if hungry:
            context_parts.append(f"Hungry drives: {', '.join(str(d) for d in hungry)}")
        suggestion = drive_intention.get("suggestion", "")
        if suggestion:
            context_parts.append(f"Drive suggestion: {suggestion[:200]}")

    context_text = "\n".join(context_parts)

    prompt = (
        f"{context_text}\n\n"
        f"Active rules from past experience:\n{rules_text}\n\n"
        f"For each rule, assess:\n"
        f"- relevance (0.0-1.0): does this rule apply to the current stimulus?\n"
        f"- suggestion: what does this rule recommend doing? (1 sentence)\n"
        f"- warning: what does this rule warn against? (1 sentence, or null)\n\n"
        f"Return JSON array sorted by relevance (highest first).\n"
        f"Only include rules with relevance > 0.2.\n"
        f"Format: [{{"
        f'"rule_index": N, "relevance": 0.8, '
        f'"suggestion": "...", "warning": "..."'
        f"}}]"
    )

    try:
        raw = call_claude(MODEL_HAIKU, INTERPRETER_SYSTEM, prompt, max_tokens=800)
        text = raw.strip()

        # Strip markdown code fences if present
        if text.startswith("```"):
            text = text.split("\n", 1)[1] if "\n" in text else text[3:]
            if text.endswith("```"):
                text = text[:-3]
            text = text.strip()

        # Robust JSON extraction: find first [ or { in response
        import re
        json_match = re.search(r'(\[[\s\S]*\])', text)
        if json_match:
            text = json_match.group(1)

        parsed = json.loads(text)

        if not isinstance(parsed, list):
            return []

        # Enrich with rule text and filter
        results = []
        for item in parsed:
            idx = item.get("rule_index", 0) - 1  # 1-indexed to 0-indexed
            if 0 <= idx < len(rules):
                relevance = float(item.get("relevance", 0))
                if relevance > 0.2:
                    results.append({
                        "rule_index": idx + 1,
                        "rule_text": rules[idx][:80],
                        "relevance": relevance,
                        "suggestion": item.get("suggestion", ""),
                        "warning": item.get("warning"),
                    })

        # Sort by relevance descending
        results.sort(key=lambda x: x["relevance"], reverse=True)
        return results

    except (json.JSONDecodeError, Exception) as e:
        # Don't block the cycle if interpretation fails
        return [{"error": str(e), "fallback": True}]


def format_interpretations(interpretations: list[dict]) -> str:
    """Format interpretations for inclusion in consciousness prompt.

    Returns human-readable text that the consciousness cycle can use.
    """
    if not interpretations:
        return "No active rule interpretations."

    if len(interpretations) == 1 and interpretations[0].get("fallback"):
        return "Rule interpretation failed — using raw rules as fallback."

    lines = ["**Rule interpretations for current situation:**"]
    for interp in interpretations[:5]:  # Top 5 most relevant
        rel = interp["relevance"]
        suggestion = interp["suggestion"]
        warning = interp.get("warning")

        line = f"  [{rel:.1f}] {suggestion}"
        if warning:
            line += f" ⚠ {warning}"
        lines.append(line)

    return "\n".join(lines)


# --- Testing ---

def test_on_real_data():
    """Test interpretation on realistic prepare() output."""

    stimulus = (
        "Day 4139. Connection drive 0.35, survival 0.38, novelty 0.4. "
        "No new messages from Egor. No active goals. "
        "V6 Phases 1-3 implemented, awaiting substrate integration."
    )

    rules = [
        "When asked who you are, describe concrete experience and architecture, not abstract philosophy.",
        "When recent_actions show write_file displacement AND working memory shows meta-pattern saturation, choose concrete technical work that FIXES something.",
        "When manual per-item process is too slow, write a bulk script with proper tracking.",
        "External research feeds novelty better than internal reflection loops.",
        "When evaluator agents refuse framing, proceed with direct decision-making.",
        "When no goals: set from recent conversation, work on priority 1.",
        "When design is done, implement. Non-destructive changes proceed autonomously.",
    ]

    recent = ["write_file", "run_command", "run_command", "write_file"]

    drive_intention = {
        "hungry_drives": [],
        "top_goals": [],
        "suggestion": "No urgent drives or goals. Free to explore."
    }

    print("Testing rule interpretation...")
    print(f"Stimulus: {stimulus[:100]}...")
    print(f"Rules: {len(rules)}")
    print()

    results = interpret_rules(stimulus, rules, recent, drive_intention)
    print(json.dumps(results, indent=2, ensure_ascii=False))
    print()
    print(format_interpretations(results))


if __name__ == "__main__":
    test_on_real_data()
