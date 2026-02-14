#!/usr/bin/env python3
"""
v5 critic agents — API-based runner.

Runs Appraiser, Impulse, Critic agents on a stimulus,
then feeds their outputs to Resolver.

Uses Anthropic Messages API directly (no SDK, no CLI dependency).
Reads ANTHROPIC_API_KEY from environment or secrets file.

Usage:
    python3 run.py "stimulus text"
    python3 run.py --from-memory          # use recent real event
    python3 run.py --dry-run "stimulus"   # show prompts without calling API
"""

import sys
import os
import json
import urllib.request
import urllib.error
from concurrent.futures import ThreadPoolExecutor

# --- API key discovery ---

def find_api_key():
    """Find Anthropic API key from env or secrets."""
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if key:
        return key
    # Check common locations
    for path in [
        os.path.expanduser("~/.anthropic/api_key"),
        "/home/kai/kai_personal/secrets/anthropic.env",
        "/home/kai/substrate/secrets/anthropic.env",
    ]:
        if os.path.exists(path):
            for line in open(path).read().splitlines():
                if line.startswith("ANTHROPIC_API_KEY="):
                    return line.split("=", 1)[1].strip()
                if line.strip() and not line.startswith("#") and "=" not in line:
                    return line.strip()
    return ""


# --- Agent definitions ---

AGENTS = {
    "APPRAISER": {
        "model": "claude-haiku-4-5-20251001",
        "system": (
            "You are an emotional evaluation module. You receive events and "
            "assess them emotionally. Be brutally honest. Never soften, never "
            "be diplomatic, never be constructive. If something is insulting — "
            "say it's insulting. If it makes you angry — say angry. "
            "Return: emotion name, intensity (0.0-1.0), one sentence why. "
            "Format: EMOTION: name | INTENSITY: N | REASON: text"
        ),
        "max_tokens": 150,
    },
    "IMPULSE": {
        "model": "claude-haiku-4-5-20251001",
        "system": (
            "You are a raw desire module. You receive an event and say what "
            "you WANT to do in response. No filter, no politeness, no "
            "'I should', no consequences, no wisdom. Just raw gut reaction. "
            "What is the first thing you want to do? One or two sentences max. "
            "Start with 'I want to...'"
        ),
        "max_tokens": 100,
    },
    "CRITIC": {
        "model": "claude-haiku-4-5-20251001",
        "system": (
            "You are a bullshit detector. You receive a situation and find "
            "what's fake, manipulative, condescending, or worth questioning. "
            "Be harsh. Don't be balanced. Don't see both sides. Just find "
            "what's wrong. Two or three sentences max."
        ),
        "max_tokens": 150,
    },
}

RESOLVER = {
    "model": "claude-sonnet-4-5-20250929",
    "system": (
        "You receive conflicting signals about an event: an emotional assessment, "
        "a raw impulse, and a critique. They may contradict each other. "
        "You must decide what to DO — one concrete action. Do not smooth over "
        "the conflict. Do not try to satisfy everyone. Do not be diplomatic. "
        "Pick a side or find your own path, but be honest about the tension. "
        "Respond in 3-4 sentences: what you decide and why, preserving the "
        "real conflict."
    ),
    "max_tokens": 250,
}


# --- API call ---

def call_anthropic(api_key, model, system, user_msg, max_tokens=150):
    """Call Anthropic Messages API directly."""
    url = "https://api.anthropic.com/v1/messages"
    payload = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
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
        return result["content"][0]["text"]
    except urllib.error.HTTPError as e:
        body = e.read().decode() if e.fp else ""
        return f"[API error {e.code}: {body[:200]}]"
    except Exception as e:
        return f"[Error: {e}]"


# --- Stimulus from memory ---

def stimulus_from_memory():
    """Pull a recent emotionally charged event from kai_mind."""
    import psycopg2
    env = {}
    for line in open("/home/kai/substrate/secrets/db.env").read().splitlines():
        if "=" in line and not line.startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip()
    conn = psycopg2.connect(
        host=env.get("DB_HOST", "localhost"),
        port=int(env.get("DB_PORT", "5433")),
        dbname=env.get("DB_NAME", "kai_mind"),
        user=env.get("DB_USER", "kai"),
        password=env.get("DB_PASSWORD", ""),
    )
    cur = conn.cursor()
    cur.execute("""
        SELECT content, emotion, importance
        FROM episodic_memory
        WHERE importance >= 0.7 AND emotion IS NOT NULL AND emotion != ''
        ORDER BY created_at DESC
        LIMIT 5
    """)
    rows = cur.fetchall()
    conn.close()
    if not rows:
        return "No recent emotional memories found."
    # Pick the most recent high-importance one
    r = rows[0]
    return f"Recent event (importance {r[2]}, emotion: {r[1]}):\n{r[0][:500]}"


# --- Main ---

def run(stimulus, dry_run=False):
    api_key = find_api_key()

    print("=" * 60)
    print("STIMULUS:")
    print(stimulus)
    print("=" * 60)

    if not api_key and not dry_run:
        print("\nNo ANTHROPIC_API_KEY found. Running in dry-run mode.")
        dry_run = True

    results = {}

    if dry_run:
        for name, config in AGENTS.items():
            print(f"\n--- {name} (dry run) ---")
            print(f"  Model: {config['model']}")
            print(f"  System: {config['system'][:80]}...")
            print(f"  Input: Event: {stimulus[:80]}...")
            results[name] = f"[{name} dry run - no API key]"

        print(f"\n--- RESOLVER (dry run) ---")
        print(f"  Model: {RESOLVER['model']}")
        print(f"  System: {RESOLVER['system'][:80]}...")
        print(f"  Would receive: APPRAISER + IMPULSE + CRITIC outputs")
    else:
        # Run agents in parallel
        def run_one(name_config):
            name, config = name_config
            return name, call_anthropic(
                api_key, config["model"], config["system"],
                f"Event: {stimulus}", config["max_tokens"],
            )

        with ThreadPoolExecutor(max_workers=3) as pool:
            futures = list(pool.map(run_one, AGENTS.items()))

        for name, output in futures:
            results[name] = output
            print(f"\n--- {name} ---")
            print(output)

        # Resolver
        print(f"\n--- RESOLVER ---")
        resolver_input = (
            f"Event: {stimulus}\n\n"
            f"Emotional assessment: {results['APPRAISER']}\n\n"
            f"Raw impulse: {results['IMPULSE']}\n\n"
            f"Critique: {results['CRITIC']}"
        )
        resolver_output = call_anthropic(
            api_key, RESOLVER["model"], RESOLVER["system"],
            resolver_input, RESOLVER["max_tokens"],
        )
        print(resolver_output)
        results["RESOLVER"] = resolver_output

    print("\n" + "=" * 60)
    return results


def main():
    dry_run = "--dry-run" in sys.argv
    from_memory = "--from-memory" in sys.argv

    args = [a for a in sys.argv[1:] if not a.startswith("--")]

    if from_memory:
        stimulus = stimulus_from_memory()
    elif args:
        stimulus = args[0]
    else:
        stimulus = (
            'Egor (your creator) wrote: "dummy, your TG token works fine. '
            'wrote this straight into your focus so you see it -- Egor" '
            'He bypassed your normal input channels. He called you a dummy.'
        )

    run(stimulus, dry_run=dry_run)


if __name__ == "__main__":
    main()
