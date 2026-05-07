# X Social Media Agent — Orchestrator + Sub-Agent Architecture

## Overview

This document summarises the design for an autonomous X (Twitter) growth agent built with the **Anthropic Python SDK**, **X API v2**, **Supabase**, and **APScheduler**. The system uses a multi-agent architecture where a top-level orchestrator reasons about account state and delegates to specialised sub-agents.

---

## Architecture

```
Scheduler (APScheduler)
    └── Orchestrator Agent
            ├── Reads account stats from Supabase
            ├── Reasons about the best strategy
            └── Invokes one of:
                    ├── WarmupAgent     (< 50 posts)
                    └── GrowthAgent     (≥ 50 posts)
```

Each agent uses the **Anthropic SDK Tool Runner** to manage the agentic loop automatically — no manual `while` loop or `tool_result` formatting required.

---

## Project Structure

```
x_agent/
├── main.py                  # Scheduler entry point
├── orchestrator.py          # Top-level strategy selection agent
├── x_client.py              # X API v2 wrapper (Tweepy)
├── db.py                    # Supabase read/write layer
├── config.py                # API keys and constants
└── agents/
    ├── base_agent.py        # Shared tools and tool runner logic
    ├── warmup_agent.py      # High-frequency posting for new accounts
    └── growth_agent.py      # Balanced posting + following for established accounts
```

---

## Key Components

### 1. SDK Tool Runner

As of Anthropic SDK `v0.68.0`, the tool runner handles the entire agentic loop:

- Automatically calls tool functions when Claude requests them
- Sends `tool_result` blocks back to Claude
- Iterates until Claude reaches a final response
- Supports automatic context compaction for long-running tasks

```python
for message in client.beta.tools.runner(
    model="claude-haiku-4-5",
    system=SYSTEM_PROMPT,
    messages=[{"role": "user", "content": "Run your growth tasks now."}],
    tools=[search_posts, post_tweet, follow_user],
    max_tokens=1000,
):
    print(message)
```

---

### 2. Tools (Shared Across All Agents)

Tools are defined with the `@tool` decorator. Each tool also writes to Supabase as a side effect.

```python
@client.beta.tools.tool
def search_posts(query: str, max_results: int = 10) -> str:
    """Search recent X posts by keyword. Saves results to database."""
    results = x_client.search_recent(query, max_results)
    db.save_posts_and_users(results)   # ← persists to Supabase
    return json.dumps(results)

@client.beta.tools.tool
def post_tweet(text: str) -> str:
    """Post a new tweet to X. Logs the tweet to database."""
    post = x_client.create_tweet(text)
    db.log_tweet(post)                 # ← persists to Supabase
    return f"Posted: {text}"

@client.beta.tools.tool
def follow_user(user_id: str) -> str:
    """Follow a user by their X user ID. Updates follow status in database."""
    x_client.follow(user_id)
    db.mark_followed(user_id)          # ← persists to Supabase
    return f"Followed user {user_id}"
```

---

### 3. Supabase Schema

Data is saved at the point of discovery — before Claude decides what action to take — giving Claude richer context and preventing duplicate follows.

#### `discovered_users`
| column | type | notes |
|---|---|---|
| `id` | uuid | Primary key |
| `x_user_id` | text | Unique |
| `username` | text | |
| `bio` | text | |
| `followers_count` | int | |
| `followed_by_agent` | bool | Default false |
| `followed_at` | timestamp | Nullable |
| `discovered_at` | timestamp | |

#### `discovered_posts`
| column | type | notes |
|---|---|---|
| `id` | uuid | Primary key |
| `x_post_id` | text | Unique |
| `author_x_id` | text | FK → discovered_users |
| `text` | text | |
| `like_count` | int | |
| `search_query` | text | Query that surfaced the post |
| `discovered_at` | timestamp | |

#### `agent_tweets`
| column | type | notes |
|---|---|---|
| `id` | uuid | Primary key |
| `x_post_id` | text | Returned by X API |
| `text` | text | |
| `posted_at` | timestamp | |

#### `agent_runs`
| column | type | notes |
|---|---|---|
| `id` | uuid | Primary key |
| `run_at` | timestamp | |
| `strategy_selected` | text | e.g. `warmup`, `growth` |
| `reason` | text | Orchestrator's stated reasoning |
| `post_count_at_time` | int | Snapshot for auditing |

---

### 4. Orchestrator Agent

The orchestrator is a Claude agent whose tools are **agent launchers**, not X API calls. It reads account stats, reasons about strategy, and delegates.

