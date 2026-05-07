"""
poster.py — Handles selecting and posting ADHD content tweets
"""

import random
from loguru import logger
from bot.auth import get_client
from bot.database import mark_posted, get_posted_ids, get_content_items

HASHTAGS = {
    "fact": "#ADHD #ADHDFacts #Neurodiversity",
    "tip":  "#ADHD #ADHDTips #ADHDAdults",
}

CATEGORY_CYCLE = ["tip", "fact", "tip"]  # morning=tip, noon=fact, evening=tip


def pick_item(type: str) -> dict | None:
    posted = get_posted_ids(type)
    items = get_content_items(type)

    available = [item for item in items if item["content_id"] not in posted]

    if not available:
        logger.warning(f"All {type} content has been posted. Cycling back.")
        available = items

    if not available:
        logger.error(f"No content found for type: {type}")
        return None

    return random.choice(available)


def format_tweet(item: dict, type: str) -> str:
    tags = HASHTAGS.get(type, "#ADHD")
    text = item["text"]

    if not item.get("emoji"):
        prefix = "🧠 " if type == "fact" else "✨ "
    else:
        prefix = item["emoji"] + " "

    tweet = f"{prefix}{text}\n\n{tags}"

    if len(tweet) > 280:
        max_text_len = 280 - len(prefix) - len(tags) - 4
        tweet = f"{prefix}{text[:max_text_len]}…\n\n{tags}"

    return tweet


def post_scheduled(cycle_index: int = 0):
    type = CATEGORY_CYCLE[cycle_index % len(CATEGORY_CYCLE)]
    item = pick_item(type)

    if not item:
        logger.error("Could not find content to post. Skipping.")
        return

    tweet_text = format_tweet(item, type)

    try:
        from xdk.posts.models import CreateRequest
        client = get_client()
        response = client.posts.create(body=CreateRequest(text=tweet_text))
        tweet_id = response.data.id
        mark_posted(item["content_id"], type, tweet_id)
        logger.info(f"✅ Posted [{type}] tweet ID {tweet_id}: {tweet_text[:60]}…")
    except Exception as e:
        logger.error(f"❌ Failed to post tweet: {e}")
