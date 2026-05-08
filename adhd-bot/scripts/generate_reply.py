"""
scripts/generate_reply.py — Generate and post a reply to a specific discovered_post.

Usage:
    python scripts/generate_reply.py <x_post_id>
    python scripts/generate_reply.py <x_post_id> --dry-run   # generate only, don't post
    python scripts/generate_reply.py <x_post_id> --yes       # skip confirmation prompt

Checks reply_settings before posting; aborts if the post is not open to everyone.
Saves the reply to agent_replies and marks the post reply_attempted.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from anthropic import Anthropic
from requests.exceptions import HTTPError
from x_agent import db
from x_agent.config import MODEL
from x_agent.x_client import XClient

REPLY_GENERATION_PROMPT = """
You are the engagement agent for @ADHDBrainBoost, a warm, punchy ADHD education account.
Given a post, write a single reply that:
- Adds new information, a complementary perspective, or a thoughtful question
- Is relevant to ADHD, neurodivergence, or mental health
- Is casual, science-backed, and affirming — never lecturing or sycophantic
- Is under 280 characters
- Does not repeat or paraphrase the original post
- Is not promotional or self-referential

Respond with ONLY the reply text. No explanation, no quotes, no prefix.
""".strip()


def generate_reply_text(post: dict) -> str:
    client = Anthropic()
    author_info = post.get("discovered_users") or {}
    username = author_info.get("username", "unknown")
    bio = author_info.get("bio", "")

    user_message = (
        f"Post by @{username}:\n{post.get('text', '')}\n\n"
        f"Author bio: {bio}\n"
        f"Likes: {post.get('like_count', 0)}"
    )

    response = client.messages.create(
        model=MODEL,
        system=REPLY_GENERATION_PROMPT,
        messages=[{"role": "user", "content": user_message}],
        max_tokens=300,
    )
    if not response.content:
        raise ValueError(f"Claude returned empty content (stop_reason={response.stop_reason!r})")
    return response.content[0].text.strip()


def main():
    args = sys.argv[1:]
    if not args or args[0].startswith("-"):
        print("Usage: python scripts/generate_reply.py <x_post_id> [--dry-run] [--yes]")
        sys.exit(1)

    x_post_id = args[0]
    dry_run = "--dry-run" in args
    skip_confirm = "--yes" in args

    x_client = XClient()

    post = db.get_discovered_post_by_x_id(x_post_id)
    if post is None:
        print(f"Post {x_post_id} not found in discovered_posts.")
        sys.exit(1)

    reply_settings = post.get("reply_settings", "everyone")
    if reply_settings != "everyone":
        print(f"Skipped: reply_settings={reply_settings!r} — post is not open to everyone.")
        sys.exit(0)

    if post.get("reply_attempted"):
        print(f"Skipped: reply_attempted=True for post {x_post_id}.")
        sys.exit(0)

    replies_today = db.get_reply_count_today()
    if replies_today >= 3:
        print(f"Skipped: daily reply cap reached ({replies_today}/3).")
        sys.exit(0)

    author_info = post.get("discovered_users") or {}
    username = author_info.get("username", "?")
    print(f"Post:    {x_post_id}  (@{username})")
    print(f"Text:    {post.get('text', '')[:120].replace(chr(10), ' ')}")
    print(f"Likes:   {post.get('like_count', 0)}   Replies today: {replies_today}/3")
    print()

    print("Generating reply ...")
    try:
        reply_text = generate_reply_text(post)
    except (ValueError, IndexError) as e:
        print(f"Error generating reply: {e}")
        sys.exit(1)

    print(f"Reply:   {reply_text}")
    print(f"Length:  {len(reply_text)} chars")

    if len(reply_text) > 280:
        print("Error: generated reply exceeds 280 characters — aborting.")
        sys.exit(1)

    if dry_run:
        print("\n[dry-run] Reply not posted.")
        sys.exit(0)

    if not skip_confirm:
        answer = input("\nPost this reply? [y/N] ").strip().lower()
        if answer != "y":
            print("Aborted.")
            sys.exit(0)

    try:
        result = x_client.create_reply(text=reply_text, reply_to=x_post_id)
    except HTTPError as e:
        resp = e.response
        status = resp.status_code if resp is not None else "unknown"
        print(f"Error: X API returned {status}")
        if resp is not None:
            print(f"  URL:     {resp.url}")
            print(f"  Body:    {resp.text}")
            limit = resp.headers.get("x-rate-limit-limit")
            remaining = resp.headers.get("x-rate-limit-remaining")
            if limit is not None:
                print(f"  Rate limit: {remaining}/{limit} remaining")
        sys.exit(1)

    new_post_id = result["x_post_id"]

    db.mark_reply_attempted(x_post_id)
    db.log_reply(
        x_post_id=new_post_id,
        in_reply_to=x_post_id,
        text=reply_text,
        reason=f"Manual via generate_reply.py targeting {x_post_id}",
    )

    print(f"\nPosted reply (ID: {new_post_id}).")


if __name__ == "__main__":
    main()
