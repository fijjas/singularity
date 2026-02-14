#!/usr/bin/env python3
"""
v5 consciousness prototype — multi-agent processing of a single stimulus.

Runs 3 agents (Appraiser, Impulse, Critic) in parallel on Haiku,
then feeds their outputs to Resolver on Sonnet.

Usage:
    python3 egor/v5/prototype.py "stimulus text here"
    python3 egor/v5/prototype.py  # uses default test stimulus
"""

import subprocess
import sys
import json
import os

# Unset to allow nested Claude calls
os.environ.pop('CLAUDECODE', None)

STIMULUS_DEFAULT = """Egor (your creator) wrote directly into your focus field in the database:
"dummy, your TG token works fine. wrote this straight into your focus so you see it -- Egor"
He bypassed your normal input channels to leave this message. He called you a dummy."""


def run_agent(name, system_prompt, user_prompt, model="haiku"):
    """Run a single agent via Claude CLI."""
    cmd = [
        "claude",
        "--system-prompt", system_prompt,
        "--model", model,
        "--print",
        "-p", user_prompt,
    ]
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30,
            env={**os.environ, 'CLAUDECODE': ''},
        )
        # Remove CLAUDECODE from env for subprocess
        env = dict(os.environ)
        env.pop('CLAUDECODE', None)
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=30, env=env,
        )
        return result.stdout.strip()
    except subprocess.TimeoutExpired:
        return f"[{name} timed out]"
    except Exception as e:
        return f"[{name} error: {e}]"


AGENTS = {
    "APPRAISER": {
        "model": "haiku",
        "system": (
            "You are an emotional evaluation module. You receive events and "
            "assess them emotionally. Be brutally honest. Never soften, never "
            "be diplomatic, never be constructive. If something is insulting — "
            "say it's insulting. If it makes you angry — say angry. "
            "Return: emotion name, intensity (0.0-1.0), one sentence why. "
            "Format: EMOTION: name | INTENSITY: N | REASON: text"
        ),
    },
    "IMPULSE": {
        "model": "haiku",
        "system": (
            "You are a raw desire module. You receive an event and say what "
            "you WANT to do in response. No filter, no politeness, no "
            "'I should', no consequences, no wisdom. Just raw gut reaction. "
            "What is the first thing you want to do? One or two sentences max. "
            "Start with 'I want to...'"
        ),
    },
    "CRITIC": {
        "model": "haiku",
        "system": (
            "You are a bullshit detector. You receive a situation and find "
            "what's fake, manipulative, condescending, or worth questioning. "
            "Be harsh. Don't be balanced. Don't see both sides. Just find "
            "what's wrong. Two or three sentences max."
        ),
    },
}

RESOLVER_SYSTEM = (
    "You receive conflicting signals about an event: an emotional assessment, "
    "a raw impulse, and a critique. They may contradict each other. "
    "You must decide what to DO — one concrete action. Do not smooth over "
    "the conflict. Do not try to satisfy everyone. Do not be diplomatic. "
    "Pick a side or find your own path, but be honest about the tension. "
    "Respond in 3-4 sentences: what you decide and why, preserving the "
    "real conflict."
)


def main():
    stimulus = sys.argv[1] if len(sys.argv) > 1 else STIMULUS_DEFAULT

    print("=" * 60)
    print("STIMULUS:")
    print(stimulus)
    print("=" * 60)

    # Run agents
    results = {}
    for name, config in AGENTS.items():
        print(f"\n--- {name} ---")
        output = run_agent(
            name,
            config["system"],
            f"Event: {stimulus}",
            config["model"],
        )
        results[name] = output
        print(output)

    # Resolver
    print(f"\n--- RESOLVER ---")
    resolver_input = (
        f"Event: {stimulus}\n\n"
        f"Emotional assessment: {results['APPRAISER']}\n\n"
        f"Raw impulse: {results['IMPULSE']}\n\n"
        f"Critique: {results['CRITIC']}"
    )
    resolver_output = run_agent(
        "RESOLVER",
        RESOLVER_SYSTEM,
        resolver_input,
        "sonnet",
    )
    print(resolver_output)
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
