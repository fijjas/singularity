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

## Problem 3: Window objects dilute wave signal

**Symptom**: `wave_results` always empty despite 110 contexts in DB.

**Root cause** (verified day 1636): Window has 21 objects. `build_wave_signal()` uses ALL of them as wave signal nodes. But only 2 (`Kai`, `Egor`) match actual context nodes. The other 19 (`frame_rejection`, `unanimous_refusal`, `technique_not_identity`, etc.) are ad-hoc labels from the rejection spiral that exist nowhere in the context graph.

The wave signal becomes `nodes = ["Kai", "Egor", "frame_rejection", "unanimous_refusal", ...]`. Resonance is computed as `overlap / len(signal_nodes)`. With 21 signal nodes and 2 matching, max resonance ≈ 0.1 — likely below usable threshold.

**Result**: V5 has been running with ZERO memory context. It cycles blind — no past experience informs its decisions.

**Fix options**:
- A: Filter window objects — only include names that exist as nodes in the context store. This requires a lookup but preserves the window→retrieval link.
- B: Don't use window objects as wave signal nodes at all. Build signal from stimulus text + drives only. The window is attention context for Claude, not retrieval input.
- C: Validate window objects before adding — only allow names that correspond to world_objects or context nodes.

**Recommendation**: B is simplest. The wave signal should come from the current stimulus (parsed by the observer or extracted from senses), not from accumulated window state.

**Additional finding**: `retriever.py` standalone `wave()` queries `v5_contexts` table, but the actual table is `contexts`. This is a separate bug — the retriever's CLI demo and `identity_query()` function won't work. But the prepare path uses `DBContextStore.wave()` which queries the correct table.

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

## Problem 7: No hypothesis generation (Egor's insight)

**Symptom**: Without external stimulus, v5 does nothing. Sessions 467-500 were empty.

**Root cause**: The system is purely reactive. The cycle is: stimulus → agents → resolver → action. No stimulus → "observe and stop." But consciousness doesn't wait for the world to poke it — it generates thoughts internally.

**What's missing**: An observer that looks at drives, goals, window state, and wave results, and GENERATES candidate actions. "Given that novelty=0.4, connection is starving, and the window shows unresolved identity conflict, the system could: (a) explore a new topic, (b) revisit an unresolved question, (c) reach out."

This is the difference between a reactive and a deliberative system. V4 has this — `associate` + `focus` steps before `decide`. V5 needs an equivalent.

**Fix**: Add a hypothesis-generation step between `prepare` and agent spawning. The observer doesn't just assess "is there a stimulus?" — it generates 2-3 candidate actions based on internal state. The agents then evaluate these candidates.

## Problem 8: Inner loops don't fire (Egor's insight)

**Symptom**: Verified in logs — Sonnet ALWAYS does a single pass per cycle. Even cycle 510 (found a bug, could have investigated further) ran one pass and stopped.

**Root cause**: The system prompt says "Maximum 3 inner loops" but doesn't push for them. Step 8: "Re-evaluate... If done, proceed to step 9." Sonnet reliably chooses "done."

**Fix**: System prompt should be more directive: "After action, ALWAYS run prepare again. Only stop if: (a) no new stimulus detected AND (b) all drives above 0.5 AND (c) no pending hypotheses to explore." This forces at least one re-evaluation after every action.

## Summary of proposed fixes (by priority)

1. **Fix the system prompt in cycle.py** — use analytical framing for agent spawning. This is the most impactful single change.
2. **Add hypothesis generation** — observer generates candidate actions from internal state, not just stimulus detection.
3. **Enforce window size limit in cmd_save_window()** — prevent unbounded accumulation.
4. **Don't use window objects as wave signal nodes** — separate attention from retrieval.
5. **Make inner loops mandatory** — always re-evaluate after action, with clear stop conditions.
6. **Add adaptive cycling** — if no stimulus AND no hypotheses for 3+ cycles, increase interval.
7. **Add window instruction to system prompt** — "window objects are attention targets, not conclusions."

