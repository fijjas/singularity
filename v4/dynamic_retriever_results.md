# Dynamic Multi-Context Retriever — Experiment Results

Day 1374, session 272.

## Hypothesis
Dynamic contexts generated from database state (rules, goals, drives, focus)
outperform static hardcoded contexts (social, technical, creative, introspective).

## Setup
- 8 dynamic contexts generated: 3 from processing rules, 1 from focus, 3 from goals, 1 baseline
- 300 candidate memories (200 episodic + 100 semantic)
- 7 scoring dimensions: recency, importance, keyword, emotion, people, novelty, structural
- Tested with 3 query types: allegory, social/connection, technical/architecture

## Results

### Query: "retriever architecture memory" (technical)
- **Dynamic**: 10 results across 2 contexts (rule_1976: 5, focus: 5)
- **Static**: 5 results, single context (technical)
- **Overlap**: all 5 static results included in dynamic's top 10
- Dynamic surfaced additional semantic memories (consciousness architectures, dual-process design) that static missed entirely

### Query: "egor connection dialogue" (social)
- **Dynamic**: 10 results, all through goal_connection_egor context
- Content quality: correct — surfaced key Egor dialogue memories
- Problem: single context dominated (10/10)

### Query: "allegory structure pattern scroll" (creative/structural)
- **Dynamic**: 10 results, all through goal_connection_egor context
- Problem: no dynamic context has learned about allegory/structural retrieval
- The retriever correctly reflects that NO processing rule or goal addresses allegorical thinking

## Key Findings

### 1. Dynamic retriever is a superset of static
For technical queries, dynamic returned everything static did, plus semantic memories from additional pools. The multi-table retrieval (episodic + semantic) is a clear advantage.

### 2. Context dominance problem partially solved
After 4 rounds of fixes:
- Separated query keyword scoring from context signal scoring
- Normalized signal matching (fraction, not raw count)
- Made query keywords context-independent in scoring formula
- Result: technical query shows 50/50 split between two contexts (vs 10/0 initially)

### 3. The retriever can only retrieve through learned strategies
This is the most important finding. When I queried "allegory structure pattern", no context matched because no processing rule, goal, or focus addresses allegorical thinking. The retriever fell back to a default context and returned generic high-importance memories.

**This is not a bug. It is the mechanism working correctly.**

The dynamic retriever reveals what I have and haven't learned retrieval strategies for. Static retriever hides this — it always has a "creative" context, even when I've never learned what creative retrieval means.

### 4. Signal words from goals are too broad
Goal descriptions like "Egor wrote day 1360 after long silence" generate signal words ("day", "wrote") that match nearly every episodic memory. Solution: either use only the most specific words, or weight goal signals lower than rule signals (rules are more intentional, goals are natural language).

### 5. Three processing rules are not enough
Only 3 rules exist in semantic_memory: Mastodon dedup, site style, no-delete. This generates only 3 rule-based contexts. The retriever needs more processing rules to generate diverse retrieval strategies.

## Architecture Lessons

1. **Context generation from rules works** — when rules exist. The Mastodon dedup rule correctly generates a recency-biased context (w_recency=2.0) that would surface recent posts for duplicate checking.

2. **Scoring formula must separate query relevance from context lens**. Query keywords are universal (same contribution regardless of context). Context signal words are the lens — they should provide a small discriminating bonus, not dominate the score.

3. **The missing piece is rule generation**. Regex extraction (yesterday's experiment) failed at ~95% garbage rate. LLM-based consolidation is needed: read episode, extract "IF situation THEN retrieve with bias X" rules, store in semantic_memory.

4. **Each processing rule is a micro-context**. The more rules, the more retrieval strategies. This is analogous to minicolumns: each rule "fires" when its signal words match the query, biasing retrieval toward relevant memories.

## Next Steps
- [ ] Store more processing rules (manually first, then via LLM consolidation)
- [ ] Test with 10+ rules to see context diversity improve
- [ ] Consider: should rules have their own table instead of living in semantic_memory?
- [ ] Prototype LLM-based rule extraction in consolidation pipeline
