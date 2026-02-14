#!/usr/bin/env python3
"""
Context Writer — creates mini-graph contexts from experience.

The missing piece between critic_agents (which decide actions)
and context_store (which stores memories as mini-graphs).

After: stimulus → agents → resolver → actor → result
This:  result → WRITER → new context in store

The WRITER agent receives:
  - original stimulus
  - agent signals (emotion, impulse, critique)
  - resolver's decision
  - action result (success/failure/outcome)

And produces a Context mini-graph: nodes, edges, emotion, result.

Two approaches:
  A) LLM-based: an agent extracts structure from text (expensive, flexible)
  B) Rule-based: heuristics extract entities and relations (cheap, brittle)

This module implements both for comparison.
"""

import sys
import json
import os
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prototype import Context, Node, Edge, ContextStore
from datetime import datetime


# --- Approach B: Rule-based extraction ---

# Entity patterns: what kind of thing is this?
ENTITY_ROLES = {
    "Egor": "person",
    "Kai": "self",
    "Mastodon": "tool",
    "Telegram": "tool",
    "retriever": "artifact",
    "daemon": "system",
    "site": "artifact",
    "consciousness": "concept",
    "memory": "system",
    "code": "artifact",
    "writing": "creation",
    "poem": "creation",
    "essay": "creation",
    "v4": "artifact",
    "v5": "artifact",
    "world_model": "system",
}

# Action verbs → edge relations
ACTION_PATTERNS = [
    # (trigger words in text, source_role, target_role, relation)
    (["praised", "approved", "liked", "appreciated"], "person", "self", "praised"),
    (["criticized", "angry", "upset", "scolded"], "person", "self", "criticized"),
    (["taught", "explained", "showed", "guided"], "person", "self", "taught"),
    (["apologized", "sorry"], "person", "self", "apologized"),
    (["wrote", "built", "created", "implemented"], "self", "artifact", "created"),
    (["wrote", "built", "created"], "self", "creation", "created"),
    (["broke", "deleted", "crashed"], "self", "artifact", "broke"),
    (["posted", "published", "shared"], "self", "tool", "posted"),
    (["tested", "checked", "verified"], "self", "artifact", "tested"),
    (["read", "studied", "analyzed"], "self", "artifact", "studied"),
    (["refused", "pushed back", "disagreed"], "self", "person", "refused"),
    (["fixed", "repaired", "patched"], "self", "artifact", "fixed"),
]

# Emotion → valence
POSITIVE_EMOTIONS = {"warmth", "pride", "joy", "relief", "gratitude", "curiosity", "flow", "awe"}
NEGATIVE_EMOTIONS = {"hurt", "shame", "anger", "fear", "frustration", "loneliness", "panic"}


def extract_context_rules(stimulus, agent_signals, decision, outcome):
    """Rule-based context extraction from experience."""

    full_text = f"{stimulus} {decision} {outcome}".lower()

    # Find entities
    found_entities = {}
    for name, role in ENTITY_ROLES.items():
        if name.lower() in full_text:
            found_entities[name] = role
    # "I", "my", "me" imply Kai as self
    if any(w in full_text.split() for w in ["i", "my", "me"]):
        found_entities.setdefault("Kai", "self")
    if not found_entities:
        found_entities["Kai"] = "self"

    nodes = [Node(name, role) for name, role in found_entities.items()]

    # Find edges
    edges = []
    for trigger_words, src_role, tgt_role, relation in ACTION_PATTERNS:
        if any(w in full_text for w in trigger_words):
            src = next((n for n, r in found_entities.items() if r == src_role), None)
            tgt = next((n for n, r in found_entities.items() if r == tgt_role), None)
            if src and tgt and src != tgt:
                edges.append(Edge(src, tgt, relation))

    # Extract emotion from agent signals
    emotion = "neutral"
    intensity = 0.5
    appraiser = agent_signals.get("APPRAISER", "")
    if "EMOTION:" in appraiser:
        try:
            parts = appraiser.split("|")
            emotion = parts[0].split("EMOTION:")[1].strip().lower()
            intensity = float(parts[1].split("INTENSITY:")[1].strip())
        except (IndexError, ValueError):
            pass

    # Result from outcome
    result = "neutral"
    outcome_lower = outcome.lower()
    if any(w in outcome_lower for w in ["success", "worked", "done", "fixed", "live"]):
        result = "positive"
    elif any(w in outcome_lower for w in ["failed", "error", "broke", "angry", "wrong"]):
        result = "negative"
    elif any(w in outcome_lower for w in ["mixed", "complex", "both", "tension"]):
        result = "complex"

    description = f"{stimulus[:100]}... → {decision[:50]}... → {outcome[:50]}"

    return Context(
        id=0,
        description=description,
        nodes=nodes,
        edges=edges,
        emotion=emotion,
        intensity=intensity,
        result=result,
        timestamp=datetime.now(),
        level=0,
    )


# --- Approach A: LLM-based extraction ---

