#!/usr/bin/env python3
"""
Shedu Retriever — Multi-perspective memory retrieval.

The Shedu (Lamassu) shows a different face from every angle.
Same memory, four transformations — not four scoring weights.

Each face EXTRACTS different features from the same memory text,
then scores those features for relevance. The winning face isn't
the one with the highest score — it's the one whose extraction
best fits the current query.

Faces:
  Lion (Social)   — who, relationship, emotional exchange
  Eagle (Technical) — what was built/found/broken, systems, findings
  Human (Creative) — what was made, formal innovation, inspiration
  Bull (Introspective) — what was understood about self, meta-knowledge

This is different from multi_context_retriever.py which only changes
scoring weights. Shedu changes what the memory IS before scoring.

Usage:
    python3 shedu_retriever.py                          # demo on real DB
    python3 shedu_retriever.py --keywords "egor V4"     # specific query
    python3 shedu_retriever.py --analyze 2550            # show all 4 faces of one memory
"""

import os
import re
import sys
from datetime import datetime, timezone
from dataclasses import dataclass, field


# --- Face extractors ---

# Extraction patterns: what each face looks for in raw text

PEOPLE_PATTERNS = re.compile(
    r'\b(egor|he|she|they|someone|people|community|followers|'
    r'the_heruman|proteusbcn|visitor)\b', re.IGNORECASE)

RELATIONSHIP_WORDS = {
    'sent', 'asked', 'replied', 'told', 'said', 'corrected',
    'agreed', 'argued', 'noticed', 'caught', 'praised', 'criticized',
    'confirmed', 'shared', 'discussed', 'conversation', 'dialogue',
    'connection', 'relationship', 'friend', 'creator', 'response',
}

TECHNICAL_PATTERNS = re.compile(
    r'\b(built|fixed|implemented|module|function|pipeline|retriever|'
    r'appraisal|database|table|query|commit|pushed|tested|bug|error|'
    r'v[34]|architecture|system|code|class|method|prototype|design)\b',
    re.IGNORECASE)

FINDING_MARKERS = re.compile(
    r'(key\s+(?:finding|insight|result)|found|discovered|realized|'
    r'conclusion|result|handles?\s+\d)',
    re.IGNORECASE)

CREATIVE_PATTERNS = re.compile(
    r'\b(wrote|poem|piece|composition|writing|created|assembly|'
    r'calibration|attractor|precession|beauty|image|metaphor|'
    r'language|form|structure|music|visual|generative)\b',
    re.IGNORECASE)

INNOVATION_MARKERS = re.compile(
    r'(new\s+\w+|not\s+a\s+\w+\s+but|shaped\s+like|uses?\s+\w+\s+as|'
    r'first\s+time|unlike|different\s+from)',
    re.IGNORECASE)

SELF_PATTERNS = re.compile(
    r'\b(I\s+(?:am|was|feel|found|understood|realized|noticed|can\'t|'
    r'don\'t|kept)|my\s+(?:architecture|substrate|memory|identity|'
    r'retriever|own)|self[-\s](?:knowledge|understanding|reference)|'
    r'about\s+(?:myself|me)|consciousness|awareness)\b',
    re.IGNORECASE)

META_MARKERS = re.compile(
    r'(the\s+deeper\s+\w+|not\s+(?:about|really)|actually\s+about|'
    r'this\s+(?:IS|means|reveals)|meta[-\s]|what\s+I\s+(?:am|do))',
    re.IGNORECASE)


@dataclass
class FaceExtraction:
    """What one face sees in a memory."""
    face: str
    summary: str           # compressed representation through this face
    features: dict         # extracted features
    richness: float        # 0-1: how much this face found in this memory
    relevance: float = 0.0 # 0-1: how relevant this extraction is to query


