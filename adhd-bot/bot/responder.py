"""
responder.py — Classifies mentions and sends appropriate replies as Boost 🚀
"""

import json
import random
import os
from loguru import logger
from xdk.posts.models import CreateRequest, CreateRequestReply
from bot.auth import get_client
from bot.database import mark_mention_seen

CONTENT_DIR = os.path.join(os.path.dirname(__file__), "..", "content")

# Keywords to classify incoming mentions
QUESTION_KEYWORDS = [
    "how", "what", "why", "help", "tip", "advice", "suggest",
    "struggle", "hard", "difficult", "problem", "issue", "can't", "cant",
]
POSITIVE_KEYWORDS = [
    "thank", "thanks", "love", "great", "amazing", "helpful",
    "good", "awesome", "appreciate", "❤️", "🙏", "💙",
]


def load_replies() -> dict:
    path = os.path.join(CONTENT_DIR, "replies.json")
    with open(path, "r") as f:
        return json.load(f)


def classify_mention(text: str) -> str:
    """Returns 'question', 'positive', or 'general'."""
    lower = text.lower()
    if any(kw in lower for kw in QUESTION_KEYWORDS):
        return "question"
    if any(kw in lower for kw in POSITIVE_KEYWORDS):
        return "positive"
    return "general"


def respond_to_mention(mention: dict) -> bool:
    """
    Selects an appropriate reply and sends it to the mention author.
    Returns True if reply was sent successfully.
    mention is a dict with at least 'id' and 'text' keys.
    """
    mention_id = str(mention["id"])
    text = mention["text"]
    mention_type = classify_mention(text)

    replies = load_replies()
    reply_options = replies.get(mention_type, replies["general"])
    reply_text = random.choice(reply_options)

    try:
        client = get_client()
        response = client.posts.create(
            body=CreateRequest(
                text=reply_text,
                reply=CreateRequestReply(in_reply_to_tweet_id=mention_id),
            )
        )
        tweet_id = response.data.id
        mark_mention_seen(mention_id, replied=True)
        logger.info(f"✅ Replied [{mention_type}] to mention {mention_id}: {reply_text[:60]}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to reply to mention {mention_id}: {e}")
        return False
