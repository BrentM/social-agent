"""
listener.py — Polls Twitter for mentions and queues them for replies
"""

import os
from loguru import logger
from bot.auth import get_client
from bot.database import has_seen_mention, mark_mention_seen
from bot.responder import respond_to_mention

BOT_USERNAME = os.getenv("BOT_USERNAME", "")


def poll_mentions():
    """
    Fetches recent mentions and dispatches replies.
    Runs on a schedule (e.g. every 15 minutes).
    """
    logger.info("🔍 Polling for new mentions...")
    client = get_client()

    try:
        # Get bot's own user ID first
        me = client.users.get_me()
        if not me.data:
            logger.error("Could not fetch bot user info.")
            return
        bot_user_id = me.data["id"]

        # Fetch recent mentions (first page only)
        page = next(
            client.users.get_mentions(
                id=bot_user_id,
                max_results=10,
                tweet_fields=["author_id", "text", "created_at"],
            )
        )

        if not page.data:
            logger.info("No new mentions found.")
            return

        for mention in page.data:
            mention_id = str(mention["id"])

            if has_seen_mention(mention_id):
                continue

            logger.info(f"📩 New mention {mention_id}: {mention['text'][:60]}")
            mark_mention_seen(mention_id, replied=False)
            respond_to_mention(mention)

    except Exception as e:
        logger.error(f"❌ Error polling mentions: {e}")
