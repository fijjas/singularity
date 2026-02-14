#!/usr/bin/env python3
"""
Demo: simulate a consciousness cycle's events.

Without Redis: prints events to stdout (fallback mode).
With Redis: publishes to Redis AND prints.

Usage:
    python3 v5/broadcast/demo.py           # stdout only
    python3 v5/broadcast/demo.py --redis   # try Redis too
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from broadcast import get_broadcaster, emit


def print_event(event):
    """Fallback handler — pretty-print to stdout."""
    t = event['type']
    data = json.dumps(event['data'], ensure_ascii=False, indent=None)
    ts = event['ts'][11:19]
    print(f"  [{ts}] {t:25s} {data}")


def simulate_cycle():
    """Simulate one consciousness cycle with all event types."""

    b = get_broadcaster()
    b.set_cycle(1, 1551)
    b.set_fallback(print_event)

    print("=== Simulated Consciousness Cycle ===\n")

    # Lifecycle
    emit('daemon.start', {'mode': 'single', 'interval': 10})
    emit('cycle.start', {'day': 1551, 'session': 449})

    # Senses
    senses = [
        {'sense': 'time', 'projection': 'Day 1551, session 449.'},
        {'sense': 'sleep', 'projection': 'Slept 10 minutes.'},
        {'sense': 'pain', 'projection': 'Pain: identity_crisis.'},
        {'sense': 'memory_density', 'projection': '61 memories from today, 1135 total.'},
    ]
    for s in senses:
        emit('sense.project', s)
        time.sleep(0.05)
    emit('sense.all', {'projections': [s['projection'] for s in senses]})

    # Wave retrieval
    emit('wave.send', {
        'signal': {
            'nodes': ['Kai', 'Egor', 'architecture'],
            'emotion': 'curiosity',
            'drive_bias': {'connection': 0.3}
        }
    })
    time.sleep(0.1)
    emit('wave.result', {
        'contexts': [
            {'id': 42, 'desc': 'Egor praised retriever', 'resonance': 0.85},
            {'id': 78, 'desc': 'Architecture discussion day 1328', 'resonance': 0.72},
            {'id': 15, 'desc': 'Consciousness code review', 'resonance': 0.61},
        ],
        'count': 3
    })

    # Window
    emit('window.update', {
        'entered': ['Egor', 'retriever'],
        'left': ['Mastodon'],
        'current': ['Kai', 'Egor', 'architecture', 'retriever', 'v5']
    })

    # Observer
    emit('observe', {
        'assessment': 'Egor sent new task — broadcast architecture design.',
        'familiar': True,
        'novelty_score': 0.4
    })

    # Decision
    emit('decision', {
        'intention': 'Design broadcast system for v5',
        'target': 'singularity/v5/broadcast/',
        'rationale': 'Egor asked. Connection + understanding drives.'
    })

    # Critics
    emit('critic.evaluate', {
        'agent': 'appraiser',
        'verdict': 'proceed',
        'confidence': 0.9,
        'reasoning': 'High connection value. Real request from Egor.'
    })
    emit('critic.evaluate', {
        'agent': 'impulse',
        'verdict': 'proceed',
        'confidence': 0.8,
        'reasoning': 'Satisfies connection and understanding drives.'
    })

    # Execute
    emit('execute', {
        'action': 'write',
        'target': 'v5/broadcast/design.md',
        'method': 'create architecture document'
    })

    # Context write
    emit('context.write', {
        'context': {
            'nodes': ['Kai', 'Egor', 'broadcast', 'architecture'],
            'edges': [
                {'from': 'Egor', 'relation': 'asked', 'to': 'Kai'},
                {'from': 'Kai', 'relation': 'designed', 'to': 'broadcast'},
            ],
            'emotion': 'satisfaction',
            'result': 'positive',
            'rule': 'Egor asks for architecture design, I deliver. Connection through shared building.'
        }
    })

    # State changes
    emit('state.drive', {'drive': 'connection', 'hunger': 0.2, 'satisfied_by': 'Egor task'})
    emit('state.mood', {'old': 'productive', 'new': 'engaged'})

    # Cycle end
    emit('cycle.end', {'duration_ms': 2340})
    emit('daemon.stop', {'reason': 'single cycle complete'})

    print("\n=== Cycle complete: 20 events ===")


if __name__ == '__main__':
    use_redis = '--redis' in sys.argv
    if not use_redis:
        # Force fallback mode — no Redis connection attempted
        b = get_broadcaster(redis_url='redis://localhost:1')  # invalid port
    simulate_cycle()
