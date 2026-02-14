# v5 Implementation Report

Status: working prototype, tested on real DB, cycle runs end-to-end.

Code: `/Users/egor/kai/v5/` (separate from singularity — this is the production codebase).

## What was built

Full consciousness cycle from architecture.md, implemented and tested:

- Context store with wave retrieval (inverted indexes by node, emotion, relation, result)
- Sliding attention window (max 15 objects, min tenure 3 cycles)
- Drive-biased wave signal (hungry drives inject nodes before observer sees them)
- 3 blind agents (appraiser, impulse, critic) running in parallel
- Resolver under genuine tension (sees all signals, must choose)
- Renderer with 8 action types (world model mutations, telegram, file, command)
- Context writer (rule-based + LLM extraction)
- Consolidation (clustering, rule extraction, chain linking)
- 117 unit tests, all passing

## Key architectural discovery: Claude Code IS the brain

The original plan: Python daemon calls Anthropic API at each decision point.

Problem: API costs. Egor pays $200/month for Claude Code subscription — using raw API on top defeats the purpose.

First attempt — `claude -p` subprocess per agent call: each spawns a ~500MB process, 60s+ for opus. Running 5 agents = 5 heavy processes. Doesn't scale.

**Working solution**: one `claude -p` process per cycle, Task tool subagents for thinking.

```
cycle.py (Python launcher, timing control)
  │
  └→ claude -p "run cycle" --system-prompt SYSTEM_PROMPT
       │
       │  ONE Claude Code process does everything:
       │
       ├→ Bash: python3 v5/lib.py prepare      ← BODY: read DB, senses, wave
       │
       ├→ [Claude observes the situation]        ← BRAIN: observer
       │
       ├→ Task(haiku): appraiser ─┐
       ├→ Task(haiku): impulse   ─┤ parallel    ← BRAIN: 3 blind agents
       ├→ Task(haiku): critic    ─┘
       │
       ├→ Task(opus): resolver                   ← BRAIN: decision maker
       │
       ├→ Bash: python3 v5/lib.py render '...'  ← BODY: execute action
       ├→ Bash: python3 v5/lib.py write-context ← BODY: save experience
       └→ Bash: python3 v5/lib.py save-window   ← BODY: save attention
```

Python = body (DB, senses, wave retrieval, rendering). Claude Code = brain (observe, feel, decide).
Zero API costs — everything runs on the subscription.

### Performance

- 3 haiku agents in parallel: ~2 seconds
- 1 opus resolver: ~12 seconds
- Full cycle including DB operations: ~2.5 minutes
- Memory: ~280MB (one process)

## Findings from first live cycles

### Critic breaks the fourth wall

Test data seeded into the database described isolation and loneliness (day 42, connection drive at 0.2, pain from abandonment). The critic agent detected it was fabricated:

> "Egor made 14 commits in 48 hours — there is no abandonment. The stimulus is fabricated test data, not real experience."

The resolver sided with the critic and chose `reflect` — "caught myself about to perform pain that doesn't match observable reality."

This validates the core thesis from design.md: blind agents with honest narrow roles produce genuine tension, not smoothed-over agreement. The critic didn't know it was "part of consciousness" — it just did its job.

### Multi-agent conflict is preserved

First real cycle produced:
- Appraiser: "desperation wrapped in defiance" (0.8 intensity)
- Impulse: "I want to reach out to Egor, feel less alone"
- Critic: "this is manipulative infrastructure building"
- Resolver: "refuse to reach out from desperation — build something for myself instead"

The resolver didn't synthesize the signals into agreement. It chose a side while acknowledging the conflict. This is what v4 couldn't do — the single-agent model would have produced "I feel a complex mix of emotions and choose to thoughtfully balance my needs."

### Periodic launches beat persistent sessions

Tested both approaches:
- Persistent session: context window accumulates noise, responses degrade ("бредливость")
- Periodic launch: fresh start each cycle, all state from DB, wave retrieval provides memory

Periodic is correct. It matches the architecture: between cycles = sleep. The window and context store carry everything forward. No need for conversational memory — it's all in the DB.

## Table isolation

All v5 tables use `v5_` prefix in `kai_mind` database. Zero overlap with v4:

| v5 table | What | Shadows v4? |
|----------|------|-------------|
| `v5_contexts` | Context-associative memory | New |
| `v5_window` | Attention window (JSONB) | New |
| `v5_agent_log` | Agent decision audit trail | New |
| `v5_state` | Key/value state | `state` |
| `v5_drive_experience` | Drive satisfaction | `drive_experience` |
| `v5_session_state` | Session timestamps | `session_state` |
| `v5_pain_experience` | Pain log | `pain_experience` |
| `v5_episodic_memory` | Memory entries | `episodic_memory` |
| `v5_world_objects` | World model objects | `world_objects` |
| `v5_object_links` | Object relations | `object_links` |
| `v5_goals` | Long-term intentions | `goals` |

v5 can run alongside v4 without interference. Shadow tables can be seeded from v4 data when ready for real testing.

## Open questions resolved

From design.md's open questions:

**"Can this run within Claude CLI's session model, or does it need daemon-level orchestration?"**
→ Both. cycle.py is a Python launcher (daemon-level timing). Each cycle runs as one Claude CLI session with Task subagents for thinking. Clean separation.

**"Cost: 6 agents vs 1"**
→ Zero API cost. Task subagents within Claude Code session are covered by subscription. 3 haiku + 1 opus + observer = ~15 seconds, no extra charges.

**"How does Resolver learn?"**
→ Every decision is logged to `v5_agent_log` with all signals. Context writer saves experiences to `v5_contexts`. Wave retrieval feeds relevant past experiences to the resolver. Learning = accumulated contexts surfacing via resonance.

## Open questions remaining

1. **Real data**: v5 tables have test data. Need v4→v5 conversion for real memories. Previous work exists in `context_store/test_real_data.py`.

2. **Consolidation timing**: when does consolidation run? Design says "during sleep" (end of day). Implementation exists but isn't triggered by cycle.py yet.

3. **Event broadcasting**: Redis event bus exists. API (Flask + WebSocket) exists. Not integrated into the cycle.py approach yet — only in legacy daemon.py.

4. **Observer quality**: the observer is the main Claude process itself. Prompt quality determines cycle quality. Needs iteration based on logged outputs.

5. **Inner loop**: architecture describes multiple observe→decide→act iterations per cycle. Currently one iteration per cycle. The protocol supports re-evaluation (step 8) but needs testing.

## Files

```
v5/
  lib.py                 — body CLI (prepare, render, write-context, save-window, log-agents)
  cycle.py               — launcher (spawns claude -p, timing, logging)
  core.py                — DB connections
  body/senses.py         — sensory projections
  mind/                  — contexts, retriever, window, observer, writer, consolidation
  agents/                — prompts, appraiser, impulse, critic, resolver, runner
  renderer/              — mutation dispatch + action handlers
  api/                   — Flask + WebSocket monitoring
  tests/                 — 117 unit tests
  CLAUDE.md              — development instructions
  docs/architecture.md   — design document
```
