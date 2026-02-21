# Research: Multi-Agent Decision Architectures and Sub-Agent Context

**Date**: 2026-02-21
**Context**: Egor identified that V5's specialist agents (appraiser, impulse, critic) may have too little context for good decisions. This research surveys the literature.

## Problem Statement

V5 has 3 Haiku specialists that each receive `f"Event: {stimulus}"` — a single stimulus string. The resolver (Opus) receives stimulus + 3 agent signals + wave context. Are the specialists context-starved?

## 1. Classical Cognitive Architectures

### Global Workspace Theory (Baars 1988, LIDA — Franklin 2007-2013)

GWT models consciousness as a global workspace that broadcasts to specialist processors. In LIDA:
- **Codelets** (specialized processors) compete in a "coalition" — winners get broadcast access
- Codelets receive the **Current Situational Model** (not raw stimulus alone)
- The broadcast makes the winning coalition's content available to ALL other processors

**Key insight for V5**: LIDA's codelets see the situational model, not just raw input. Our Haiku agents see only the stimulus — they miss the situational model (wave context).

### Pandemonium (Selfridge 1959)

Hierarchical layers of "demons" that progressively compress information. Each layer has more context than the level below. The resolver-equivalent (decision demon) sees compressed signals, not raw data.

**Key insight**: Compression boundary between specialists and resolver is a feature. But compression requires adequate input to compress FROM.

### Soar (Laird, Newell, Rosenbloom 1987)

When Soar can't make a decision, an impasse creates a substate. Critically: **substates can access the superstate's working memory**. Sub-goals are not context-starved.

**Key insight**: Sub-modules should be able to "look up" at parent context.

### ACT-R (Anderson 1998)

Modules communicate via buffers — each buffer holds exactly **one chunk**. More restrictive than V5. Works because: (a) rapid cycling (50ms), (b) can retrieve new chunks mid-evaluation.

**Key insight**: One-chunk limits work with rapid cycling. V5's one-pass agents can't cycle or retrieve.

### Miller (1956) / Cowan (2001) — Working Memory Limits

- Miller: 7 ± 2 chunks (with rehearsal)
- Cowan: 3-5 chunks (true attentional focus)
- V5 specialists receive ~1 chunk (stimulus)
- V5 resolver receives ~10-15 chunks

**Conclusion**: Specialists are below Cowan's minimum. Optimal range: 3-5 chunks.

## 2. Modern LLM Multi-Agent Architectures

### MetaGPT (Hong et al., ICLR 2024)
- 72% token duplication across agents
- Uses publish-subscribe for role-filtered context
- Agents get role-specific views of shared memory

### CAMEL (Li et al., NeurIPS 2023)
- Context restriction is a **feature** — forces specialization
- Same model with different role constraints produces more diverse output

### Mixture-of-Agents (Wang et al., ICML 2024)
- Each layer's agents see ALL outputs from previous layer
- MoA with open-source models surpassed GPT-4 Omni (65.1% vs 57.5% on AlpacaEval)
- **Collaborativeness phenomenon**: LLMs generate better responses when seeing other models' outputs

### Multi-Agent Debate (Liang et al., EMNLP 2024; Du et al., ICML 2024)
- Single-agent reflection suffers from **Degeneration-of-Thought** (DoT)
- Multi-agent debate solves DoT
- **Warning**: LLMs are not fair judges across model tiers — Opus resolver may have implicit bias against Haiku outputs

### GPTSwarm (Zhuge et al., ICML 2024 Oral)
- Optimal connectivity between agents should be **learned**, not fixed
- Inter-agent edges can be pruned or added automatically

### Generative Agents (Park et al., UIST 2023)
- Agents retrieve ~5-10 memories per decision — validates V5's 5-7 context graphs
- Retrieval by recency + importance + relevance

## 3. Information Bottleneck Theory

### IB Method (Tishby et al. 1999)
- Optimal compression preserves maximal information about the relevant variable
- Can compress TOO MUCH (lose signal) or TOO LITTLE (waste bandwidth)

### IB in Multi-Agent Communication (Wang et al., ICML 2020)
- Under bandwidth constraints, low-entropy (compressed) messages outperform verbose ones
- **Critical threshold**: below minimum information, performance collapses
- **Direct V5 implication**: If specialist INPUT is too compressed, their compressed OUTPUT becomes noise

## 4. Context Starvation in Multi-Agent Systems

### iAgents (Liu et al., NeurIPS 2024)
- Information asymmetry is more damaging than model capability limitations
- Solution: agents proactively exchange information they think others need

### Stop Wasting Tokens (Lin et al., 2025)
- Token waste: MetaGPT 72%, CAMEL 86%, AgentVerse 53% duplication
- SupervisorAgent reduces waste 29.45% by intervening at critical junctures