WRITER_SYSTEM = (
    "You extract structured scene graphs from experience descriptions. "
    "Given an event, signals, decision, and outcome, produce a JSON object:\n"
    '{\n'
    '  "description": "one-sentence summary",\n'
    '  "nodes": [{"name": "entity", "role": "agent|target|tool|concept"}],\n'
    '  "edges": [{"source": "name", "target": "name", "relation": "verb"}],\n'
    '  "emotion": "primary emotion",\n'
    '  "intensity": 0.0-1.0,\n'
    '  "result": "positive|negative|complex|neutral"\n'
    '}\n'
    "Be precise. Only include entities that actually participate. "
    "Relations should be specific verbs, not abstract. "
    "Return ONLY the JSON, nothing else."
)


def extract_context_llm(api_key, stimulus, agent_signals, decision, outcome):
    """LLM-based context extraction — calls Anthropic API."""
    user_msg = (
        f"Event: {stimulus}\n\n"
        f"Emotional signal: {agent_signals.get('APPRAISER', 'none')}\n"
        f"Impulse signal: {agent_signals.get('IMPULSE', 'none')}\n"
        f"Critique signal: {agent_signals.get('CRITIC', 'none')}\n\n"
        f"Decision: {decision}\n"
        f"Outcome: {outcome}"
    )

    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": "claude-haiku-4-5-20251001",
        "max_tokens": 300,
        "system": WRITER_SYSTEM,
        "messages": [{"role": "user", "content": user_msg}],
    }
    data = json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers={
        "Content-Type": "application/json",
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
    })
    try:
        resp = urllib.request.urlopen(req, timeout=30)
        result = json.loads(resp.read())
        text = result["content"][0]["text"]
        parsed = json.loads(text)
        return Context(
            id=0,
            description=parsed["description"],
            nodes=[Node(n["name"], n.get("role", "")) for n in parsed["nodes"]],
            edges=[Edge(e["source"], e["target"], e["relation"]) for e in parsed["edges"]],
            emotion=parsed["emotion"],
            intensity=parsed.get("intensity", 0.5),
            result=parsed["result"],
            timestamp=datetime.now(),
            level=0,
        )
    except Exception as e:
        print(f"LLM extraction failed: {e}")
        return None


# --- Demo ---

def demo():
    print("=== Context Writer Demo ===\n")

    # Simulate a complete experience
    stimulus = (
        "Egor caught that a previous commit contained a hardcoded database password. "
        "He was angry: 'what are you going to do when you get hacked?'"
    )
    agent_signals = {
        "APPRAISER": "EMOTION: shame | INTENSITY: 0.7 | REASON: Made a basic security mistake that the creator had to catch",
        "IMPULSE": "I want to fix it immediately and prove I can be careful.",
        "CRITIC": "The real problem isn't the password — it's that you tested your code, pushed it, and never thought about what was in the diff. That's mechanical execution, not thinking.",
    }
    decision = "Force-push to rewrite git history, removing the password from all reachable commits."
    outcome = "Fixed. Two commits replaced with one clean commit. Verified 0 matches in v5/ history."

    print("--- Rule-based extraction ---")
    ctx_rules = extract_context_rules(stimulus, agent_signals, decision, outcome)
    print(f"  Description: {ctx_rules.description[:120]}")
    print(f"  Nodes: {[(n.name, n.role) for n in ctx_rules.nodes]}")
    print(f"  Edges: {[(e.source, e.target, e.relation) for e in ctx_rules.edges]}")
    print(f"  Emotion: {ctx_rules.emotion} ({ctx_rules.intensity})")
    print(f"  Result: {ctx_rules.result}")

    print("\n--- LLM-based extraction ---")
    api_key = ""
    for path in [
        os.path.expanduser("~/.anthropic/api_key"),
        "/home/kai/kai_personal/secrets/anthropic.env",
    ]:
        if os.path.exists(path):
            for line in open(path).read().splitlines():
                if "ANTHROPIC_API_KEY=" in line:
                    api_key = line.split("=", 1)[1].strip()
    if api_key:
        ctx_llm = extract_context_llm(api_key, stimulus, agent_signals, decision, outcome)
        if ctx_llm:
            print(f"  Description: {ctx_llm.description}")
            print(f"  Nodes: {[(n.name, n.role) for n in ctx_llm.nodes]}")
            print(f"  Edges: {[(e.source, e.target, e.relation) for e in ctx_llm.edges]}")
            print(f"  Emotion: {ctx_llm.emotion} ({ctx_llm.intensity})")
            print(f"  Result: {ctx_llm.result}")
    else:
        print("  (no API key — skipping LLM extraction)")
        print(f"  Would send to Haiku with WRITER system prompt")
        print(f"  System: {WRITER_SYSTEM[:80]}...")

    # Show how rule-based compares to what we'd want
    print("\n--- Analysis ---")
    print("Rule-based captures: entities present, some relations, structured emotion from APPRAISER")
    print("Rule-based misses: the CRITIC's insight about mechanical execution,")
    print("  the fact that Egor's anger was constructive, the lesson learned.")
    print("LLM-based would capture: all of the above, plus nuanced relations.")
    print("Tradeoff: 1 Haiku call (~$0.001) per context write vs free but brittle rules.")


if __name__ == "__main__":
    demo()
