"""
engagement_agent.py — Evaluates candidate posts and optionally replies to one per run.
"""

import json
from anthropic import Anthropic, beta_tool
from loguru import logger
from requests.exceptions import HTTPError
from x_agent.config import MODEL, AGENT_MAX_TOKENS

ENGAGEMENT_SYSTEM_PROMPT = """
You are the engagement agent for @ADHDBrainBoost, a warm, punchy ADHD education account.
Your job is to identify the single best reply opportunity from a list of candidate posts
and craft a genuine, value-adding reply.

Tone: casual, science-backed, affirming. Never lecturing, never sycophantic,
never just "great point!".

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
""".strip()


class EngagementAgent:
    def __init__(self, x_client, db):
        self._x_client = x_client
        self._db = db
        self._client = Anthropic()

    def _make_tools(self):
        db = self._db
        x_client = self._x_client

        @beta_tool
        def get_reply_count_today() -> str:
            """Return the number of replies posted today. Used to enforce the 3-reply daily cap."""
            count = db.get_reply_count_today()
            return json.dumps({"replies_today": count, "cap": 3, "can_reply": count < 3})

        @beta_tool
        def get_post_details(x_post_id: str) -> str:
            """Fetch full text, author info, and engagement metrics for a candidate post.
            x_post_id is X's tweet ID."""
            post = db.get_discovered_post_by_x_id(x_post_id)
            if post is None:
                return json.dumps({"error": f"Post {x_post_id} not found."})
            return json.dumps(post)

        @beta_tool
        def post_reply(in_reply_to_x_post_id: str, text: str, reason: str) -> str:
            """Post a reply to a specific post on X. Logs the reply and marks the post as evaluated.
            reason: one sentence explaining why this post was chosen and what value the reply adds."""
            if len(text) > 280:
                return f"Error: reply is {len(text)} characters, must be 280 or fewer. Shorten it."
            post_meta = db.get_discovered_post_by_x_id(in_reply_to_x_post_id)
            if post_meta and post_meta.get("reply_settings", "everyone") != "everyone":
                return json.dumps({"error": f"Post {in_reply_to_x_post_id} has reply_settings={post_meta['reply_settings']}; skipping."})
            try:
                result = x_client.create_reply(text=text, reply_to=in_reply_to_x_post_id)
            except HTTPError as e:
                status = e.response.status_code if e.response is not None else "unknown"
                logger.error(f"X API error {status} posting reply: {e}")
                db.mark_reply_attempted(in_reply_to_x_post_id)
                return json.dumps({"error": f"X API returned {status}: {e}"})
            db.log_reply(
                x_post_id=result["x_post_id"],
                in_reply_to=in_reply_to_x_post_id,
                text=text,
                reason=reason,
            )
            db.mark_reply_attempted(in_reply_to_x_post_id)
            logger.info(f"Posted reply to {in_reply_to_x_post_id}: {text[:60]}...")
            return f"Reply posted (ID: {result['x_post_id']}): {text}"

        @beta_tool
        def skip_engagement(reason: str, evaluated_x_post_ids: list[str]) -> str:
            """Call when no candidate post meets the bar for a reply.
            reason: brief explanation. evaluated_x_post_ids: all IDs considered."""
            db.log_skipped_engagement(reason)
            for x_post_id in evaluated_x_post_ids:
                db.mark_reply_attempted(x_post_id)
            logger.info(f"Engagement skipped: {reason}")
            return f"Engagement skipped: {reason}"

        return [get_reply_count_today, get_post_details, post_reply, skip_engagement]

    def run(self, reason: str, candidate_ids: list[str]) -> None:
        user_message = f"""Reason from orchestrator: {reason}

Candidate post IDs to evaluate: {json.dumps(candidate_ids)}

Steps:
1. Check reply count today (get_reply_count_today).
2. If cap is reached, call skip_engagement with all candidate IDs.
3. Otherwise, review each candidate (get_post_details).
4. Choose the single best reply opportunity or skip if none qualify.
5. If you reply, craft the text and call post_reply.
6. If you skip, call skip_engagement with all candidate IDs you reviewed.
"""
        runner = self._client.beta.messages.tool_runner(
            model=MODEL,
            system=ENGAGEMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
            tools=self._make_tools(),
            max_tokens=AGENT_MAX_TOKENS,
        )
        runner.until_done()
        logger.info("Engagement agent run complete.")