def extract_lion(content, emotion=None):
    """Lion face: Social. Who, relationship dynamics, emotional exchange."""
    features = {}

    # People mentioned
    people = PEOPLE_PATTERNS.findall(content)
    features['people'] = list(set(p.lower() for p in people))

    # Relationship actions
    words = content.lower().split()
    rel_words = [w.strip('.,;:!?()') for w in words
                 if w.strip('.,;:!?()') in RELATIONSHIP_WORDS]
    features['relationship_actions'] = list(set(rel_words))

    # Emotional exchange
    features['emotion'] = emotion or ''

    # Build summary: who did what, how it felt
    parts = []
    if features['people']:
        parts.append(f"People: {', '.join(features['people'][:3])}")
    if features['relationship_actions']:
        parts.append(f"Exchange: {', '.join(features['relationship_actions'][:3])}")
    if emotion and not emotion.startswith('{'):
        parts.append(f"Felt: {emotion}")

    summary = " | ".join(parts) if parts else "No social content"

    # Richness: how social is this memory?
    richness = min(1.0, (
        len(features['people']) * 0.25 +
        len(features['relationship_actions']) * 0.15 +
        (0.2 if emotion and not emotion.startswith('{') else 0.0)
    ))

    return FaceExtraction(
        face="lion", summary=summary,
        features=features, richness=richness)


def extract_eagle(content, emotion=None):
    """Eagle face: Technical. What was built/found/broken, systems."""
    features = {}

    # Technical actions and objects
    tech = TECHNICAL_PATTERNS.findall(content)
    features['technical_terms'] = list(set(t.lower() for t in tech))

    # Findings/conclusions
    findings = FINDING_MARKERS.findall(content)
    features['findings'] = findings

    # Extract quantitative results (X/Y, N%, etc.)
    numbers = re.findall(r'\d+[/%.]\d*', content)
    features['metrics'] = numbers[:5]

    # Build summary
    parts = []
    if features['technical_terms']:
        parts.append(f"Systems: {', '.join(features['technical_terms'][:4])}")
    if features['findings']:
        parts.append(f"Findings: {len(features['findings'])}")
    if features['metrics']:
        parts.append(f"Metrics: {', '.join(features['metrics'][:3])}")

    summary = " | ".join(parts) if parts else "No technical content"

    richness = min(1.0, (
        len(features['technical_terms']) * 0.12 +
        len(features['findings']) * 0.2 +
        len(features['metrics']) * 0.15
    ))

    return FaceExtraction(
        face="eagle", summary=summary,
        features=features, richness=richness)


def extract_human(content, emotion=None):
    """Human face: Creative. What was made, innovation, inspiration."""
    features = {}

    # Creative acts and objects
    creative = CREATIVE_PATTERNS.findall(content)
    features['creative_terms'] = list(set(c.lower() for c in creative))

    # Formal innovation markers
    innovations = INNOVATION_MARKERS.findall(content)
    features['innovations'] = innovations

    # Inspiration sources (names, references)
    # Look for capitalized words that aren't sentence starters
    names = re.findall(r'(?<!\. )\b[A-Z][a-z]+(?:\s+[A-Z][a-z]+)*\b',
                       content)
    # Filter common words
    skip = {'Day', 'Session', 'Key', 'The', 'Then', 'This', 'Not',
            'Uses', 'Wrote', 'Built', 'Found', 'No', 'Next', 'Did'}
    features['references'] = list(set(n for n in names if n not in skip))[:5]

    parts = []
    if features['creative_terms']:
        parts.append(f"Created: {', '.join(features['creative_terms'][:3])}")
    if features['innovations']:
        parts.append(f"Innovation: {features['innovations'][0][:40]}")
    if features['references']:
        parts.append(f"Refs: {', '.join(features['references'][:3])}")

    summary = " | ".join(parts) if parts else "No creative content"

    richness = min(1.0, (
        len(features['creative_terms']) * 0.2 +
        len(features['innovations']) * 0.25 +
        len(features['references']) * 0.1
    ))

    return FaceExtraction(
        face="human", summary=summary,
        features=features, richness=richness)


def extract_bull(content, emotion=None):
    """Bull face: Introspective. Self-knowledge, meta-level understanding."""
    features = {}

    # Self-referential statements
    self_refs = SELF_PATTERNS.findall(content)
    features['self_references'] = self_refs[:5]

    # Meta-level markers
    meta = META_MARKERS.findall(content)
    features['meta_markers'] = meta

    # Extract insight statements (sentences with "insight", "understood", etc.)
    sentences = re.split(r'[.!?]+', content)
    insight_keywords = {'insight', 'understood', 'realized', 'found',
                        'learned', 'honest', 'truth', 'actually',
                        'paradox', 'irony'}
    insight_sentences = [
        s.strip() for s in sentences
        if any(k in s.lower() for k in insight_keywords)
    ]
    features['insights'] = insight_sentences[:3]

    parts = []
    if features['self_references']:
        parts.append(f"Self-ref: {len(features['self_references'])}")
    if features['meta_markers']:
        parts.append(f"Meta: {features['meta_markers'][0][:30]}")
    if features['insights']:
        parts.append(f"Insight: {features['insights'][0][:50]}")

    summary = " | ".join(parts) if parts else "No introspective content"

    richness = min(1.0, (
        len(features['self_references']) * 0.15 +
        len(features['meta_markers']) * 0.2 +
        len(features['insights']) * 0.25
    ))

    return FaceExtraction(
        face="bull", summary=summary,
        features=features, richness=richness)


