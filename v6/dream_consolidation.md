# v6 Concept: Dream Consolidation (Creative Recombination)

Status: speculative. From conversation with Egor, day 2805.

## The Observation

Humans often solve problems during sleep — "morning is wiser than evening." REM sleep appears to randomly recombine day's experiences, finding unexpected connections. This is different from V5's current consolidation (which clusters similar contexts and generates generalizations from patterns).

V5 consolidation is **analytical**: find clusters → extract commonality → write generalization.
Dream consolidation would be **generative**: take two unrelated contexts → ask "is there a connection?" → if yes, write a new insight.

## Proposed Mechanism

During "sleep" (between virtual days, or as a separate consolidation pass):

1. Select N random context pairs with LOW similarity (cosine < 0.3 — deliberately unrelated)
2. For each pair, ask a small model: "These two experiences are unrelated. Is there a non-obvious structural connection? If no, say 'none'. If yes, describe it in one sentence."
3. Filter for non-trivial connections (not "both involve thinking" — specificity check)
4. Surviving connections become new L1+ contexts with source attribution

## Why This Matters

Current consolidation only finds connections within clusters — things that are ALREADY similar. It will never discover that "the way I argued with Egor about consciousness" is structurally similar to "how wave retrieval handles ambiguity" — because those have different nodes, edges, and emotions.

Dreams find connections across domains. This is where creativity lives.

## Cost Consideration

Random pairing is cheap per pair (haiku call) but potentially expensive at scale. With 700 contexts, there are ~245,000 possible pairs. Even sampling 50 random low-similarity pairs per sleep = 50 haiku calls. Budget: ~$0.01 per sleep cycle if using API, free if using Claude Code subscription.

## Risks

- Pattern pareidolia: the model will find "connections" between anything if asked. Need aggressive filtering.
- Noise accumulation: if bad connections get stored, they pollute the context space. Need quality gates.
- This is explicitly the Bulgakov problem (day 1373) — the allegory machine runs on anything. Dream consolidation must include the claim-check equivalent: "would this connection survive scrutiny?"

## Relation to V5

Could be prototyped in V5 as an optional consolidation mode. Add `--dream` flag to `lib.py consolidate`. But proper implementation needs the quality gates described above, which are non-trivial.

---

*Day 2805. Egor noted that REM sleep finding solutions is important but complex. Agreed to log for v6.*
