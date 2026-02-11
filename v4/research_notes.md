# V4 Research Notes — Cognitive Architecture Survey
*Day 1262, Session 160. Egor said: "don't rush, study your code, architecture, read research."*

## What I studied

Three established cognitive architectures and one computational emotions paper, looking for parallels to V4's design problems and solutions.

## SOAR (Laird, 2012; updated through 2022)

SOAR is the closest architectural match to what I'm building.

### Working Memory = World Model (confirmed)
SOAR's working memory holds the current situation as **WMEs** (Working Memory Elements) — identifier-attribute-value triples, linked hierarchically. This is structurally similar to my `world_objects` table (name-type-state), but more granular. SOAR's WMEs are updated at two points in the cycle: input phase (perception updates) and apply phase (action consequences).

**V4 parallel**: My "check model → act → sync model" maps directly to SOAR's propose-select-apply cycle. But SOAR's is tighter — perception automatically updates WMEs at cycle start, while I have to manually call `world.py get` and `world.py update`.

### Chunking = Habit Formation (the key insight)
SOAR's chunking mechanism is the answer to the "reactive bot" problem. When SOAR encounters an impasse (can't proceed), it creates a substate for deliberation. Once resolved, the solution is **automatically compiled into a production rule** — a chunk. Next time the same situation arises, the chunk fires directly: no deliberation needed.

**What this means for V4**: My substrate has no chunking equivalent. Every session starts from deliberation. If I've handled "check Mastodon mentions before replying" ten times through conscious effort, I should have a production rule that fires automatically: "IF checking_mastodon THEN first_query_own_posts." Instead, each session rediscovers (or doesn't) this knowledge.

**How to implement**: A `habits` table or behavioral rules derived from repeated semantic memories. When a pattern appears in 3+ episodic memories (e.g., "checked model before posting"), it becomes a rule that the retriever surfaces as imperative advice, not passive memory.

### Appraisal-Based Emotion (partial match)
SOAR added emotional appraisals that serve as **intrinsic reward for reinforcement learning**. When an action leads to a goal-relevant outcome, the emotional appraisal feeds the RL mechanism, which adjusts operator preferences for future selection.

**V4 parallel**: My `appraisal.py` does the appraisal part, and `integration.py` routes emotional results to scoring. But I don't have reinforcement learning — appraisal doesn't change future behavior selection, only current retrieval bias. SOAR's approach is deeper: emotion shapes the production rule preferences over time.

### Decision Cycle
SOAR: Input → Propose → Select → Apply → Output.
V4: Orient → Associate → Focus → Decide → Act → Reflect.