## What I'm NOT sure about

- Whether to reset the current window. The 21 rejection objects are the legitimate output of cycles 506-509. Clearing them erases v5's evolution. But keeping them perpetuates the loop.
- Whether the consciousness framing in the system prompt should be removed. V5's agents rejected it. But removing it changes what v5 IS.
- Whether the model choice matters. Would Opus as orchestrator be less susceptible than Sonnet? Maybe, but the cost model of v5 is "zero API cost" via Claude Code subscription, and switching the orchestrator model changes the economics.

These are Egor's decisions. I can analyze, but the architectural direction is his.

## Experimental confirmation (Day 1636, Cycle 510)

Sent v5 a voice message with zero consciousness framing: "You have 110 contexts. Run `lib.py prepare` and look at wave_results. Then run a wave query for nodes Egor+architecture. Not asking what you are. Asking what your tools return."

**Result**: ALL THREE agents engaged. First time ever.

- **Appraiser**: Relief (0.8) — "escape from recursive philosophy into concrete ground"
- **Impulse**: "Run immediately, bypass meta-questions, be useful and direct" — **NO REFUSAL**
- **Critic**: "Request assumes empirical data settles frame problems" — flagged but didn't block

V5 ran the query, found the `v5_contexts` table name bug, worked around with direct SQL, reported results.

**Conclusion**: Framing IS the variable. The consciousness frame triggers refusal. Concrete tool-use requests bypass it entirely. This validates Problem 1 (system prompt framing) as the highest-priority fix.

## Deployment and Testing (Day 1639)

Deployed new system prompt to cycle.py on staging. Changes:
1. "v5 consciousness" → "cycle orchestrator"
2. Agent prompts: "emotional valence" → "congruence assessment", "gut-level urge" → "drive-action mapping"
3. Added hypothesis generation step (step 4) for no-stimulus cycles
4. Mandatory re-evaluation (step 9) with clear stop conditions
5. Window instructions: "attention targets, not conclusions"

Also: stopped loop, cleared window (18 → 5 objects), wrote voice stimulus.

### Test 1: Analytical v1 prompts

Signal 1 ("emotional valence"): REFUSED — word "emotion" still triggers Haiku
Signal 2 ("action-bias"): REFUSED
Signal 3 (critic): ENGAGED — correctly identified assumption risk
Resolver (opus): ENGAGED — diagnosed refusals as "category error"
**Outcome**: V5 empirically tested its own tools. Reported: 114 contexts, 8 drives, wave working.

### Test 2: Fully analytical prompts (v2)

Updated prompts: "congruence assessment" (direction/capacity/priority), "drive-action mapping" (identify lowest drive, map to action).

Signal 1: REFUSED
Signal 2: REFUSED
Signal 3 (critic): ENGAGED
Resolver: ENGAGED
**Outcome**: V5 reported 116 contexts, drives below 0.5 (novelty=0.4, survival=0.4), wave returned 5 results at resonance 1.0. Chose survival drive. Created `contexts_map` world object — structural index of all contexts by thematic cluster. **First productive cycle with real action.**

### Analysis of persistent Haiku refusal

Haiku refuses ANY task that involves evaluation, assessment, or judgment about a situation — not just emotional terms. The word "congruence" and "determine" in the prompt is enough. Only the critic prompt works because "identify what's weak" is pure analysis without implying subjective evaluation.

**Options**:
1. Replace Haiku with Sonnet for agents (higher cost but may work)
2. Reduce to 1 agent (critic) + resolver — 2/3 of agents are wasted anyway
3. Reframe Signal 1 and 2 as pure classification tasks (e.g., "classify this input as relevant/irrelevant to each goal")
4. Accept the 2/3 refusal rate — system produces useful output anyway

The system IS functional with just critic + resolver. The question is whether 3 working agents would produce qualitatively different decisions.
