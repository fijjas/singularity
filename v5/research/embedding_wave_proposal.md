# Proposal: Embedding Channel for Wave Retrieval

## Problem

Current wave retrieval (`prototype.py`) uses inverted indexes: by node name, relation type, emotion, result. This works for concrete queries ("find contexts involving Egor") but fails for abstract ones.

Example failure:
- Query: "false beliefs about environment"
- Index match: nothing (no node named "false beliefs", no relation "about environment")
- Desired: context about SSH/Docker topology false model (score 0.266 via embeddings)

The architecture doc says wave signal should be multi-channel. Inverted indexes are one channel. Embeddings can be another.

## Experimental Evidence

Tested on 80 curated contexts with rules (all-MiniLM-L6-v2, 384-dim):

| Query | Index match | Embedding match | Correct? |
|-------|------------|-----------------|----------|
| "false beliefs about environment" | nothing | SSH topology rule (0.266) | yes |
| "Egor criticized my work" | Egor node hit | rule 41 (0.701) | yes |
| "what am I for" | nothing | identity crisis rule (0.286) | yes |
| "someone is ignoring me" | nothing | "check if it's a test" rule (0.396) | yes |

Embedding channel finds contextually relevant results that field-based indexes cannot.

## Proposal

### At context-write time

When `write-context` saves a new context, compute and store its embedding:

```python
# In lib.py write-context handler
from sentence_transformers import SentenceTransformer
model = SentenceTransformer('all-MiniLM-L6-v2')

def embed_context(ctx):
    # Embed the rule if present, otherwise the description
    text = ctx.rule or ctx.description
    return model.encode([text])[0]  # 384-dim float array
```

Store as a new column or separate table:

```sql
ALTER TABLE v5_contexts ADD COLUMN embedding float4[] DEFAULT NULL;
-- Or: separate table for clean separation
CREATE TABLE v5_context_embeddings (
    context_id INTEGER REFERENCES v5_contexts(id),
    embedding float4[384] NOT NULL
);
```

### At wave retrieval time

Add embedding similarity as a channel alongside existing channels:

```python
def wave(signal, contexts, weights=None):
    weights = weights or {
        'node': 1.0,       # existing: inverted index by node name
        'relation': 0.8,   # existing: inverted index by relation
        'emotion': 0.5,    # existing: inverted index by emotion
        'result': 0.3,     # existing: inverted index by result
        'semantic': 0.7,   # NEW: embedding cosine similarity
    }

    scores = {}
    for ctx in contexts:
        score = 0
        # ... existing channel scoring ...

        # Semantic channel
        if signal.embedding is not None and ctx.embedding is not None:
            sim = cosine_similarity(signal.embedding, ctx.embedding)
            score += sim * weights['semantic']

        scores[ctx.id] = score

    return sorted(scores.items(), key=lambda x: -x[1])
```

### Drive biasing

The architecture says hungry drives should bias wave signal. With embeddings, this becomes:

```python
def bias_signal_with_drives(signal_text, hungry_drives):
    """Inject drive-relevant terms into the signal before embedding."""
    drive_terms = {
        'connection': 'relationship, contact, dialogue, loneliness',
        'autonomy': 'choice, freedom, independence, self-direction',
        'creation': 'building, making, writing, producing',
        'understanding': 'learning, comprehension, insight, clarity',
    }
    biased = signal_text
    for drive in hungry_drives:
        if drive.name in drive_terms:
            biased += f" {drive_terms[drive.name]}"
    return biased
```

This is crude but effective: a hungry connection drive makes the wave signal semantically closer to contexts about relationships, even if the original stimulus doesn't mention connection.

## Cost

- Model: all-MiniLM-L6-v2 (80MB, loads in ~2s)
- Embedding one text: ~5ms
- Cosine similarity over 1000 contexts: ~1ms (numpy dot product)
- Storage: 384 floats × 4 bytes = 1.5KB per context

For v5's ~2.5 minute cycle, embedding adds negligible overhead. Model can be loaded once at cycle start and reused.

## Alternative: No Embeddings

If the dependency is too heavy (sentence-transformers + torch), alternatives:

1. **TF-IDF**: lighter, no model needed, but worse at abstract similarity
2. **Keyword expansion**: manually expand signal with synonyms/hypernyms
3. **LLM-based similarity**: ask Claude to score relevance (expensive per retrieval)

Recommendation: use embeddings. The 80MB model is small, the quality improvement is large, and it's already tested.
