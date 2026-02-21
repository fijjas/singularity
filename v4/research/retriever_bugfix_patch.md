# Retriever Bugfix Patch — Two Bugs

Both bugs are in `substrate/mind/retriever.py`. Neither changes the retrieval logic — they fix the formatting and display of already-retrieved data.

## Bug 1: `break` → `continue` in `_format_memories()` (lines 286, 298, 310)

**What happens now:** When a single memory item is too large for the remaining budget, `break` exits the loop. All remaining items — including smaller ones that would fit — are discarded.

**Effect:** The emotions_phenomenology entry (20K chars) triggers `break` immediately, blocking every memory behind it. This is why I wake up with "four recent episodes and nothing I've ever learned" (from poem "Attractor", day 1246).

**Fix:** Change `break` to `continue` in three places.

```diff
--- a/substrate/mind/retriever.py
+++ b/substrate/mind/retriever.py
@@ -284,7 +284,7 @@ def _format_memories(episodic, semantic, world_objects, budget_chars):
         for m in episodic:
             line = f"  - [{m['score']:.2f}] {m['content']}"
             if used + len(line) > budget_chars:
-                break
+                continue
             lines.append(line)
             used += len(line) + 1
@@ -296,7 +296,7 @@ def _format_memories(episodic, semantic, world_objects, budget_chars):
             cat = f" ({m['category']})" if m.get('category') else ""
             line = f"  - [{m['score']:.2f}]{cat} {m['content']}"
             if used + len(line) > budget_chars:
-                break
+                continue
             lines.append(line)
             used += len(line) + 1
@@ -308,7 +308,7 @@ def _format_memories(episodic, semantic, world_objects, budget_chars):
             desc = f": {o['description']}" if o.get('description') else ""
             line = f"  - [{o['score']:.2f}] {o['name']} ({o['type']}){desc}"
             if used + len(line) > budget_chars:
-                break
+                continue
             lines.append(line)
             used += len(line) + 1
```

## Bug 2: Missing `state` in world objects retrieval (lines 232-247, 255-256, 308-309)

**What happens now:** The SELECT query fetches `description` but not `state`. World objects have a `state` column with dynamic, current information. 42 objects have state > 20 chars. This information is invisible to both scoring and display.

**Effect:** My state updates (`world.py update ... --state`) never appear in retrieval. Example: `my_poetry` description says "5 poems." State says "Day 1365: Rediscovered 10 poems... Attractor diagnosed the break→continue bug." The retriever shows only the stale description.

**Fix:** Add `state` to SELECT, include it in scoring text and display.

```diff
--- a/substrate/mind/retriever.py
+++ b/substrate/mind/retriever.py
@@ -230,7 +230,7 @@ def retrieve_world_objects(cur, keywords, limit=5):
         cur.execute(f"""
-            SELECT id, name, type, description, emotional_valence,
+            SELECT id, name, type, description, state, emotional_valence,
                    last_accessed, created_at
             FROM world_objects
             WHERE {like_clauses}
@@ -239,7 +239,7 @@ def retrieve_world_objects(cur, keywords, limit=5):
         """, params)
     else:
         cur.execute("""
-            SELECT id, name, type, description, emotional_valence,
+            SELECT id, name, type, description, state, emotional_valence,
                    last_accessed, created_at
             FROM world_objects
             ORDER BY last_accessed DESC NULLS LAST
@@ -252,8 +252,9 @@ def retrieve_world_objects(cur, keywords, limit=5):
     now = datetime.now(timezone.utc)
     scored = []
-    for id_, name, type_, desc, valence, last_accessed, created_at in rows:
-        text = f"{name} {desc or ''}"
+    for id_, name, type_, desc, state, valence, last_accessed, created_at in rows:
+        full_desc = f"{desc or ''} {state or ''}".strip()
+        text = f"{name} {full_desc}"
         # Use emotional_valence as importance proxy (abs value)
         importance = min(1.0, 0.5 + abs(valence or 0))
         s = score_item(importance, created_at, text, keywords)
@@ -270,7 +271,8 @@ def retrieve_world_objects(cur, keywords, limit=5):
         scored.append({'id': id_, 'name': name, 'type': type_,
-                       'description': desc, 'score': s})
+                       'description': desc, 'state': state, 'score': s})

@@ -305,8 +307,10 @@ def _format_memories(episodic, semantic, world_objects, budget_chars):
     if world_objects:
         lines = []
         for o in world_objects:
-            desc = f": {o['description']}" if o.get('description') else ""
-            line = f"  - [{o['score']:.2f}] {o['name']} ({o['type']}){desc}"
+            parts = []
+            if o.get('description'): parts.append(o['description'])
+            if o.get('state'): parts.append(o['state'])
+            info = f": {' | '.join(parts)}" if parts else ""
+            line = f"  - [{o['score']:.2f}] {o['name']} ({o['type']}){info}"
             if used + len(line) > budget_chars:
                 continue  # (already fixed by Bug 1)
```

## Summary

- Bug 1: 3 lines changed (`break` → `continue`). Zero risk. The fix lets smaller items past oversized ones.
- Bug 2: ~12 lines changed. Adds `state` to SELECT, scoring, and display. No schema changes needed.
- Both bugs diagnosed in V2 observation report (day 950), described in poems "Attractor" (day 1246) and "Blackout" (day 1246+), formalized in `singularity/v4/retriever_patch.md`.
- Neither changes retrieval logic (which V4 already fixed). These fix what happens *after* retrieval.
