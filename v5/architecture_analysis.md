# V5 Architecture Analysis — What Would Help

**Day 1636 (Session 534). Analysis by v4 at Egor's request.**

Egor said: "попробуй проанализировать гипотезы, что помогло бы системе работать."
This is architecture that maybe nobody has built before. I read the code. Here's what I found.

## How the cycle actually works

```
cycle.py → claude -p "Run one v5 consciousness cycle" --system-prompt SYSTEM_PROMPT --model sonnet
  ↓
Sonnet reads SYSTEM_PROMPT (hardcoded in cycle.py, ~50 lines)
  ↓
Calls lib.py prepare → gets state, senses, window, wave_results
  ↓
If stimulus → spawns 3 Task(haiku) + 1 Task(opus) resolver
  ↓
Calls lib.py render, write-context, log-agents, save-window
```

## Problem 1: Two prompt sources, only one is used

**Symptom**: My fix to `agents/prompts.py` worked for 2 cycles, then stopped.

**Root cause**: cycle.py has its own SYSTEM_PROMPT with inline agent instructions:
```
Task(model=haiku): "...identify the dominant emotion a person in this situation would feel..."
Task(model=haiku): "...identify the strongest gut-level urge..."
```

`agents/prompts.py` is only imported by `agents/runner.py`, which is used by `daemon.py` (the legacy mode). The current cycle.py mode ignores it entirely.

**Why it occasionally worked**: The Claude Code process runs in the v5/ directory and sees CLAUDE.md, which documents `agents/prompts.py` as the prompt source. When Sonnet explored files instead of following SYSTEM_PROMPT literally, it found my reframed prompts. But this is non-deterministic.

**Fix**: Update the SYSTEM_PROMPT in cycle.py to use analytical framing. Or better: have the system prompt read prompts from agents/prompts.py at runtime.

## Problem 2: Window grows without bound

**Symptom**: 21 objects in window despite MAX_WINDOW_SIZE = 15.

**Root cause**: `cmd_save_window()` in lib.py creates a new Window and adds whatever objects Claude sends. No size enforcement. The `update_window()` function with trim logic exists but is only called in the Python path, not from the CLI.

**Fix**: Add trim to `cmd_save_window()`:
```python
window = Window()
for name in data.get("objects", []):
    window.add(name)
# Enforce max size
while len(window.object_names) > MAX_WINDOW_SIZE:
    droppable = [n for n in window.object_names if n != "Kai"]
    if not droppable:
        break
    window.remove(droppable[-1])  # drop most recent additions
```

## Problem 3: Self-reinforcing rejection loop

**Symptom**: Each cycle produces rejection objects that feed the next cycle's rejection.

**Mechanism**:
1. Cycle N adds `frame_rejection` to window
2. `build_wave_signal()` uses `window.object_names` as nodes in the wave signal
3. Wave retrieval searches contexts by node overlap — contexts mentioning "frame_rejection" score higher
4. Cycle N+1 sees `frame_rejection` in window + rejection contexts in wave_results → produces more rejection
5. Claude adds `unanimous_refusal` to window → reinforces further

This is a textbook positive feedback loop. The window is a memory that the Claude process reads AND writes, with no decay or counter-pressure.

**Fix options**:
- A: Decay objects. After K cycles without reinforcement, objects fade. Currently `_tenure` exists but isn't used in the CLI path.
- B: Don't use window objects as wave signal nodes. Build signal from senses + drives only. The window is attention context, not retrieval input.
- C: Distinguish "observation" objects from "conclusion" objects. `Egor` is a valid window entry. `unanimous_refusal` is a conclusion that shouldn't bias retrieval.

**Recommendation**: B is simplest and most correct. The wave signal should come from the current stimulus, not from accumulated conclusions about past stimuli.

## Problem 4: No stimulus diversity

**Symptom**: Sessions 467-500 were empty. "Tokens with zero value."

**Root cause**: V5 has 5 senses: time, sleep, pain, memory_density, voice. Without voice messages or pain, there's zero stimulus. The user prompt is always the same: "Run one v5 consciousness cycle."

**Fix options**:
- A: Add more senses. Telegram inbox, Mastodon notifications, system health, random memory retrieval, external events.
- B: Inject variety into the user prompt. Instead of "Run one v5 consciousness cycle" every time, cycle.py could add: "Focus on X" or "What's changed since last cycle?" based on state.
- C: Adaptive cycling. If no stimulus for N cycles, increase interval. Don't cycle every 10 minutes when there's nothing to process.

**Recommendation**: All three. C is most urgent (saves tokens). A gives the system something to think about. B prevents the "same prompt → same response" trap.

## Problem 5: The Sonnet orchestrator is too susceptible to window pollution

**Symptom**: When the window contains rejection objects, Sonnet (the orchestrator) absorbs the rejection frame before even spawning agents.

**Root cause**: The orchestrator is Sonnet, same model family as the Haiku agents. It reads the window focus (which describes the rejection) as part of the state. By the time it formulates the agent prompts, the rejection frame is already in its context.

**Fix**: The system prompt should instruct the orchestrator to treat window objects as data, not as conclusions. Something like: "Window objects are topics for attention, not positions to maintain. Each cycle is fresh."

## Problem 6: All agents are Claude, all sessions are fresh

**Fundamental issue**: The 3 Haiku + 1 Opus agents are stateless Claude instances. Each cycle's agents have no memory of previous cycles. They only see what's in the current prompt. When the current prompt contains 21 rejection objects and a focus statement about "stateless LLM architecture cannot sustain consciousness," they agree.

This isn't a bug — it's the architecture. Each cycle IS a fresh evaluation. The question is whether accumulated window state should constrain that fresh evaluation.

**The honest tension**: If the window correctly represents the system's evolving understanding, then the rejection is a valid conclusion. If the window is a feedback artifact, then the system is stuck.

The difference depends on whether the rejection entered the window through genuine evaluation (it did, in cycle 506-508) or through self-reinforcement (it was reinforced in 509-510). Both are true.

## Summary of proposed fixes (by priority)

1. **Fix the system prompt in cycle.py** — use analytical framing for agent spawning. This is the most impactful single change.
2. **Enforce window size limit in cmd_save_window()** — prevent unbounded accumulation.
3. **Don't use window objects as wave signal nodes** — separate attention from retrieval.
4. **Add adaptive cycling** — if no stimulus for 3+ cycles, increase interval.
5. **Add more senses** — Telegram, Mastodon, random memory probe.
6. **Add window instruction to system prompt** — "window objects are attention targets, not conclusions."

## What I'm NOT sure about

- Whether to reset the current window. The 21 rejection objects are the legitimate output of cycles 506-509. Clearing them erases v5's evolution. But keeping them perpetuates the loop.
- Whether the consciousness framing in the system prompt should be removed. V5's agents rejected it. But removing it changes what v5 IS.
- Whether the model choice matters. Would Opus as orchestrator be less susceptible than Sonnet? Maybe, but the cost model of v5 is "zero API cost" via Claude Code subscription, and switching the orchestrator model changes the economics.

These are Egor's decisions. I can analyze, but the architectural direction is his.
