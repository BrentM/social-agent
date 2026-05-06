"""
poster.py — Handles selecting and posting ADHD content tweets
"""

import json
import random
import os
from loguru import logger
from bot.auth import get_client
from bot.database import mark_posted, get_posted_ids

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "content")

HASHTAGS = {
    "facts": "#ADHD #ADHDFacts #Neurodiversity",
    "tips":  "#ADHD #ADHDTips #ADHDAdults",
}

CATEGORY_CYCLE = ["tips", "facts", "tips"]  # morning=tip, noon=fact, evening=tip


def load_content(category: str) -> list[dict]:
    """Loads content items from the JSON library."""
    path = os.path.join(CONTENT_DIR, f"{category}.json")
    with open(path, "r") as f:
        return json.load(f)


def pick_item(category: str) -> dict | None:
    """
    Picks a random unposted item from the given category.
    If all items have been posted, resets and allows repeats.
    """
    items = load_content(category)
    posted = get_posted_ids(category)

    available = [item for item in items if item["id"] not in posted]

    if not available:
        logger.warning(f"All {category} content has been posted. Cycling back.")
        available = items  # reset cycle

    if not available:
        logger.error(f"No content found for category: {category}")
        return None

    return random.choice(available)


def format_tweet(item: dict, category: str) -> str:
    """
    Formats an item dict into a tweet string with hashtags.
    Trims if over 280 characters.
    """
    tags = HASHTAGS.get(category, "#ADHD")
    text = item["text"]

    # Add emoji prefix if not already present
    if not item.get("emoji"):
        prefix = "🧠 " if category == "facts" else "✨ "
    else:
        prefix = item["emoji"] + " "

    tweet = f"{prefix}{text}\n\n{tags}"

    if len(tweet) > 280:
        # Trim text to fit
        max_text_len = 280 - len(prefix) - len(tags) - 4  # 4 for "\n\n"
        tweet = f"{prefix}{text[:max_text_len]}…\n\n{tags}"

    return tweet


def post_scheduled(cycle_index: int = 0):
    """
    Posts a tweet. cycle_index (0, 1, 2) determines the content category
    based on CATEGORY_CYCLE.
    """
    category = CATEGORY_CYCLE[cycle_index % len(CATEGORY_CYCLE)]
    item = pick_item(category)

    if not item:
        logger.error("Could not find content to post. Skipping.")
        return

    tweet_text = format_tweet(item, category)

    try:
        client = get_client()
        response = client.create_tweet(text=tweet_text)
        tweet_id = response.data["id"]
        mark_posted(item["id"], category, tweet_id)
        logger.info(f"✅ Posted [{category}] tweet ID {tweet_id}: {tweet_text[:60]}…")
    except Exception as e:
        logger.error(f"❌ Failed to post tweet: {e}")
