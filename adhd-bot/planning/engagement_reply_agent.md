# Engagement Reply Agent — Plan

> Adds a new phase to the x_agent run loop: **pre-run research** that surfaces
> high-performing posts, followed by a dedicated `EngagementAgent` that decides
> whether to reply. The engagement step runs in addition to (not instead of) the
> warmup or growth strategy selected by the orchestrator.

---

## Motivation

The current architecture posts original content and follows users, but never
replies to posts from other accounts. Replying to high-performing posts from
reputable ADHD voices is one of the highest-leverage growth actions on X —
it surfaces the account to an already-engaged audience at the moment they are
paying attention.

---

## Updated Flow

```
Scheduler
    └── run_orchestrator()
            ├── 1. ResearchPhase.run()        → ResearchResult
            │       ├── keyword searches
            │       ├── key person timelines
            │       └── hashtag top posts
            │
            ├── 2. Orchestrator Agent (receives ResearchResult)
            │       ├── reasons about account state
            │       ├── invokes run_warmup_strategy(reason)
            │       │        OR run_growth_strategy(reason)
            │       └── invokes run_engagement_strategy(candidates)
            │               [if high-performing posts found]
            │
            └── Both steps complete independently; engagement is additive
```

**Key change:** Research moves from inside each sub-agent to a shared pre-step.
The `ResearchResult` is passed to the orchestrator so it informs both the
strategy decision and the engagement opportunity check.

---

## 1. Research Phase

### Purpose

Read today's high-performing posts from Supabase. No X API calls are made
during this step — the data was populated by the daily research job (see
[daily_research_phase.md](daily_research_phase.md)).

### Module

`x_agent/research_phase.py` — a plain database read, not an agent.

```python
@dataclass
class ResearchResult:
    high_performing: list[dict]    # posts flagged high_performing=true today
```

### Output

```python
def run_research_phase(db) -> ResearchResult:
    high_performing = db.get_todays_high_performing_posts()
    return ResearchResult(high_performing=high_performing)
```

`get_todays_high_performing_posts()` queries `discovered_posts` where
`high_performing=true`, `reply_attempted=false`, and
`discovered_at >= today 00:00`.

---

## 2. Updated Orchestrator

The orchestrator now receives `ResearchResult` in the user message and has an
additional launcher tool: `run_engagement_strategy`.

```python
ORCHESTRATOR_PROMPT = """
You are a strategy orchestrator for an ADHD tips X account.

You will receive:
- Account stats (post count, follower count, recent activity)
- A list of high-performing posts found during research (may be empty)

You must always:
1. Select and run the correct posting strategy (warmup or growth).
2. If high-performing posts are provided, also run the engagement strategy.

Decision criteria for posting strategy:
- Under 50 posts → warmup strategy
- 50+ posts → growth strategy

Always provide a clear reason for your choices.
"""

@beta_tool
def run_engagement_strategy(reason: str, candidate_post_ids: list[str]) -> str:
    """
    Run the engagement agent to evaluate and optionally reply to high-performing
    posts. Pass the IDs of candidate posts identified during research.
    Use when research surfaced one or more posts with a strong engagement rate.
    """
    agent = EngagementAgent(x_client, db)
    agent.run(reason=reason, candidate_ids=candidate_post_ids)
    return "Engagement agent completed."

def run_orchestrator():
    stats = db.get_account_stats()
    research = run_research_phase(db)                   # reads Supabase cache

    user_message = f"""
Account stats: {json.dumps(stats)}

High-performing posts found during research ({len(research.high_performing)} total):
{json.dumps(research.high_performing)}

Select and run the correct posting strategy. If high-performing posts are
listed above, also run the engagement strategy.
"""

    for message in client.beta.messages.tool_runner(
        model="claude-haiku-4-5",
        system=ORCHESTRATOR_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        tools=[run_warmup_strategy, run_growth_strategy, run_engagement_strategy],
        max_tokens=600,
    ):
        print(message)
```

---

## 3. Engagement Sub-Agent

### Purpose

Given a list of candidate posts, decide which (if any) is worth replying to,
then craft and post one reply per run (hard cap: 3 per day).

### System Prompt

```
You are the engagement agent for @ADHDBrainBoost, a warm, punchy ADHD education
account. Your job is to identify the single best reply opportunity from a list
of candidate posts and craft a genuine, value-adding reply.

Tone: same as Boost's voice — casual, science-backed, affirming. Never
lecturing, never sycophantic, never just "great point!".

A good reply MUST:
- Add new information, a complementary perspective, or a thoughtful question
- Be relevant to ADHD, neurodivergence, or mental health
- Speak to Boost's audience (adults with ADHD, families, coaches, therapists)
- Be under 280 characters
- Not repeat or merely paraphrase the original post

A good reply must NOT:
- Be off-topic from the ADHD / mental health space
- Be promotional or self-referential ("follow us for more...")
- Reply to promotional accounts, brand accounts, or anything political
- Reply if the daily reply cap (3) has already been reached

If no candidate post meets the bar, do nothing and explain why.
```

### Tools