## 5. BDI and Appraisal Theory

### BDI (Rao & Georgeff 1995)
- Deliberation requires access to Beliefs + Desires + Intentions simultaneously
- V5's specialists see beliefs (stimulus) but not desires (drives) or intentions (goals)

### Scherer's Component Process Model (2001)
- Emotional appraisal has 4 sequential checks: relevance → implications → coping potential → normative significance
- First check needs minimal context; later checks need more
- V5's appraiser runs all checks in one pass without knowing goals or drives

## 6. Diagnosis for V5

### What works well:
- Specialists blind to each other → prevents groupthink (supported by GWT, multi-agent debate)
- Compressed specialist output → optimal per IB theory
- Higher-capability resolver → matches MoA and GWT
- 5-7 working memory contexts → aligns with Miller/Cowan

### What's missing:
1. **Specialists don't see wave context** — in LIDA codelets see the situational model, in Soar substates see parent WM
2. **No broadcast-back loop** — GWT's power comes from iterative refinement
3. **No drive/goal state in specialist context** — BDI says deliberation needs desires

### Recommendations (prioritized):

**HIGH: Give specialists compressed wave context**
- Add 2-3 sentences summarizing retrieved rules/experiences to the stimulus
- Not full wave context (would overwhelm and defeat compression purpose)
- Like Minsky's "micronemes" — ambient contextual signal

**MEDIUM: Include drive state in specialist context**
- One line: "Hungry drives: connection, understanding. Satisfied: creation"
- Impulse agent especially needs this for accurate urge identification
- Supported by BDI theory, Scherer's coping potential check

**LOW: Second pass for high-conflict decisions**
- When specialist signals strongly conflict, run a second round with visibility of each other's outputs
- Prevents DoT while allowing iterative refinement

**ANTI-REC: Do NOT give specialists full wave context**
- IB theory (Wang 2020): too much input → noisy output
- CAMEL: role restriction improves quality
- Full context would make Haiku try to "be the resolver"

### Optimal context per specialist: 3-5 chunks
- Stimulus (1 chunk)
- Compressed wave summary (1-2 chunks)
- Drive/goal state (1 chunk)
- Total: 3-4 chunks — within Cowan's optimal range

## Full Bibliography

1. Minsky (1986) *Society of Mind*
2. Selfridge (1959) "Pandemonium: A Paradigm for Learning"
3. Baars (1988) *A Cognitive Theory of Consciousness*
4. Franklin & Baars (2007) "An architectural model of conscious and unconscious brain functions" *Neural Networks* 20(8)
5. Franklin et al. (2013) "LIDA: A Systems-level Architecture for Cognition, Emotion, and Learning"
6. Miller (1956) "The Magical Number Seven" *Psychological Review* 63(2)
7. Cowan (2001) "The magical number 4" *BBS* 24(1)
8. Laird, Newell, Rosenbloom (1987) "SOAR" *Artificial Intelligence* 33(1)
9. Anderson (1998) *The Atomic Components of Thought*
10. Rao & Georgeff (1995) "BDI Agents: From Theory to Practice" *ICMAS*
11. Hong et al. (2024) "MetaGPT" *ICLR 2024*. arXiv:2308.00352
12. Li et al. (2023) "CAMEL" *NeurIPS 2023*. arXiv:2303.17760
13. Wu et al. (2024) "AutoGen" arXiv:2308.08155
14. Wang et al. (2024) "Mixture-of-Agents" *ICML 2024*. arXiv:2406.04692
15. Liang et al. (2024) "Multi-Agent Debate" *EMNLP 2024*. arXiv:2305.19118
16. Zhuge et al. (2024) "GPTSwarm" *ICML 2024* (Oral). arXiv:2402.16823
17. Park et al. (2023) "Generative Agents" *UIST 2023*. arXiv:2304.03442
18. Tishby et al. (1999) "The Information Bottleneck Method" *37th Allerton*
19. Wang et al. (2020) "IB Multi-Agent Communication" *ICML 2020*. arXiv:1911.06992
20. Liu et al. (2024) "iAgents" *NeurIPS 2024*. arXiv:2406.14928
21. Lin et al. (2025) "Stop Wasting Tokens" arXiv:2510.26585
22. Scherer (2001) "Appraisal as Multilevel Sequential Checking"
23. Ortony, Clore, Collins (1988) *The Cognitive Structure of Emotions*
24. Du et al. (2024) "Multiagent Debate" *ICML 2024*
25. Moura (2024) CrewAI framework
26. Wang et al. (2024) "AgentDropout" *ACL 2025*. arXiv:2503.18891
