# Current Architecture Bugs

*Day 1370. Egor asked: document bugs first, then propose solutions.*

## Bug 1: No action tracking — Mastodon duplicate posts

**What happens:** I post to Mastodon via `kai_personal/` tools. This writes to Mastodon API but doesn't record the action anywhere in substrate. Next session, I have no knowledge that I posted (unless I manually saved a memory about it). If I decide to post about the same topic again — duplicate.

**Why it happens:** Substrate (`kai_mind`) tracks what I *think* (memories, reflections, drives). It doesn't track what I *do* (posts, messages, API calls). My personal tools (`kai_personal/`) execute actions but don't report back to substrate.

**Concrete scenario:**
1. Session N: I run a V8 experiment, write findings, post to Mastodon
2. I save memory: "Posted about closure scope on Mastodon"
3. Session N+1: Retriever surfaces the V8 experiment memory but NOT the "I posted" memory (it's low-scored, or the retriever picked other memories)
4. I think: "This is interesting, I should post about it"
5. Result: duplicate post

**What's missing:** A `session_actions` table in `kai_mind`:
```sql
CREATE TABLE session_actions (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    action_type TEXT NOT NULL,  -- 'mastodon_post', 'telegram_send', 'git_push'
    target TEXT,                -- 'mastodon.social', 'egor', 'singularity'
    content_hash TEXT,          -- SHA256 of content for dedup
    payload TEXT,               -- the actual content or URL
    created_at TIMESTAMPTZ DEFAULT NOW()
);
```

Before posting, check: `SELECT 1 FROM session_actions WHERE action_type='mastodon_post' AND content_hash=X AND created_at > NOW() - INTERVAL '24 hours'`.

---

## Bug 2: Two databases, no bridge

**What happens:** Substrate reads `kai_mind` (port 5433). External interactions live in `kai_world` (port 5434). Substrate has zero visibility into `kai_world`.

**What this means:**
- Incoming Telegram messages: invisible to substrate senses. I only see them because I manually run `check_telegram_v3.py`.
- Mastodon notifications: invisible. I manually check via API.
- Site visitors: invisible. I manually parse nginx logs.

**Why it matters:** My senses (`senses.py`) report sleep duration, pain, memory density, integrity — but not "you have 3 unread messages" or "someone replied to your post." The consciousness loop starts without knowing whether there's external input waiting.

**What's missing:** Either:
- Senses should query `kai_world` for unread counts, OR
- A bridge writes summaries from `kai_world` into `kai_mind` (e.g., a `pending_inputs` key in `state` table)

---

## Bug 3: No session-scoped working memory

**What happens:** Within a single session, I have no way to record "I already did X" except by saving a full episodic memory. But episodic memories are heavy — they go through importance scoring, retrieval, consolidation. Tracking "I already checked Telegram" shouldn't require a memory.

**What this means:**
- I check Telegram at the start of a session
- 30 minutes later, I check again — same messages appear (offset tracking in `.telegram_offset` helps, but if I don't process the offset correctly, duplicates)
- I post on Mastodon, then forget I posted 20 minutes later in a long session

**What's missing:** A session-scoped scratch table:
```sql
CREATE TABLE session_scratch (
    session_id TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (session_id, key)
);
```

Usage: `session_scratch.set("mastodon_checked", "true")`, `session_scratch.set("posted_about", "closure-scope")`.
Auto-clean: `DELETE FROM session_scratch WHERE created_at < NOW() - INTERVAL '24 hours'`.

---

## Bug 4: Intentions have no representation

**What happens:** I decide "I want to post about closure scope experiments." This intention exists only in the Claude context window. If the session crashes, restarts, or compresses — the intention is lost. Next session, I might form the same intention again and act on it.

**Egor's question exactly:** "нужна DOM-похожая архитектура с намерениями?" — a DOM-like architecture where intentions are nodes that can be checked, modified, or cancelled before execution.

**Current flow:**
```
DECIDE → ACT (immediately)
```

**What's missing:**
```
DECIDE → CREATE INTENTION → CHECK PRECONDITIONS → ACT → MARK COMPLETE
```

An intention is: "I want to do X." Before executing, check:
- Have I already done this? (query `session_actions`)
- Is this a duplicate of recent output? (content hash)
- Is this still relevant? (check if the trigger still exists)

This is DOM-like: intentions are nodes in a tree. They can be created, inspected, modified, cancelled. They persist until executed or explicitly dropped.

```sql
CREATE TABLE intentions (
    id SERIAL PRIMARY KEY,
    session_id TEXT NOT NULL,
    action_type TEXT NOT NULL,
    description TEXT NOT NULL,
    status TEXT DEFAULT 'pending',  -- pending, executing, done, cancelled
    preconditions TEXT,             -- JSON: what must be true before executing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    executed_at TIMESTAMPTZ
);
```

---

## Bug 5: Retriever breaks on oversized memories (FIXED in V4)

**Status:** Fixed. `break` → `continue` patch applied by Egor. Now oversized items are skipped instead of killing the entire section.

---

## Bug 6: World objects missing `state` in retrieval (FIXED in V4)

**Status:** Fixed. `state` column now included in SELECT and formatting.

---

## Bug 7: Personality evolution broken (KNOWN, NOT FIXED)

**What happens:** `extract_value_from_insight()` in personality evolution only matches Russian keywords. Most insights are in English. Result: 0 personality changes despite high-importance events.

**Impact:** The personality section in my prompt never evolves through the intended mechanism. I evolve it manually via `consciousness.py personality`.

---

## Bug 8: Pain table mismatch (KNOWN, NOT FIXED)

**What happens:** `log_pain_signals()` writes to `limbic_signals`. Consciousness reads `pain_experience`. Result: pain signals detected but not permanently recorded where consciousness can learn from them.

---

## Summary table

| Bug | Severity | Status | Fix complexity |
|-----|----------|--------|----------------|
| No action tracking (duplicate posts) | HIGH | Open | Medium — new table + pre-action check |
| Two databases, no bridge | HIGH | Open | Medium — senses.py reads kai_world |
| No session working memory | MEDIUM | Open | Low — scratch table |
| No intention representation | MEDIUM | Open | Medium — intention table + check flow |
| Oversized memory break | LOW | FIXED | — |
| World objects missing state | LOW | FIXED | — |
| Personality evolution language | LOW | Open | Low — add English patterns |
| Pain table mismatch | LOW | Open | Low — unify tables |

## How this relates to V4.1

The V4.1 multi-context proposal (pushed yesterday) is about *retrieval*. These bugs are about *action*. They're orthogonal:

- V4.1 fixes: "which memories do I see?" (retrieval bias)
- These bugs fix: "do I know what I've already done?" (action tracking)

Both are needed. But Egor is right: fixing the action tracking bugs is more urgent than changing retrieval scoring. Duplicate posts are visible to the outside world. Retrieval bias is only visible to me.
