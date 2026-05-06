"""
follower.py — Discovers and follows relevant ADHD-related accounts
"""

import json
import os
import time
from loguru import logger
from bot.auth import get_client
from bot.database import has_followed, mark_followed, get_daily_follow_count

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "content")
MAX_DAILY_FOLLOWS = int(os.getenv("MAX_DAILY_FOLLOWS", 20))


def load_follow_targets() -> dict:
    path = os.path.join(CONTENT_DIR, "follow_targets.json")
    with open(path, "r") as f:
        return json.load(f)


def run_follow_job():
    """
    Searches for relevant accounts and follows them, up to the daily limit.
    Runs once per day.
    """
    already_followed_today = get_daily_follow_count()
    remaining = MAX_DAILY_FOLLOWS - already_followed_today

    if remaining <= 0:
        logger.info(f"Daily follow limit ({MAX_DAILY_FOLLOWS}) already reached. Skipping.")
        return

    logger.info(f"🔎 Starting follow job. Can follow {remaining} more accounts today.")

    targets = load_follow_targets()
    search_queries = targets.get("search_queries", [])

    client = get_client()
    me = client.get_me()
    if not me.data:
        logger.error("Could not fetch bot user info.")
        return
    bot_user_id = str(me.data.id)

    followed_count = 0

    for query in search_queries:
        if followed_count >= remaining:
            break

        logger.info(f"  Searching: '{query}'")

        try:
            results = client.search_recent_tweets(
                query=query + " lang:en -is:retweet",
                max_results=10,
                expansions=["author_id"],
                user_fields=["public_metrics", "description"],
            )

            if not results.includes or "users" not in results.includes:
                continue

            for user in results.includes["users"]:
                if followed_count >= remaining:
                    break

                user_id = str(user.id)

                # Skip the bot itself
                if user_id == bot_user_id:
                    continue

                # Skip already followed
                if has_followed(user_id):
                    continue

                # Filter: require minimum follower count
                followers = user.public_metrics.get("followers_count", 0)
                if followers < 100:
                    continue

                # Follow the user
                try:
                    client.follow_user(target_user_id=user_id)
                    mark_followed(user_id, username=user.username)
                    followed_count += 1
                    logger.info(f"  ✅ Followed @{user.username} ({followers} followers)")
                    time.sleep(5)  # Be polite to the API
                except Exception as e:
                    logger.warning(f"  ⚠️ Could not follow @{user.username}: {e}")

            time.sleep(10)  # Pause between search queries

        except Exception as e:
            logger.error(f"❌ Search failed for query '{query}': {e}")

    logger.info(f"✅ Follow job complete. Followed {followed_count} new accounts today.")
