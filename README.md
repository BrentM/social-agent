# ADHD Bot — X Growth Agent

An autonomous X (Twitter) growth agent for an ADHD tips account. Built with the Anthropic Python SDK, X API v2, Supabase, and APScheduler.

The relevant code lives entirely in [adhd-bot/x_agent/](adhd-bot/x_agent/).

See example logs from the running bot in Sample-logs.txt

---

## How it works

A scheduler fires hourly. Each run, an **Orchestrator** agent reads account stats from Supabase, reasons about which strategy to apply, and delegates to a sub-agent:

```
APScheduler (hourly)
    └── Orchestrator Agent (claude-haiku-4-5)
            ├── reads post_count from Supabase
            └── delegates to:
                    ├── WarmupAgent   (< 50 posts) — post more, follow less
                    └── GrowthAgent   (≥ 50 posts) — balanced posting + following
```

All agents use the Anthropic SDK's `tool_runner` — no manual agentic loop needed.

---

## Project structure

```
adhd-bot/x_agent/
├── main.py            # Scheduler entry point
├── orchestrator.py    # Reads stats, selects and runs a strategy
├── config.py          # Model, thresholds, token limits
├── x_client.py        # X API v2 wrapper (xdk)
├── db.py              # Supabase read/write helpers
└── agents/
    ├── base_agent.py  # Shared tools (search_posts, post_tweet, follow_user) + BaseAgent
    ├── warmup_agent.py
    └── growth_agent.py
```

---

## Setup

### 1. Install dependencies

```bash
cd adhd-bot
python -m venv .venv
source .venv/bin/activate
pip install anthropic xdk supabase apscheduler python-dotenv loguru
```

### 2. Configure environment

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp adhd-bot/.env.example adhd-bot/.env
```

Required variables:

| Variable | Description |
|---|---|
| `CONSUMER_KEY` | X API OAuth1 consumer key |
| `CONSUMER_KEY_SECRET` | X API OAuth1 consumer key secret |
| `ACCESS_TOKEN` | X API OAuth1 access token |
| `ACCESS_TOKEN_SECRET` | X API OAuth1 access token secret |
| `BEARER_TOKEN` | X API bearer token (for search) |
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |

Set `X_API_BASE_URL=http://localhost:8080` to point at a local X API playground instead of the live API.

### 3. Create Supabase tables

Run the following in your Supabase SQL editor:

```sql
create table discovered_users (
    id uuid primary key default gen_random_uuid(),
    x_user_id text unique not null,
    username text,
    bio text,
    followers_count int default 0,
    followed_by_agent bool default false,
    followed_at timestamptz,
    discovered_at timestamptz default now()
);

create table discovered_posts (
    id uuid primary key default gen_random_uuid(),
    x_post_id text unique not null,
    author_x_id text references discovered_users(x_user_id),
    text text,
    like_count int default 0,
    search_query text,
    discovered_at timestamptz default now()
);

create table agent_tweets (
    id uuid primary key default gen_random_uuid(),
    x_post_id text,
    text text,
    posted_at timestamptz default now()
);

create table agent_runs (
    id uuid primary key default gen_random_uuid(),
    run_at timestamptz default now(),
    strategy_selected text,
    reason text,
    post_count_at_time int
);
```

---

## Running

```bash
cd adhd-bot
python -m x_agent.main
```

Runs immediately on startup, then every hour. Logs go to `logs/x_agent.log` and stdout. Stop with `Ctrl+C`.

---

## Agent behaviour

### WarmupAgent (< 50 posts)

Focuses on building a content foundation:
- Posts 2-3 tweets covering different ADHD subtopics per run
- Searches 1-2 queries
- Follows up to 3 highly relevant accounts

### GrowthAgent (≥ 50 posts)

Focuses on steady audience growth:
- Posts 1 high-quality tweet per run
- Searches 2-3 queries to find relevant users
- Follows up to 5 targeted accounts

Both agents share the same three tools (`search_posts`, `post_tweet`, `follow_user`) — specialisation lives in the system prompt, not the tool layer. Discovered users and posts are written to Supabase before Claude decides what to do, giving it richer context and preventing duplicate follows.

---

## Extending

To add a new strategy, create a class in `agents/` and add a launcher tool to `orchestrator.py`. Claude will automatically consider the new tool based on its docstring.

```python
@beta_tool
def run_engagement_strategy(reason: str) -> str:
    """Run when follower count is high but engagement is low. Focuses on replying to trending ADHD posts."""
    agent = EngagementAgent(x_client, db)
    agent.run(reason)
    return "Engagement agent completed."
```

---

## X API rate limits

As of early 2026, X API is pay-per-use. Set a monthly spending cap in the X Developer Console.

| Action | Limit | Notes |
|---|---|---|
| Search recent | 450 req / 15 min | Primary cost driver |
| Post tweet | 17 / 24h per user | Warmup: 2-3/run; Growth: 1/run — stays under limit |
| Follow user | 400 / day (ToS) | Conservative per-run limits stay well under |

---

## Dependencies

- `anthropic >= 0.68.0` — SDK tool runner for the agentic loop
- `xdk >= 0.9.0` — X API v2 client
- `supabase` — persistence layer
- `apscheduler` — hourly scheduler
- `python-dotenv` — environment config
- `loguru` — structured logging
