"""
base_agent.py — Shared tools and base agent class for the growth system.
"""

import json
from anthropic import Anthropic, beta_tool
from loguru import logger
from requests.exceptions import HTTPError
from x_agent.config import MODEL, AGENT_MAX_TOKENS

SHARED_NICHE_PROMPT = """
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
"""


def make_tools(x_client, db) -> list:
    @beta_tool
    def search_posts(query: str, max_results: int = 10) -> str:
        """Search recent X posts by keyword. Returns posts with author info. Saves results to database."""
        results = x_client.search_posts(query, max_results)
        db.save_posts_and_users(results["posts"], results["users"])
        # Return a condensed view so Claude can reason about who to follow
        condensed = [
            {
                "post_id": p["x_post_id"],
                "text": p["text"],
                "likes": p["like_count"],
                "author_id": p["author_x_id"],
                "author_username": p["author_username"],
                "author_followers": p["author_followers"],
                "author_bio": p["author_bio"],
            }
            for p in results["posts"]
        ]
        return json.dumps(condensed)

    @beta_tool
    def post_tweet(text: str) -> str:
        """Post a new tweet to X. Must be 280 characters or fewer. Logs the tweet to the database."""
        if len(text) > 280:
            return f"Error: Tweet is {len(text)} characters, must be 280 or fewer. Please shorten it."
        post = x_client.post_tweet(text)
        db.log_tweet(post["x_post_id"], text)
        logger.info(f"Posted tweet: {text[:60]}...")
        return f"Posted successfully (ID: {post['x_post_id']})"

    @beta_tool
    def follow_user(user_id: str) -> str:
        """Follow a user by their X user ID (from search_posts results). Updates follow status in database."""
        if db.is_already_followed(user_id):
            return f"Already following user {user_id} — skipping."
        try:
            x_client.follow_user(user_id)
        except HTTPError as e:
            status = e.response.status_code if e.response is not None else "unknown"
            logger.warning(f"Failed to follow user {user_id}: HTTP {status}")
            if status == 400:
                db.mark_followed(user_id)  # X says already following; sync DB
                return f"Already following user {user_id} on X (DB was out of sync)."
            return f"Could not follow user {user_id}: HTTP {status}."
        db.mark_followed(user_id)
        logger.info(f"Followed user {user_id}")
        return f"Successfully followed user {user_id}."

    return [search_posts, post_tweet, follow_user]


class BaseAgent:
    system_prompt = ""

    def __init__(self, x_client, db):
        self._x_client = x_client
        self._db = db
        self._tools = make_tools(x_client, db)
        self._client = Anthropic()

    def run(self, user_message: str) -> str:
        full_system = self.system_prompt.strip() + "\n\n" + SHARED_NICHE_PROMPT.strip()
        runner = self._client.beta.messages.tool_runner(
            model=MODEL,
            system=full_system,
            messages=[{"role": "user", "content": user_message}],
            tools=self._tools,
            max_tokens=AGENT_MAX_TOKENS,
        )
        final = runner.until_done()
        # Extract the last text block as the agent's summary
        for block in reversed(list(final.content)):
            if hasattr(block, "text"):
                return block.text
        return ""