```python
@beta_tool
def get_reply_count_today() -> str:
    """Return the number of replies the agent has posted today. Used to enforce
    the 3-reply daily cap."""
    count = db.get_reply_count_today()
    return json.dumps({"replies_today": count, "cap": 3, "can_reply": count < 3})

@beta_tool
def get_post_details(post_id: str) -> str:
    """Fetch full text, author info, and engagement metrics for a discovered post
    from the database."""
    post = db.get_discovered_post(post_id)
    return json.dumps(post)

@beta_tool
def post_reply(in_reply_to_post_id: str, text: str, reason: str) -> str:
    """Post a reply to a specific post on X. Logs the reply to database.
    reason: one sentence explaining why this post was chosen and what value
    the reply adds."""
    result = x_client.create_reply(text=text, reply_to=in_reply_to_post_id)
    db.log_reply(
        x_post_id=result.id,
        in_reply_to=in_reply_to_post_id,
        text=text,
        reason=reason,
    )
    return f"Reply posted: {text}"

@beta_tool
def skip_engagement(reason: str) -> str:
    """Call this when no candidate post meets the bar for a reply.
    reason: brief explanation of why no post was chosen."""
    db.log_skipped_engagement(reason)
    return f"Engagement skipped: {reason}"
```

### Agent Run

```python
class EngagementAgent(BaseAgent):
    system_prompt = ENGAGEMENT_SYSTEM_PROMPT

    def run(self, reason: str, candidate_ids: list[str]):
        user_message = f"""
Reason from orchestrator: {reason}

Candidate post IDs to evaluate: {json.dumps(candidate_ids)}

Steps:
1. Check reply count today (get_reply_count_today).
2. If cap is reached, call skip_engagement.
3. Otherwise, review each candidate (get_post_details).
4. Choose the single best reply opportunity or skip if none qualify.
5. If you reply, craft the text and call post_reply.
"""
        for message in client.beta.messages.tool_runner(
            model="claude-haiku-4-5",
            system=self.system_prompt,
            messages=[{"role": "user", "content": user_message}],
            tools=[
                get_reply_count_today,
                get_post_details,
                post_reply,
                skip_engagement,
            ],
            max_tokens=800,
        ):
            print(message)
```

---

## 4. Schema Changes

### New table: `agent_replies`

Tracks every reply posted (and every run where engagement was skipped), enabling
the daily cap check and providing an audit trail.

```sql
CREATE TABLE agent_replies (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    x_post_id       text,                      -- NULL if skipped
    in_reply_to     text,                      -- NULL if skipped
    text            text,                      -- NULL if skipped
    reason          text NOT NULL,             -- agent's stated reason
    skipped         boolean NOT NULL DEFAULT false,
    posted_at       timestamp NOT NULL DEFAULT now()
);
```

### Modified table: `discovered_posts`

Add two columns:

```sql
ALTER TABLE discovered_posts
    ADD COLUMN engagement_rate   numeric,     -- calculated at collection time
    ADD COLUMN reply_attempted   boolean NOT NULL DEFAULT false;
```

`reply_attempted` is set to `true` after the engagement agent evaluates the
post (regardless of whether a reply was sent), preventing the same post from
being re-evaluated across runs.

---

## 5. Database Helpers (db.py)

| Helper | Purpose |
|---|---|
| `get_reply_count_today()` | Count rows in `agent_replies` where `skipped=false` and `posted_at >= today 00:00` |
| `log_reply(x_post_id, in_reply_to, text, reason)` | Insert into `agent_replies` with `skipped=false` |
| `log_skipped_engagement(reason)` | Insert into `agent_replies` with `skipped=true`, `x_post_id=NULL` |
| `get_discovered_post(post_id)` | Fetch post details from `discovered_posts` |
| `mark_reply_attempted(post_id)` | Set `reply_attempted=true` on a discovered post |

---

## 6. Files to Create / Modify

| File | Action |
|---|---|
| `x_agent/research_phase.py` | **Create** — shared pre-run research; returns `ResearchResult` |
| `x_agent/agents/engagement_agent.py` | **Create** — `EngagementAgent` class |
| `x_agent/orchestrator.py` | **Modify** — call research phase, add `run_engagement_strategy` tool, pass research results to user message |
| `x_agent/db.py` | **Extend** — add reply/skip log helpers, `get_reply_count_today`, `get_discovered_post` |
| `x_agent/agents/warmup_agent.py` | **Modify** — remove internal research (now handled by research phase) |
| `x_agent/agents/growth_agent.py` | **Modify** — remove internal research (now handled by research phase) |
| `scripts/engagement_migration.sql` | **Create** — `agent_replies` table + `discovered_posts` column additions |

---

## 7. Rate Limit & Cost Impact

### Reply cap
- **1 reply per run, 3 per day** — enforced by `get_reply_count_today()` at the
  start of each engagement agent run.
- The cap is stored in `agent_replies` so it survives across runs/restarts.

### X API cost

The research phase makes no X API calls — it reads from the Supabase cache
populated by the daily research job (see [daily_research_phase.md](daily_research_phase.md),
~$0.42/day). The only X API call added by this flow is a single `POST /2/tweets`
(reply) when the engagement agent fires — same endpoint and cost as a regular tweet.

| Operation | Calls/run | Est. cost |
|---|---|---|
| Research phase (Supabase read only) | 0 X API calls | $0.00 |
| Reply post (if triggered, max 1/run) | 0–1 | per-post cost |

---

## 8. Design Principles (additions)

- **Research is shared, not duplicated** — one research pass feeds both strategy
  selection and the engagement decision.
- **Engagement is additive** — the orchestrator always runs a posting strategy;
  the engagement agent is a bonus step, never a replacement.
- **Agent decides, not heuristics** — the engagement filter (engagement rate)
  surfaces candidates, but the agent makes the final call using the full
  context of Boost's guidelines.
- **Every decision is logged** — both replies and skips are written to
  `agent_replies` so the daily cap is auditable and the system is debuggable.
- **`reply_attempted` prevents re-evaluation** — a post the agent has already
  seen will not be re-queued in a future run.
