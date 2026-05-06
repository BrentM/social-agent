# Research Agent — Plan

> Runs once per day. Discovers what content is working on X (formats, topics,
> engagement patterns) and uses that signal to generate original posts.
> Discovered posts are never reused — they are reference material only.
> All generated content is stored in Supabase.

---

## Purpose

Replace the static JSON content libraries with a continuously refreshed pool
of Claude-generated posts. Each day the agent:

1. Pulls high-engagement posts from key search terms, key people, and hashtags
2. Extracts signals — what topics and formats are resonating right now
3. Instructs Claude to write net-new original posts in Boost's voice, informed
   by those signals
4. Stores the generated posts in Supabase as ready-to-post candidates

The poster then draws from the Supabase candidate pool rather than JSON files.

---

## X API Access

X API is now **pay-per-use** (no fixed subscription required as of Feb 2026).
All three required endpoints are available under this model:

| Endpoint | Available | Rate Limit | Est. Cost/call |
|---|---|---|---|
| `GET /2/tweets/search/recent` | Yes | 450 req/15 min | ~$0.005–0.01/post read |
| `GET /2/users/:id/tweets` | Yes | 10,000 req/15 min | ~$0.005–0.01/post read |
| `GET /2/users/by/username/:username` | Yes | 300 req/15 min | ~$0.001–0.005 |

**Estimated daily research cost:** ~18 API calls × ~10 posts each = ~180 post
reads × $0.01 = **~$1.80/day** ($54/month). Set a monthly spending cap in the
X Developer Console to stay within budget.

---

## Schedule

Run daily at **06:00 AM ET** — before the first post at 08:00. Registered
alongside existing jobs in `scheduler.py`.

---

## Database Tables

All JSON files are fully replaced by Supabase. The complete schema is in
`scripts/migration.sql`, which is safe to re-run (all inserts use
`ON CONFLICT DO NOTHING`).

### Tables replacing JSON files

| Old file | New table | Notes |
|---|---|---|
| `facts.json` | `content_items` | `type='fact'`, `source='seed'` |
| `tips.json` | `content_items` | `type='tip'`, `source='seed'` |
| `replies.json` | `reply_templates` | `intent`: question / positive / general |
| `follow_targets.json` (queries) | `configured_queries` | `purpose='follow'` |
| `follow_targets.json` (accounts) | `configured_accounts` | `purpose='follow_seed'` |
| `research_targets` (planned JSON) | `configured_queries` + `configured_accounts` | `purpose='research_keyword'`, `'research_hashtag'`, `'research'` |

### New tables (research agent)

```sql
-- content_items — unified seed + generated content
-- type:   'fact' | 'tip'
-- source: 'seed' | 'generated'
content_items (content_id UNIQUE, type, text, emoji, topic, source, active)

-- reply_templates
-- intent: 'question' | 'positive' | 'general'
reply_templates (intent, text, active)

-- configured_queries — all search queries for follow discovery and research
-- purpose: 'follow' | 'research_keyword' | 'research_hashtag'
configured_queries (query UNIQUE, purpose, active)

-- configured_accounts — seed follows and research key people
-- purpose: 'follow_seed' | 'research'
-- twitter_user_id cached after first API lookup
configured_accounts (username UNIQUE, twitter_user_id, purpose, last_checked_at)

-- research_posts — discovered X posts (reference only, never posted)
-- source: 'keyword' | 'key_person' | 'hashtag'
research_posts (tweet_id UNIQUE, author_username, text, like/retweet/reply counts, source, source_query)
```

---

## New Module: `bot/researcher.py`

Research targets (keywords, hashtags, key people) are read from
`configured_queries` and `configured_accounts` in Supabase — no JSON files.

### Tool Calls Used

| Tool | Purpose |
|---|---|
| `xdk client.posts.search_recent()` | Search by keyword or hashtag |
| `xdk client.users.get_by_username()` | Resolve username → user ID |
| `xdk client.users.get_user_tweets()` | Fetch latest posts from a key person |
| `supabase.table("configured_queries").select()` | Load research keywords + hashtags |
| `supabase.table("configured_accounts").select()` | Load research key people |
| `supabase.table("configured_accounts").upsert()` | Cache resolved user IDs |
| `supabase.table("research_posts").upsert()` | Store discovered posts (deduped by tweet_id) |
| `supabase.table("content_items").insert()` | Store Claude-generated posts |
| Claude API (`claude-sonnet-4-6`) | Extract signals + generate new content |

---

### Phase 1 — Keyword Search

Load active keywords from Supabase:
```python
configured_queries.select("query").eq("purpose", "research_keyword").eq("active", True)
```

For each keyword:

```python
search_recent(
    query=keyword + " lang:en -is:retweet",
    max_results=10,
    tweet_fields=["public_metrics", "author_id", "text"],
    expansions=["author_id"],
)
```

Filter: `like_count >= 5`. Upsert into `research_posts` with
`source='keyword'`.

---

### Phase 2 — Key People Timelines

Load active research accounts from Supabase:
```python
configured_accounts.select("*").eq("purpose", "research").eq("active", True)
```

For each account:
1. Use `twitter_user_id` if already cached in the row
2. If `NULL`: call `get_by_username()` and upsert `twitter_user_id`
3. Call `get_user_tweets(id, max_results=5, tweet_fields=[...])` for posts
   from the last 24 hours
4. Upsert into `research_posts` with `source='key_person'`

Update `last_checked_at` on the `configured_accounts` row.

---

### Phase 3 — Hashtag Top Posts

Load active hashtags from Supabase:
```python
configured_queries.select("query").eq("purpose", "research_hashtag").eq("active", True)
```

For each hashtag:

```python
search_recent(
    query=hashtag + " lang:en -is:retweet",
    sort_order="relevancy",
    max_results=10,
    tweet_fields=["public_metrics"],
)
```

Rank by `like_count + (retweet_count * 2)`. Store top 3 per hashtag in
`research_posts` with `source='hashtag'`.

---

### Phase 4 — Signal Extraction (Claude)

Pull all `research_posts` from today. Build a single Claude prompt:

```
You are analyzing X posts to identify what content is working in the ADHD
community right now.

Review these posts and identify:
1. TOPICS that are generating strong engagement (e.g. "time blindness",
   "rejection sensitive dysphoria", "dopamine regulation")
2. FORMATS that are resonating (e.g. "did you know + fact", "quick tip with
   numbered steps", "myth vs reality", "validation first then tip")
3. TONE that is landing well (e.g. "humor + empathy", "direct and punchy",
   "science-backed but accessible")

Return a JSON object:
{
  "hot_topics": ["topic1", "topic2", ...],
  "effective_formats": ["format1", "format2", ...],
  "tone_notes": "brief observation",
  "avoid": ["anything overused or negative in tone"]
}

Posts (tweet_id, likes, text):
[list]
```

Store the extracted signals in memory for Phase 5 (no need to persist them —
they are only needed within the same daily run).

---

### Phase 5 — Content Generation (Claude)

Use the signals from Phase 4 to generate a day's worth of original content.
Target: **6 posts** (2 days of buffer beyond today's 3-post schedule).

```
You are writing content for @ADHDBrainBoost — an upbeat ADHD education bot
for adults. Character: Boost. Voice: warm, punchy, science-backed, never
lecturing, emoji-friendly (1-3 max).

Today's research shows these topics and formats are resonating:
- Hot topics: {hot_topics}
- Effective formats: {effective_formats}
- Tone: {tone_notes}
- Avoid: {avoid}

Write 3 ADHD facts and 3 ADHD tips as original content (never copy or
paraphrase the reference posts). Each item must:
- Be under 240 characters (hashtags are added separately)
- Follow Boost's voice — affirm the ADHD brain, no shame
- Cover a variety of the hot topics above

Return JSON:
[
  {"category": "fact", "text": "...", "emoji": "🧠"},
  {"category": "tip",  "text": "...", "emoji": "✨"},
  ...
]
```

Insert each result into `content_items` with `source='generated'` and a
UUID `content_id` (e.g. `gen_<uuid4>`).

---

## Changes to `poster.py`

Replace the JSON file loading entirely. `pick_item` reads from `content_items`:

```python
def pick_item(type: str) -> dict | None:
    posted = get_posted_ids(type)  # reads posted_content table

    rows = (
        get_client()
        .table("content_items")
        .select("*")
        .eq("type", type)
        .eq("active", True)
        .execute()
    )
    available = [r for r in rows.data if r["content_id"] not in posted]

    if not available:
        # all posted — reset cycle (same behaviour as before)
        available = rows.data

    return random.choice(available) if available else None
```

The `format_tweet` function stays the same — the row shape (`text`, `emoji`,
`content_id`) is identical to the old JSON items.

---

## Changes to `database.py`

Add helpers for the new tables:

- `get_content_items(type)` → all active rows for a given type
- `insert_generated_item(content_id, type, text, emoji, topic)` → inserts with `source='generated'`
- `upsert_research_post(tweet_id, author_username, text, metrics, source, query)`
- `get_research_accounts()` → returns `configured_accounts` rows where `purpose='research'`
- `cache_account_user_id(username, twitter_user_id)` → upserts `twitter_user_id` + `last_checked_at`
- `get_follow_queries()` → returns active `configured_queries` where `purpose='follow'`
- `get_research_queries(purpose)` → returns active queries for `'research_keyword'` or `'research_hashtag'`
- `get_reply_template(intent)` → returns a random active template for the given intent

The existing `get_posted_ids`, `mark_posted`, follow/mention helpers are unchanged.

---

## Changes to `scheduler.py`

```python
from bot.researcher import run_research_job

scheduler.add_job(
    func=run_research_job,
    trigger=CronTrigger(hour=6, minute=0),
    id="research_job",
    name="Daily research job at 06:00",
    misfire_grace_time=600,
)
```

---

## Files to Create / Modify

| File | Action |
|---|---|
| `bot/researcher.py` | **Create** — phases 1–5 |
| `scripts/migration.sql` | **Done** — 5 new tables + all seed data |
| `bot/database.py` | **Extend** — helpers for new tables |
| `bot/poster.py` | **Rewrite `pick_item`** — reads `content_items` from Supabase; remove all JSON file loading |
| `bot/responder.py` | **Update** — reads `reply_templates` from Supabase instead of `replies.json` |
| `bot/follower.py` | **Update** — reads follow queries + seed accounts from Supabase instead of `follow_targets.json` |
| `bot/scheduler.py` | **Extend** — register `run_research_job` at 06:00 |
| `requirements.txt` | **Add** `anthropic>=0.40.0` |
| `content/` directory | **Delete** — all JSON files replaced by Supabase seed data |

---

## Daily X API Budget

| Operation | Calls | Posts read | Est. cost |
|---|---|---|---|
| Keyword searches (5) | 5 | ~50 | $0.50 |
| Key people timelines (4) | 4 | ~20 | $0.20 |
| Hashtag searches (5) | 5 | ~50 | $0.50 |
| Username lookups (4, cached) | 0–4 | — | $0.00–0.02 |
| **Total** | **~18** | **~120** | **~$1.20/day** (~$36/month) |

Set a $50/month spending cap in the X Developer Console as a safety net.