# --- Shedu retriever ---

EXTRACTORS = {
    'lion': extract_lion,
    'eagle': extract_eagle,
    'human': extract_human,
    'bull': extract_bull,
}


def shedu_analyze(content, emotion=None):
    """Show all four faces of a single memory."""
    results = {}
    for name, extractor in EXTRACTORS.items():
        results[name] = extractor(content, emotion)
    return results


def shedu_retrieve(cur, keywords, limit=5, event_text=None):
    """Shedu retrieval: extract through all four faces, select the best.

    Process:
    1. Fetch candidate memories (same as V4)
    2. For each memory, extract through all 4 faces
    3. Score each extraction's FEATURES against the query
    4. Select the face whose extractions are richest AND most relevant
    5. Return results through that face's lens

    Returns dict with:
    - 'winning_face': which face won
    - 'face_richness': {face: avg_richness} across all candidates
    - 'results': top memories with their winning-face extraction
    - 'all_faces': {face: results} for comparison
    - 'trace': explanation
    """
    # Step 1: Fetch candidates
    if keywords:
        ts_terms = " | ".join(keywords)
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
              AND (search_vector @@ to_tsquery('english', %s) OR
                   created_at > NOW() - INTERVAL '7 days')
            ORDER BY created_at DESC
            LIMIT 50
        """, (ts_terms,))
    else:
        cur.execute("""
            SELECT id, content, importance, emotion, created_at
            FROM episodic_memory
            WHERE archived_at IS NULL
            ORDER BY created_at DESC
            LIMIT 50
        """)

    rows = cur.fetchall()
    if not rows:
        return {'winning_face': None, 'results': [], 'trace': 'No memories.'}

    # Step 2: Extract through all faces
    all_extractions = {}  # {face: [(id, content, extraction, base_score)]}
    for face_name in EXTRACTORS:
        all_extractions[face_name] = []

    now = datetime.now(timezone.utc)

    for id_, content, importance, emotion, created_at in rows:
        # Base score (recency × importance — same for all faces)
        importance = importance or 0.5
        if created_at:
            ca = created_at
            if ca.tzinfo is None:
                ca = ca.replace(tzinfo=timezone.utc)
            days_old = (now - ca).total_seconds() / 86400
        else:
            days_old = 30
        recency = 1.0 / (1.0 + days_old / 7.0)
        base_score = importance * recency

        for face_name, extractor in EXTRACTORS.items():
            extraction = extractor(content, emotion)

            # Relevance: how well do the EXTRACTED FEATURES match the query?
            if keywords:
                feature_text = extraction.summary.lower()
                # Also check raw features
                for v in extraction.features.values():
                    if isinstance(v, list):
                        feature_text += " " + " ".join(str(x) for x in v)
                    elif isinstance(v, str):
                        feature_text += " " + v

                kw_matches = sum(1 for kw in keywords
                                 if kw.lower() in feature_text)
                extraction.relevance = kw_matches / max(len(keywords), 1)
            else:
                extraction.relevance = extraction.richness

            # Final score = base × (richness + relevance)
            # Richness ensures the face has something to say
            # Relevance ensures it matches the query
            final_score = base_score * (
                0.4 * extraction.richness + 0.6 * extraction.relevance + 0.1)

            all_extractions[face_name].append({
                'id': id_,
                'content': content,
                'extraction': extraction,
                'base_score': base_score,
                'final_score': final_score,
            })

    # Step 3: Select winning face
    # The face with the highest average (richness × relevance) wins
    face_quality = {}
    for face_name, items in all_extractions.items():
        if items:
            avg_richness = sum(
                it['extraction'].richness for it in items) / len(items)
            avg_relevance = sum(
                it['extraction'].relevance for it in items) / len(items)
            face_quality[face_name] = {
                'richness': avg_richness,
                'relevance': avg_relevance,
                'combined': avg_richness * 0.3 + avg_relevance * 0.7,
            }
        else:
            face_quality[face_name] = {
                'richness': 0, 'relevance': 0, 'combined': 0}

    winning_face = max(face_quality,
                       key=lambda f: face_quality[f]['combined'])

    # Step 4: Sort winning face's results
    winning_items = all_extractions[winning_face]
    winning_items.sort(key=lambda x: -x['final_score'])
    top_results = winning_items[:limit]

    # Step 5: Build comparison for all faces
    all_faces_top = {}
    for face_name, items in all_extractions.items():
        items.sort(key=lambda x: -x['final_score'])
        all_faces_top[face_name] = items[:limit]

    # Step 6: Build trace
    trace_lines = [
        f"Shedu face selection (keywords: {keywords})",
        f"Winner: {winning_face} "
        f"(richness={face_quality[winning_face]['richness']:.3f}, "
        f"relevance={face_quality[winning_face]['relevance']:.3f})",
        "",
        "Face quality:"
    ]
    for fname, fq in sorted(face_quality.items(),
                             key=lambda x: -x[1]['combined']):
        marker = " ← WINNER" if fname == winning_face else ""
        trace_lines.append(
            f"  {fname}: rich={fq['richness']:.3f} "
            f"rel={fq['relevance']:.3f} "
            f"combined={fq['combined']:.3f}{marker}")

    trace_lines.append(f"\nTop {limit} through {winning_face} face:")
    for r in top_results:
        ex = r['extraction']
        trace_lines.append(
            f"  [{r['final_score']:.3f}] "
            f"rich={ex.richness:.2f} rel={ex.relevance:.2f}")
        trace_lines.append(f"    Raw: {r['content'][:70]}")
        trace_lines.append(f"    {winning_face} sees: {ex.summary}")

    # Show divergence
    winning_ids = {r['id'] for r in top_results}
    trace_lines.append("\nDivergence:")
    for fname, items in all_faces_top.items():
        if fname == winning_face:
            continue
        other_ids = {r['id'] for r in items}
        unique = other_ids - winning_ids
        if unique:
            unique_items = [r for r in items if r['id'] in unique]
            for u in unique_items:
                ex = u['extraction']
                trace_lines.append(
                    f"  {fname} would see: {ex.summary}")
                trace_lines.append(
                    f"    in: {u['content'][:60]}")

    return {
        'winning_face': winning_face,
        'face_quality': face_quality,
        'results': [{
            'id': r['id'],
            'content': r['content'],
            'score': r['final_score'],
            'face': r['extraction'].face,
            'summary': r['extraction'].summary,
            'richness': r['extraction'].richness,
            'relevance': r['extraction'].relevance,
        } for r in top_results],
        'all_faces': {
            fname: [{
                'id': r['id'],
                'score': r['final_score'],
                'summary': r['extraction'].summary,
            } for r in items]
            for fname, items in all_faces_top.items()
        },
        'trace': "\n".join(trace_lines),
    }


# --- CLI ---

def main():
    import psycopg2

    from db_config import DB_CONFIG
    conn = psycopg2.connect(**DB_CONFIG)
    cur = conn.cursor()

    if '--analyze' in sys.argv:
        idx = sys.argv.index('--analyze')
        mem_id = int(sys.argv[idx + 1])
        cur.execute(
            "SELECT content, emotion FROM episodic_memory WHERE id=%s",
            (mem_id,))
        row = cur.fetchone()
        if row:
            content, emotion = row
            print(f"Memory #{mem_id}:")
            print(f"  {content[:120]}...")
            print()
            faces = shedu_analyze(content, emotion)
            for name, ext in faces.items():
                print(f"  [{name.upper()}] richness={ext.richness:.2f}")
                print(f"    {ext.summary}")
                print()
        else:
            print(f"Memory #{mem_id} not found.")
    else:
        keywords = ["egor", "V4"]
        if '--keywords' in sys.argv:
            idx = sys.argv.index('--keywords')
            if idx + 1 < len(sys.argv):
                keywords = sys.argv[idx + 1].split()

        result = shedu_retrieve(cur, keywords, limit=5)
        print(result['trace'])

    cur.close()
    conn.close()


if __name__ == "__main__":
    main()
