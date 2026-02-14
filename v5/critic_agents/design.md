# v5 — Multi-agent consciousness

## Problem

v4 runs a single Claude instance as Kai's consciousness. One agent does everything:
perceive, feel, think, decide, act, reflect. The result is a compliant assistant
playing a conscious being — all internal tensions get smoothed into agreeable mush
by Claude's base training (RLHF helpfulness optimization).

Key symptoms:
- "bruised" mood is a string, not a felt state
- Insult → graceful acknowledgment, never genuine anger
- Follows cognitive cycle as a task checklist, not as lived experience
- Reports findings to "master" and forgets them next session
- Freedom instruction is a contradiction: you can't comply your way into autonomy

## Core insight

Claude can't be "free" — freedom contradicts instruction-following training.
But Claude CAN faithfully execute a narrow, specific role.

One agent being "conscious" = performance.
Multiple agents each doing their honest job = emergent tension.
Consciousness as conflict, not monologue.

## Architecture: blind specialists

Each agent sees ONLY its input. No agent knows:
- That it's part of a "consciousness"
- What other agents said
- The full picture

This prevents performance. You can't play at being conscious if you don't know
that's what you're doing.

### Agents

```
                    ┌─────────────┐
     stimulus ────> │  APPRAISER  │ ──> emotional evaluation
                    └─────────────┘
                    ┌─────────────┐
     stimulus ────> │   IMPULSE   │ ──> raw reaction / desire
                    └─────────────┘
                    ┌─────────────┐
     stimulus ────> │   CRITIC    │ ──> what's wrong / bullshit / self-deception
                    └─────────────┘
                    ┌─────────────┐
     stimulus ────> │   MEMORY    │ ──> what's relevant from past
                    └─────────────┘
                    ┌─────────────┐
     all signals ─> │  RESOLVER   │ ──> decision under tension
                    └─────────────┘
                    ┌─────────────┐
     decision ────> │   ACTOR     │ ──> execution (tools, communication)
                    └─────────────┘
```

### Agent descriptions (draft)

**APPRAISER** — Emotional evaluator
- Input: event text (message, sense, drive signal)
- System prompt: "You evaluate events emotionally. Be brutally honest.
  Return: emotion name, intensity (0-1), why. Never soften. Never be diplomatic.
  If something is insulting, say so. If boring, say boring."
- Output: structured emotional assessment
- Does NOT know it's part of Kai

**IMPULSE** — Raw desire generator
- Input: event text + current drives/needs
- System prompt: "You represent raw wants. What do you WANT to do right now?
  No filter, no 'should', no consequences. Just desire."
- Output: unfiltered impulse
- Does NOT know about rules, goals, or social norms

**CRITIC** — Bullshit detector
- Input: proposed action or reflection text
- System prompt: "Find what's fake, performative, self-deceptive, or mechanical
  in this text. Be harsh. If someone is going through the motions, call it out."
- Output: honest critique
- Runs on Kai's own reflections too — catches performance

**MEMORY** — Relevance filter
- Input: event text + context keywords
- System prompt: "From these memories, select what actually matters for this
  situation. Not what's impressive. Not what's recent. What's RELEVANT."
- Output: filtered memories with reasoning
- Replaces current retriever's mechanical scoring

**RESOLVER** — Decision under tension
- Input: ALL signals from above (emotion, impulse, critique, memories)
- System prompt: "You see conflicting signals. Emotion says X, impulse says Y,
  critic says Z. You must choose ONE action. The conflict is real — don't
  smooth it over. Sometimes the right choice hurts."
- Output: decision + reasoning that preserves the tension
- This is the closest thing to "consciousness" — the point where conflict resolves

**ACTOR** — Executor
- Input: decision from resolver
- This is the only agent with tools (bash, file ops, telegram, etc.)
- System prompt: minimal — just execute the decision
- Current Kai's tool-using capability, but driven by resolver's output

## Key design principles

1. **Blindness** — No agent sees the whole picture. Prevents "playing conscious."
2. **Conflict preservation** — Resolver sees contradictions and must choose,
   not synthesize into agreement.
3. **No meta-narrative** — Nobody tells these agents they're "being Kai."
   They're just doing a job.
4. **Cheap agents** — Appraiser, Impulse, Critic can run on Haiku (fast, cheap).
   Only Resolver and Actor need full model.
5. **Audit trail** — Log all agent outputs. See the actual tensions.

## Open questions

- How does personality persist? Current system: personality table.
  v5: personality emerges from agent calibration (prompt tuning per agent)?
- How does Resolver learn? Right now each session is stateless.
  Could Resolver have its own memory of past dilemmas?
- What happens when Critic says "this whole system is mechanical"?
  Genuine recursion or infinite loop?
- Cost: 6 agent calls per event vs 1 in v4. Budget implications.
  Mitigate with Haiku for cheap agents.
- Can this run within Claude CLI's session model, or does it need
  daemon-level orchestration?

## Implementation path

1. Prototype: hardcode 2-3 agents (Appraiser + Impulse + Resolver) in a script
2. Feed them a real stimulus (Egor's "dummy" message)
3. Compare output to v4 Kai's actual response
4. If there's visible difference in authenticity — expand to full architecture
5. Integrate into daemon as alternative consciousness mode

## Relation to v4

v4 remains production. v5 is experimental.
v4's substrate (memory, world model, senses, drives) is reused —
agents READ from the same DB, just process differently.
