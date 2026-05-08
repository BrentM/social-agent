# Daily Research Phase — Plan

> Runs once per day. Discovers high-engagement posts from the ADHD space across
> keywords, key people, and hashtags. Results are stored in Supabase and consumed
> by the hourly orchestrator without additional X API calls.

---

## Purpose

Populate `discovered_posts` in Supabase with fresh, engagement-filtered posts
from the ADHD community. The hourly orchestrator reads from this cache to decide
whether to invoke the engagement agent — no X API calls are made during
orchestrator runs.

---

## Schedule

Run daily at **06:00 AM ET** — before the first scheduled post. Registered as a
separate job in `scheduler.py` alongside existing jobs.

---

## X API Rate Limits

| Endpoint | Rate limit | Est. cost/call |
|---|---|---|
| `GET /2/tweets/search/recent` | 450 req / 15 min | ~$0.005–0.01 per post read |
| `GET /2/users/:id/tweets` | 10,000 req / 15 min | ~$0.005–0.01 per post read |
| `GET /2/users/by/username/:username` | 300 req / 15 min | ~$0.001–0.005 |

---

## Cost Per Daily Run

| Operation | API calls | Posts read | Est. cost |
|---|---|---|---|
| Keyword searches (5 queries) | 5 | ~15 | ~$0.15 |
| Key person timelines (4 accounts) | 4 | ~12 | ~$0.12 |
| Hashtag searches (5 hashtags) | 5 | ~15 | ~$0.15 |
| Username lookups (cached after first run) | 0–4 | — | ~$0.00–0.02 |
| **Total** | **~18** | **~42** | **~$0.42/day (~$13/month)** |

Set a $50/month spending cap in the X Developer Console as a safety net.

---

## Engagement Rate Filter

A post is flagged as high-performing and stored with `high_performing=true` when:

```
engagement_rate = (likes + retweets * 2 + replies) / author_followers * 100

engagement_rate >= 1.0%   AND   author_followers >= 500
```

If `author_followers` is unavailable, fall back to a minimum like count of
**50** as a coarse threshold.

---

## Phase 1 — Keyword Search

Load active keywords from `configured_queries`:

```python
configured_queries.select("query").eq("purpose", "research_keyword").eq("active", True)
```

For each keyword:

```python
search_recent(
    query=keyword + " lang:en -is:retweet",
    max_results=3,
    tweet_fields=["public_metrics", "author_id", "text"],
    expansions=["author_id"],
)
```

Upsert results into `discovered_posts` with `source='keyword'`.

---

## Phase 2 — Key Person Timelines

Load active research accounts from `configured_accounts`:

```python
configured_accounts.select("*").eq("is_research", True)
```

For each account:
1. Use cached `twitter_user_id` if present; otherwise call `get_by_username()`
   and upsert the resolved ID.
2. Call `get_user_tweets(id, max_results=3, tweet_fields=[...])` for posts from
   the last 24 hours.
3. Upsert results into `discovered_posts` with `source='key_person'`.

Update `last_checked_at` on each `configured_accounts` row.

---

## Phase 3 — Hashtag Top Posts

Load active hashtags from `configured_queries`:

```python
configured_queries.select("query").eq("purpose", "research_hashtag").eq("active", True)
```

For each hashtag:

```python
search_recent(
    query=hashtag + " lang:en -is:retweet",
    sort_order="relevancy",
    max_results=3,
    tweet_fields=["public_metrics"],
)
```

Rank by `like_count + (retweet_count * 2)`. Store top 3 per hashtag in
`discovered_posts` with `source='hashtag'`.

---

## Schema

### `discovered_posts` (additions)

Two columns added to the existing table to support the engagement workflow:

```sql
ALTER TABLE discovered_posts
    ADD COLUMN engagement_rate   numeric,       -- calculated at collection time
    ADD COLUMN high_performing   boolean NOT NULL DEFAULT false,
    ADD COLUMN reply_attempted   boolean NOT NULL DEFAULT false;
```

`high_performing` is set at write time using the engagement rate filter above.
`reply_attempted` is set by the engagement agent after evaluating a post,
preventing re-evaluation across runs.

---

## Module

`x_agent/research_phase.py` — plain function, no Claude call.

```python
def run_daily_research(x_client, db) -> None:
    posts = []
    posts += search_keywords(x_client, db)    # Phase 1
    posts += fetch_key_people(x_client, db)   # Phase 2
    posts += search_hashtags(x_client, db)    # Phase 3

    for post in posts:
        post["engagement_rate"] = calculate_engagement_rate(post)
        post["high_performing"] = passes_engagement_filter(post)
        db.upsert_discovered_post(post)
```

---

## Scheduler Registration

```python
from x_agent.research_phase import run_daily_research

scheduler.add_job(
    func=run_daily_research,
    trigger=CronTrigger(hour=6, minute=0),
    id="x_agent_daily_research",
    name="X agent daily research at 06:00",
    misfire_grace_time=600,
)
```
