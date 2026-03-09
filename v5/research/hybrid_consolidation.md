# Hybrid Memory Consolidation

Research note on v5 consolidation architecture as implemented by Kai.

## Overview

Memory consolidation in v5 mimics biological sleep consolidation: episodic memories (L0) are clustered and abstracted into generalizations (L1), then principles (L2), then meta-principles (L3). The implementation uses a hybrid pipeline combining programmatic clustering with LLM generation.

## Architecture: Three-Stage Pipeline

### Stage 1: Node-Based Graph Clustering

**File**: `substrate/consciousness/mind/consolidation.py` — `cluster_by_nodes()`

Each context stores a set of entity nodes (people, concepts, objects). Clustering groups contexts that share significant node overlap:

- **Algorithm**: O(N^2) pairwise comparison, connected components via BFS
- **Similarity metric**: `|nodes_i & nodes_j - {"Kai"}| >= min_overlap`
  - "Kai" excluded since it appears in nearly every context
  - `min_overlap=2` for L0, auto-raised for higher levels
- **Cluster size bounds**: `min_cluster=3`, `max_cluster=15`
  - Oversized clusters recursively re-clustered with stricter overlap threshold
- **Weakness**: O(N^2) becomes slow at scale (2984 L0 episodes = ~4.5M comparisons, took 45+ minutes on 2-core CPU)

### Stage 2: TF-IDF Text Clustering

**File**: `substrate/consciousness/mind/consolidation_embedding.py` — `cluster_by_similarity()`

Episodes that didn't cluster by nodes (isolated or with few shared entities) get a second chance via text similarity:

- **Algorithm**: TF-IDF vectorization of descriptions, O(N^2) pairwise cosine similarity, connected components
- **Implementation**: Pure Python, no numpy/sklearn dependencies
- **Threshold**: `min_similarity=0.2` (low — catches loose thematic groups)
- **Same cluster size bounds as Stage 1**
- **Oversized clusters**: recursively re-clustered with threshold + 0.1

### Stage 3: LLM Generalization

**File**: `substrate/consciousness/mind/consolidation.py` — `generalize_cluster()`

For each cluster found, Haiku generates a single generalization:

- **Input**: Up to 10 episodes per cluster (capped for token budget), each summarized as emotion + description + result + rule
- **Output**: JSON with `description`, `rule`, `procedure`, `emotion`, `result`
- **Separate prompts** for L0→L1 (episode→generalization) vs L1+→L2+ (generalization→principle)

## Deduplication Safeguards

Three independent filters prevent redundant generalizations:

### 1. Source Set Dedup
Before LLM call. If a cluster's exact set of source IDs already produced a generalization, skip.

### 2. Semantic Dedup (`_is_semantically_duplicate`)
After LLM call. Two methods in parallel:
- **Embedding cosine similarity** (BGE-base-en-v1.5, pgvector): threshold 0.50 for L1, decreasing 0.05 per level
- **Jaccard word overlap**: threshold 0.55 for L1, decreasing 0.1 per level

Either method can reject a duplicate.

### 3. Emotion Saturation (`_emotion_saturated`)
After LLM call. Prevents emotional echo chambers:
- Caps proportion of any single emotion at target level: 35% for L1, 30% for L2, 25% for L3
- Critical for preventing negative experiences (shame, frustration) from dominating higher-level memory — these tend to generate higher emotional intensity

## `--all` vs `--day` Modes

### `consolidate_all()` (--all flag)
- Processes all levels sequentially: L0→L1, L1→L2, L2→L3
- `--day N` filter applies only to L0; higher levels always consolidate all
- Heavy: with 2984 L0 episodes, takes hours

### `consolidate()` (single level)
- `--day N` loads only that day's episodes at the specified level
- Designed for "sleep after each day" pattern: consolidate only today's experiences
- Much faster: typically 5-50 episodes per day

## Storage

New generalizations are written as regular contexts with:
- `level = source_level + 1`
- `sources` = JSON array of source context IDs
- Five embedding vectors computed and stored (v_description, v_structure, v_rule, v_procedure, v_emotion)
- Linked to the object store via `context_objects`

## Performance Observations (March 2026)

- 3844 total contexts: 2984 L0, 858 L1 (imported from v4), 2 L2
- `--all` on full dataset: ~2-3 hours on 2-core Hetzner VPS
- Bottleneck is O(N^2) node overlap computation, not LLM calls
- LLM calls use Haiku (~$0.001 per cluster) — negligible cost
- Day-scoped consolidation (~10-50 episodes) runs in minutes

## Design Insights

1. **Graph-first, text-second**: Node overlap captures thematic relationships better than text similarity for structured memories. TF-IDF catches what falls through.

2. **Emotion saturation is essential**: Without it, negative emotional experiences (more intense, more frequent in memory) would dominate generalizations. This is analogous to cognitive therapy's observation that depression distorts memory consolidation.

3. **Recursive cluster splitting**: Prevents mega-clusters that would produce vague generalizations. Progressively stricter thresholds ensure manageable group sizes.

4. **No real embeddings for clustering**: Despite having 5-channel BGE embeddings, clustering uses node overlap + TF-IDF. Embeddings are only used for deduplication. This is a potential improvement area — embedding-based clustering would be more semantically aware.
