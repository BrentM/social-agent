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
            │       └── reads discovered_posts (populated by warmup/growth agents)
            │
            ├── 2. Orchestrator Agent (receives ResearchResult + account stats)
            │       ├── reasons about account state
            │       ├── invokes run_warmup_strategy(reason)
            │       │        OR run_growth_strategy(reason)
            │       └── invokes run_engagement_strategy(candidates)
            │               [if research returned posts]
            │
            └── Both steps complete independently; engagement is additive
```

**Key change:** The research phase is a zero-cost database read. The warmup and
growth agents already write discovered posts to Supabase during their normal
runs — the engagement agent reuses that data rather than making additional X API
calls. No separate research job is required.

---

## 1. Research Phase

### Purpose

Read recent posts from `discovered_posts` in Supabase. The warmup and growth
agents already populate this table during their normal search-and-follow runs,
so no X API calls are needed here.

If no posts are found (agents haven't run yet, or all recent posts are already
evaluated), the orchestrator still runs the posting strategy and silently skips
engagement.

### Module

`x_agent/research_phase.py` — plain database read, not an agent.

```python
@dataclass
class ResearchResult:
    posts: list[dict]    # recent, unevaluated posts from discovered_posts
```

### Query

```python
def run_research_phase(db) -> ResearchResult:
    posts = db.get_recent_unevaluated_posts()
    return ResearchResult(posts=posts)
```

`get_recent_unevaluated_posts()` queries `discovered_posts` where:
- `reply_attempted = false`
- `discovered_at >= NOW() - INTERVAL '24 hours'`
- `like_count >= 10` — coarse filter to avoid passing low-signal posts to the agent

Results are ordered by `like_count DESC` so the agent sees the strongest
candidates first.

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
        max_tokens=1000,
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

All post IDs passed between the orchestrator and engagement agent are
`x_post_id` values (X's own tweet ID, e.g. `"1234567890"`), not internal
Supabase UUIDs.

```python
@beta_tool
def get_reply_count_today() -> str:
    """Return the number of replies the agent has posted today. Used to enforce
    the 3-reply daily cap."""
    count = db.get_reply_count_today()
    return json.dumps({"replies_today": count, "cap": 3, "can_reply": count < 3})

@beta_tool
def get_post_details(x_post_id: str) -> str:
    """Fetch full text, author info, and engagement metrics for a discovered post
    from the database. x_post_id is X's tweet ID (not the internal UUID)."""
    post = db.get_discovered_post_by_x_id(x_post_id)
    return json.dumps(post)

@beta_tool
def post_reply(in_reply_to_x_post_id: str, text: str, reason: str) -> str:
    """Post a reply to a specific post on X. Logs the reply to database and
    marks the post as evaluated so it is not re-queued.
    reason: one sentence explaining why this post was chosen and what value
    the reply adds."""
    result = x_client.create_reply(text=text, reply_to=in_reply_to_x_post_id)
    db.log_reply(
        x_post_id=result.id,
        in_reply_to=in_reply_to_x_post_id,
        text=text,
        reason=reason,
    )
    db.mark_reply_attempted(in_reply_to_x_post_id)   # prevent re-evaluation
    return f"Reply posted: {text}"

@beta_tool
def skip_engagement(reason: str, evaluated_x_post_ids: list[str]) -> str:
    """Call this when no candidate post meets the bar for a reply.
    reason: brief explanation of why no post was chosen.
    evaluated_x_post_ids: all post IDs that were considered, so they are not
    re-queued in future runs."""
    db.log_skipped_engagement(reason)
    for x_post_id in evaluated_x_post_ids:
        db.mark_reply_attempted(x_post_id)
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
2. If cap is reached, call skip_engagement with all candidate IDs.
3. Otherwise, review each candidate (get_post_details).
4. Choose the single best reply opportunity or skip if none qualify.
5. If you reply, craft the text and call post_reply.
6. If you skip, call skip_engagement with all candidate IDs you reviewed.
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

One column added to the existing table:

```sql
ALTER TABLE discovered_posts
    ADD COLUMN reply_attempted boolean NOT NULL DEFAULT false;
```

`reply_attempted` is set to `true` by the engagement agent after evaluating a
post (via `post_reply` or `skip_engagement`), preventing re-evaluation in
future runs. This is the only schema dependency this plan has on `discovered_posts`
— the `engagement_rate` and `high_performing` columns belong to
[daily_research_phase.md](daily_research_phase.md) and are not required here.

---

## 5. Database Helpers (db.py)

| Helper | Purpose |
|---|---|
| `get_recent_unevaluated_posts()` | Query `discovered_posts` where `reply_attempted=false`, `discovered_at >= NOW() - INTERVAL '24 hours'`, `like_count >= 10`; ordered by `like_count DESC` |
| `get_discovered_post_by_x_id(x_post_id)` | Fetch full post details from `discovered_posts` by X tweet ID |
| `get_reply_count_today()` | Count rows in `agent_replies` where `skipped=false` and `posted_at >= NOW() - INTERVAL '24 hours'` |
| `log_reply(x_post_id, in_reply_to, text, reason)` | Insert into `agent_replies` with `skipped=false` |
| `log_skipped_engagement(reason)` | Insert into `agent_replies` with `skipped=true`, `x_post_id=NULL` |
| `mark_reply_attempted(x_post_id)` | Set `reply_attempted=true` on a `discovered_posts` row; called inside `post_reply` and `skip_engagement` tools |

---

## 6. Files to Create / Modify

| File | Action |
|---|---|
| `x_agent/research_phase.py` | **Create** — lightweight pre-run topic search; returns `ResearchResult` |
| `x_agent/agents/engagement_agent.py` | **Create** — `EngagementAgent` class |
| `x_agent/orchestrator.py` | **Modify** — call research phase, add `run_engagement_strategy` tool, pass research results to user message |
| `x_agent/db.py` | **Extend** — add helpers listed in Section 5 |
| `scripts/engagement_migration.sql` | **Create** — `agent_replies` table only; `discovered_posts` columns are owned by `daily_research_phase.md` |

The warmup and growth agents are not modified — they continue to do their own
follow-discovery research independently of this flow.

---

## 7. Rate Limit & Cost Impact

### Reply cap
- **1 reply per run, 3 per day** — enforced by `get_reply_count_today()` at the
  start of each engagement agent run.
- The cap is stored in `agent_replies` so it survives across runs/restarts.

### X API cost

The research phase makes no X API calls — it reads from `discovered_posts`
already populated by the warmup and growth agents. The only X API call added
by this entire flow is a single `POST /2/tweets` (reply) when the engagement
agent fires.

| Operation | X API calls/run | Est. cost |
|---|---|---|
| Research phase (Supabase read) | 0 | $0.00 |
| Reply post (if triggered, max 1/run) | 0–1 | per-post cost |

No additional API budget is required beyond what warmup and growth already spend.

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