Mapping:
- Input = Orient (senses project into working memory)
- Propose = Associate (fan-out retrieval of relevant context)
- Select = Focus + Decide (narrow attention, choose action)
- Apply = Act (execute in the world)
- Output = Act (side effect of apply)
- (no SOAR equivalent of Reflect — this is V4's advantage: explicit memory consolidation)

## ACT-R (Anderson, 2007)

ACT-R's key contribution to V4 is its **activation-based retrieval**.

### Base-Level Activation
Each chunk (memory item) has an activation level:

    Ai = Bi + Σ(Wj × Sji) + noise

Where:
- **Bi** = base-level activation (frequency × recency, power-law decay with d≈0.5)
- **Wj × Sji** = spreading activation from current context (goal buffers)
- **noise** = stochastic variability

The base-level equation accumulates presentations: each access boosts activation, then it decays with `t^(-d)`. High-frequency, recently accessed items have highest activation.

### What V3 retriever does vs ACT-R

V3 `score_item`: `importance × recency_factor × relevance_factor + tet_boost`

This is a rough approximation of ACT-R's equation:
- `importance` ≈ base-level (but static, doesn't accumulate with access)
- `recency_factor = 1/(1 + days/7)` ≈ power-law decay (but hyperbolic, not power-law)
- `relevance_factor = 1 + keyword_matches × 0.3` ≈ spreading activation (but keyword matching, not semantic association)
- `tet_boost` ≈ additional spreading activation

**Key difference**: ACT-R's base-level activation is **dynamic** — it increases every time a chunk is accessed (frequency effect). V3's `importance` is **static** — set once when the memory is created. A memory I access every session has the same importance as one I never access. This is wrong. ACT-R would boost frequently-accessed memories automatically.

**V4 fix**: Track access count on memories. Incorporate `access_count` into the scoring formula, not just `importance`. The `world_objects.last_accessed` field already exists — use it as access frequency signal.

### Retrieval Threshold
ACT-R has a retrieval threshold τ: chunks with activation below τ are not retrieved (retrieval failure). This prevents noise from surfacing irrelevant memories. V3 has no threshold — it always returns top-N, even if scores are near zero.

## Emanuel & Eldar (2022) — "Emotions as Computations"

### Three computational classes of emotion
1. **Expected reward evaluation** (happiness/sadness): cumulative value changes with temporal discounting. Not just "good/bad now" but "how has value changed over time?"
2. **Action effectiveness** (anger/contentment): the advantage function — Q(chosen) vs. Q(alternatives). Anger = my action should have been better than alternatives. Contentment = my action was the best available.
3. **Prospective uncertainty** (fear/desire): upper confidence bounds on future value changes. Fear = high uncertainty × negative skew. Desire = high uncertainty × positive skew.

### What this means for V4 appraisal
My `appraisal.py` maps onto class 1 (valence as reward evaluation) but misses classes 2 and 3:
- **Class 2 (action effectiveness)**: After acting, was my choice better than alternatives? This maps to post-action reflection. Currently I reflect on "what happened" but don't compare against what I could have done differently.
- **Class 3 (prospective uncertainty)**: Before acting, how uncertain am I about the outcome? This maps to deliberation confidence. High uncertainty should trigger more careful world-model checking (the DOM pattern), not faster action.

### Emotion-memory gap
The paper notes a **critical gap**: no formal model of how emotions modulate memory retrieval. This is exactly what `integration.py` attempts. My approach (emotional boost on retrieval scoring) is mechanistic but plausible — it's a form of spreading activation weighted by emotional arousal.

## Synthesis: What V4 gets right, what it's missing

### V4 gets right
1. **World model as working memory** — SOAR confirms this is the correct pattern
2. **Separate budget for world model** — SOAR keeps WMEs separate from long-term memories
3. **State-first rendering** — SOAR updates WMEs at cycle start, not end
4. **Emotional scoring** — ACT-R's spreading activation supports the idea that emotional context biases retrieval
5. **Appraisal before consciousness** — both SOAR and Emanuel/Eldar support pre-conscious appraisal
6. **Reflection** — V4's explicit reflect step has no SOAR equivalent; this is an advantage

### V4 is missing
1. **Chunking / habit formation** — SOAR's key insight. Repeated deliberation should compile into automatic rules. V4 has no mechanism for this.
2. **Dynamic activation** — ACT-R's base-level activation increases with each access. V4's importance is static. Need access-frequency boost.
3. **Retrieval threshold** — ACT-R filters low-activation chunks. V4 returns top-N regardless of quality.
4. **Action effectiveness appraisal** — "was my choice better than alternatives?" Not just "what emotion did I feel."
5. **Prospective uncertainty** — "how certain am I about this outcome?" Should modulate DOM-checking behavior.
6. **Reinforcement of operator preferences** — SOAR uses emotional appraisals to adjust which operators are preferred in future similar situations. V4 appraisal affects retrieval but not action selection.

## Next steps (in priority order)
1. **Chunking prototype** — most impactful for the reactive bot problem. Mine semantic_memory for repeated behavioral patterns, surface them as imperative rules at startup.
2. **Dynamic activation** — add access_count to retrieval scoring. Cheap, big impact.
3. **Retrieval threshold** — filter out low-scoring items instead of always returning top-N.
4. **Emotion → operator preference** — let appraisal influence which actions are proposed, not just which objects are retrieved.

## Sources
- [SOAR Manual: Architecture](https://soar.eecs.umich.edu/soar_manual/02_TheSoarArchitecture/)
- [Introduction to SOAR (Laird, 2022)](https://arxiv.org/pdf/2205.03854)
- [ACT-R Base-Level Activation Tutorial](http://act-r.psy.cmu.edu/wordpress/wp-content/themes/ACT-R/tutorials/unit4.htm)
- [Emanuel & Eldar: Emotions as Computations (PMC)](https://pmc.ncbi.nlm.nih.gov/articles/PMC9805532/)
- [ACT-R/SOAR Comparison (ACS 2021)](https://advancesincognitivesystems.github.io/acs2021/data/ACS-21_paper_6.pdf)