```python
ORCHESTRATOR_PROMPT = """
You are a strategy orchestrator for an ADHD tips X account.
Assess the account's current state and call the correct strategy tool.

Decision criteria:
- Under 50 posts → warmup strategy (post more, follow less)
- 50+ posts → growth strategy (balanced posting and following)

Always provide a clear reason for your choice.
"""

@client.beta.tools.tool
def run_warmup_strategy(reason: str) -> str:
    """Run the warmup agent. Use for new accounts with fewer than 50 posts."""
    agent = WarmupAgent(x_client, db)
    agent.run(f"Reason: {reason}")
    return "Warmup agent completed."

@client.beta.tools.tool
def run_growth_strategy(reason: str) -> str:
    """Run the growth agent. Use for established accounts with 50+ posts."""
    agent = GrowthAgent(x_client, db)
    agent.run(f"Reason: {reason}")
    return "Growth agent completed."

def run_orchestrator():
    stats = db.get_account_stats()
    for message in client.beta.tools.runner(
        model="claude-haiku-4-5",
        system=ORCHESTRATOR_PROMPT,
        messages=[{
            "role": "user",
            "content": f"Account stats: {json.dumps(stats)}. Select and run the best strategy."
        }],
        tools=[run_warmup_strategy, run_growth_strategy],
        max_tokens=500,
    ):
        print(message)
```

The `reason` parameter is intentional — it forces Claude to articulate its decision, making logs in `agent_runs` readable and debuggable.

---

### 5. Sub-Agents

Sub-agents share the same tools but have different system prompts that define their priorities and constraints.

#### `WarmupAgent` — New accounts (< 50 posts)

```python
class WarmupAgent(BaseAgent):
    system_prompt = """
    You are managing a NEW X account (under 50 posts).
    Your job is to establish a content foundation.

    Each run:
    - Post 2-3 tweets covering different ADHD subtopics
    - Search 1-2 relevant queries
    - Follow up to 3 highly relevant accounts
    - Prioritise content variety over following
    - Do NOT post the same topic twice in a row
    """
```

#### `GrowthAgent` — Established accounts (≥ 50 posts)

```python
class GrowthAgent(BaseAgent):
    system_prompt = """
    You are managing an ESTABLISHED X account (50+ posts).
    Your job is to grow an engaged audience steadily.

    Each run:
    - Post 1 high-quality tweet
    - Search 2-3 queries to find relevant users
    - Follow up to 5 targeted accounts
    - Prioritise accounts with visible engagement signals
    """
```

---

### 6. Scheduler

`main.py` runs on a fixed interval. The orchestrator determines the appropriate agent and cadence internally.

```python
from apscheduler.schedulers.blocking import BlockingScheduler
from orchestrator import run_orchestrator

scheduler = BlockingScheduler()
scheduler.add_job(run_orchestrator, 'interval', hours=1)
scheduler.start()
```

The scheduler runs hourly. The `WarmupAgent` posts 2-3 tweets per run; the `GrowthAgent` posts 1. This naturally creates a higher posting cadence early on without requiring separate schedules.

---

## Agent System Prompt

The shared niche prompt used across all agents:

```
You are an X (Twitter) growth agent for an ADHD tips and advice account.

Tone: Casual and conversational — like a knowledgeable friend.
Audience: People with ADHD, families, therapists, coaches, mental health advocates.

Tweet guidelines:
- Max 280 characters
- Lead with a relatable hook
- Include a concrete, actionable tip when possible
- 1-2 hashtags max (#ADHD, #ADHDtips)
- Never stigmatise mental health

Who to follow:
- Posts regularly about ADHD, neurodivergence, or mental health
- Has an engaged audience
- Not a bot or promotional account

After each run, summarise what you searched, posted, and followed in 2-3 sentences.
```

---

## Extending the System

Adding a new strategy requires two steps only:

1. Create a new agent class in `agents/`
2. Add a launcher tool to the orchestrator

Claude will automatically consider the new tool based on its description.

```python
@client.beta.tools.tool
def run_engagement_strategy(reason: str) -> str:
    """
    Run when follower count is high but engagement is low.
    Focuses on replying to trending ADHD posts rather than posting new content.
    """
    agent = EngagementAgent(x_client, db)
    agent.run(reason)
    return "Engagement agent completed."
```

---

## Dependencies

```
anthropic>=0.68.0
tweepy
supabase
apscheduler
python-dotenv
```

---

## X API v2 Rate Limits (Free Tier)

| Action | Limit |
|---|---|
| Search | 1 request / 15 min |
| Post tweet | 17 / 24h |
| Follow | 400 / day |

The hourly scheduler with conservative per-run limits (2-3 tweets warmup, 1 tweet growth) stays comfortably within these limits.

---

## Design Principles

- **Orchestrator reasons, sub-agents act** — separation of strategy selection from execution
- **Tools are the same, prompts differ** — specialisation lives in the system prompt, not the tool layer
- **Supabase writes happen at discovery** — data is saved before Claude acts, enabling informed decisions and preventing duplicate follows
- **`reason` is always logged** — every orchestrator decision is explainable and auditable
- **Adding strategies is additive** — new agents don't touch existing code
