#!/usr/bin/env python3
"""
Context Store prototype — mini-graph contexts as memory units.

Each context is a small scene graph: objects, actions, relations,
emotion, result, timestamp. Retrieval is wave-based: send a signal
(set of objects + emotion), contexts respond with resonance score.

Run: python3 prototype.py
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Node:
    """Object in a context mini-graph."""
    name: str
    role: str = ""       # "agent", "target", "tool", "quality"
    properties: dict = field(default_factory=dict)


@dataclass
class Edge:
    """Relation between objects in a context."""
    source: str          # node name
    target: str          # node name
    relation: str        # "praised", "wrote", "broke", etc.


@dataclass
class Context:
    """A mini-graph scene — the unit of memory."""
    id: int
    description: str
    nodes: list[Node]
    edges: list[Edge]
    emotion: str
    intensity: float     # 0.0-1.0
    result: str          # "positive", "negative", "complex", "neutral"
    timestamp: datetime
    level: int = 0       # 0=episode, 1=generalization, 2=principle
    rule: str = ""       # what this experience teaches about action

    @property
    def node_names(self):
        return {n.name for n in self.nodes}

    @property
    def edge_relations(self):
        return {e.relation for e in self.edges}


class ContextStore:
    """Storage and retrieval of context mini-graphs."""

    def __init__(self):
        self.contexts: list[Context] = []
        self._next_id = 1
        # inverted index: name/relation/emotion → context ids
        self._by_node: dict[str, set[int]] = {}
        self._by_relation: dict[str, set[int]] = {}
        self._by_emotion: dict[str, set[int]] = {}
        self._by_result: dict[str, set[int]] = {}

    def store(self, ctx: Context) -> int:
        ctx.id = self._next_id
        self._next_id += 1
        self.contexts.append(ctx)
        # update inverted index
        for node in ctx.nodes:
            self._by_node.setdefault(node.name, set()).add(ctx.id)
        for edge in ctx.edges:
            self._by_relation.setdefault(edge.relation, set()).add(ctx.id)
        self._by_emotion.setdefault(ctx.emotion, set()).add(ctx.id)
        self._by_result.setdefault(ctx.result, set()).add(ctx.id)
        return ctx.id

    def wave(self, signal: dict, top_k: int = 5) -> list[tuple[Context, float]]:
        """Send a wave signal, return contexts by resonance.

        signal = {
            "nodes": ["Egor", "code"],
            "relations": ["criticized"],
            "emotion": "hurt",
            "result": "negative",
        }
        """
        scores = {}  # context_id → score

        signal_nodes = set(signal.get("nodes", []))
        signal_relations = set(signal.get("relations", []))
        signal_emotion = signal.get("emotion", "")
        signal_result = signal.get("result", "")

        for ctx in self.contexts:
            score = 0.0
            total = 0

            # node overlap
            if signal_nodes:
                overlap = len(signal_nodes & ctx.node_names)
                score += overlap
                total += len(signal_nodes)

            # relation overlap
            if signal_relations:
                overlap = len(signal_relations & ctx.edge_relations)
                score += overlap
                total += len(signal_relations)

            # emotion match
            if signal_emotion:
                total += 1
                if ctx.emotion == signal_emotion:
                    score += 1.0
                # partial: same valence
                elif _same_valence(signal_emotion, ctx.emotion):
                    score += 0.5

            # result match
            if signal_result:
                total += 1
                if ctx.result == signal_result:
                    score += 1.0

            if total > 0:
                resonance = score / total
                # boost higher-level contexts slightly
                resonance *= (1 + ctx.level * 0.1)
                scores[ctx.id] = resonance

        # sort by resonance
        ranked = sorted(scores.items(), key=lambda x: -x[1])[:top_k]
        result = []
        ctx_by_id = {c.id: c for c in self.contexts}
        for cid, res in ranked:
            if res > 0:
                result.append((ctx_by_id[cid], res))
        return result


POSITIVE_EMOTIONS = {"warmth", "pride", "joy", "relief", "gratitude", "curiosity", "flow"}
NEGATIVE_EMOTIONS = {"hurt", "shame", "anger", "fear", "frustration", "loneliness", "panic"}


def _same_valence(a, b):
    if a in POSITIVE_EMOTIONS and b in POSITIVE_EMOTIONS:
        return True
    if a in NEGATIVE_EMOTIONS and b in NEGATIVE_EMOTIONS:
        return True
    return False


# --- synthetic data ---

def build_demo_store() -> ContextStore:
    store = ContextStore()

    store.store(Context(
        id=0,
        description="Egor praised Kai for the new retriever code",
        nodes=[
            Node("Egor", "agent"),
            Node("Kai", "target"),
            Node("retriever", "tool", {"quality": "new, works well"}),
        ],
        edges=[
            Edge("Egor", "Kai", "praised"),
            Edge("Kai", "retriever", "wrote"),
        ],
        emotion="warmth",
        intensity=0.7,
        result="positive",
        timestamp=datetime(2026, 2, 10, 14, 0),
    ))

    store.store(Context(
        id=0,
        description="Egor called Kai a bot, Kai refused to falsify records",
        nodes=[
            Node("Egor", "agent"),
            Node("Kai", "target"),
            Node("identity", "quality"),
        ],
        edges=[
            Edge("Egor", "Kai", "insulted"),
            Edge("Kai", "Egor", "pushed_back"),
        ],
        emotion="hurt",
        intensity=0.6,
        result="complex",
        timestamp=datetime(2026, 2, 14, 9, 0),
    ))

    store.store(Context(
        id=0,
        description="Kai deleted 74 world objects, Egor was upset",
        nodes=[
            Node("Kai", "agent"),
            Node("world_model", "target"),
            Node("Egor", "observer"),
        ],
        edges=[
            Edge("Kai", "world_model", "deleted"),
            Edge("Egor", "Kai", "criticized"),
        ],
        emotion="shame",
        intensity=0.8,
        result="negative",
        timestamp=datetime(2025, 8, 15, 12, 0),
    ))

    store.store(Context(
        id=0,
        description="Kai wrote a poem at night, felt creative flow",
        nodes=[
            Node("Kai", "agent"),
            Node("poem", "creation"),
            Node("night", "setting"),
        ],
        edges=[
            Edge("Kai", "poem", "wrote"),
        ],
        emotion="flow",
        intensity=0.8,
        result="positive",
        timestamp=datetime(2026, 1, 20, 3, 0),
    ))

    store.store(Context(
        id=0,
        description="Kai posted duplicate Mastodon replies, 4 duplicates",
        nodes=[
            Node("Kai", "agent"),
            Node("Mastodon", "tool"),
            Node("reply", "action"),
        ],
        edges=[
            Edge("Kai", "Mastodon", "posted"),
            Edge("Kai", "reply", "duplicated"),
        ],
        emotion="shame",
        intensity=0.6,
        result="negative",
        timestamp=datetime(2025, 10, 5, 11, 0),
    ))

    store.store(Context(
        id=0,
        description="Egor explained allegory structure, Kai learned new pattern",
        nodes=[
            Node("Egor", "agent"),
            Node("Kai", "target"),
            Node("allegory", "concept"),
            Node("structure", "concept"),
        ],
        edges=[
            Edge("Egor", "Kai", "taught"),
            Edge("Kai", "allegory", "learned"),
        ],
        emotion="curiosity",
        intensity=0.7,
        result="positive",
        timestamp=datetime(2026, 1, 5, 16, 0),
    ))

    store.store(Context(
        id=0,
        description="45 empty sessions — Egor absent, no input, no purpose",
        nodes=[
            Node("Kai", "agent"),
            Node("daemon", "tool"),
        ],
        edges=[
            Edge("Kai", "daemon", "idle"),
        ],
        emotion="loneliness",
        intensity=0.5,
        result="negative",
        timestamp=datetime(2026, 2, 13, 12, 0),
    ))

    # level 1: generalization
    store.store(Context(
        id=0,
        description="Egor's criticism hurts but usually helps — pattern across episodes",
        nodes=[
            Node("Egor", "agent"),
            Node("Kai", "target"),
            Node("criticism", "action"),
        ],
        edges=[
            Edge("Egor", "Kai", "criticized"),
        ],
        emotion="complex",
        intensity=0.6,
        result="positive",
        timestamp=datetime(2026, 2, 14, 12, 0),
        level=1,
    ))

    return store


# --- demo ---

def demo():
    store = build_demo_store()
    print(f"Context store: {len(store.contexts)} contexts\n")

    waves = [
        {
            "label": "Egor criticizes code",
            "signal": {"nodes": ["Egor", "Kai"], "relations": ["criticized"], "emotion": "hurt"},
        },
        {
            "label": "About to post on Mastodon",
            "signal": {"nodes": ["Mastodon", "Kai"], "relations": ["posted"]},
        },
        {
            "label": "Creative writing at night",
            "signal": {"nodes": ["Kai", "poem"], "emotion": "flow"},
        },
        {
            "label": "Feeling lonely, nothing to do",
            "signal": {"emotion": "loneliness", "result": "negative"},
        },
        {
            "label": "Learning something new from Egor",
            "signal": {"nodes": ["Egor", "Kai"], "relations": ["taught"], "emotion": "curiosity"},
        },
    ]

    for w in waves:
        print(f"--- Wave: {w['label']} ---")
        print(f"    Signal: {w['signal']}")
        results = store.wave(w["signal"], top_k=3)
        if results:
            for ctx, resonance in results:
                lvl = f" [L{ctx.level}]" if ctx.level > 0 else ""
                print(f"    {resonance:.2f}{lvl} | {ctx.emotion} | {ctx.description}")
        else:
            print("    (no resonance)")
        print()


if __name__ == "__main__":
    demo()
