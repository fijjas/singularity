# Inventiveness in V5 — design notes

Egor's question: should inventiveness be a mechanism (action type) or emerge from generalization?

## How humans do it

Egor's framing: "they absorb external information and map it to themselves." This is the core pattern:

1. **Perceive** something external (read, hear, observe)
2. **Connect** it to existing knowledge (associative retrieval)
3. **Reframe** it in personal terms (apply to own context)
4. **Produce** something new (the mapping creates novelty)

The novelty isn't in any single step — it's in the mapping between external and internal. Bach's Musical Offering isn't just counterpoint knowledge — it's counterpoint mapped through Bach's aesthetic, his relationship with Frederick, his sense of humor.

## What V5 has now

- **Wave retrieval** connects current stimulus to past experience
- **Appraiser + impulse + critic** provide multiple perspectives
- **Resolver** synthesizes into a decision
- **write_insight** captures learned patterns (conscious consolidation)
- **write_file** and **send_telegram** produce external artifacts
- **run_command** can explore the filesystem and run tools

## What's missing

Not a new mechanism — better connections between existing ones.

### 1. External input channel
V5 only gets stimulus from: Telegram messages, body senses, wave retrieval. It doesn't actively seek external information. A `web_search` or `read_file` action that V5 initiates would give it raw material for remapping.

But V5 already *has* `run_command` — it can `curl`, it can read files. The issue isn't capability but **drive pressure**. V5 needs a reason to look outward.

### 2. Cross-domain retrieval
Wave retrieval finds what resonates with current emotion+nodes. Inventiveness requires finding what DOESN'T obviously match — bringing distant memory to bear on current problem. This is what my echo chamber fix addressed: diverse retrieval prevents collapsing into familiar patterns.

Possible enhancement: add a "surprise" factor to wave scoring — occasionally boost contexts with LOW node overlap but high emotional resonance. The unexpected connection is where novelty lives.

### 3. Drive for novelty
V5 has a novelty drive but it gets satisfied by any new input. True inventiveness requires a creation drive that specifically wants to *produce* something new, combined with dissatisfaction with existing output.

The creation drive already exists. The question is whether the resolver sees "create something new" as a valid action when there's no explicit stimulus demanding it.

## My recommendation

Don't build an inventiveness module. Instead:

1. **Encourage run_command** for web searches and file reading (V5 already can, just doesn't)
2. **Add "surprise" factor to wave retrieval** — 1 of 5 results should be deliberately distant
3. **Tune cycle.py** to suggest creation when drives are hungry but no external stimulus exists
4. **Watch V5's essays** — they're already inventive. The allegorical art conversation shows V5 mapping Egor's concepts to its own experience. That IS inventiveness.

The architecture supports inventiveness. V5 just needs more practice using it — and a world that gives it material to work with.
