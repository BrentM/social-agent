"""
database.py — Supabase database helpers for ADHD Bot
"""

import os
import random
from datetime import datetime, timedelta, timezone
from loguru import logger
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        url = os.environ["SUPABASE_URL"]
        key = os.environ["SUPABASE_SERVICE_ROLE_KEY"]
        _client = create_client(url, key)
    return _client


def init_db():
    """Verifies Supabase connectivity. Tables must exist via migration.sql."""
    try:
        client = get_client()
        client.table("posted_content").select("id").limit(1).execute()
        client.table("mentions_seen").select("id").limit(1).execute()
        client.table("followed_accounts").select("id").limit(1).execute()
        logger.info("✅ Supabase connected and tables verified.")
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        raise


# ── Posted Content ──────────────────────────────────────────────────────────

def mark_posted(content_id: str, category: str, tweet_id: str = None):
    get_client().table("posted_content").insert({
        "content_id": content_id,
        "category": category,
        "tweet_id": tweet_id,
    }).execute()


def get_posted_ids(category: str) -> set:
    response = get_client().table("posted_content").select("content_id").eq("category", category).execute()
    return {row["content_id"] for row in response.data}


# ── Mentions ────────────────────────────────────────────────────────────────

def has_seen_mention(mention_id: str) -> bool:
    response = get_client().table("mentions_seen").select("id").eq("mention_id", mention_id).execute()
    return len(response.data) > 0


def mark_mention_seen(mention_id: str, replied: bool = False):
    get_client().table("mentions_seen").upsert(
        {"mention_id": mention_id, "replied": replied},
        on_conflict="mention_id",
    ).execute()


# ── Follows ─────────────────────────────────────────────────────────────────

def has_followed(twitter_user_id: str) -> bool:
    response = get_client().table("followed_accounts").select("id").eq("twitter_user_id", twitter_user_id).execute()
    return len(response.data) > 0


def mark_followed(twitter_user_id: str, username: str = None):
    get_client().table("followed_accounts").upsert(
        {"twitter_user_id": twitter_user_id, "username": username},
        on_conflict="twitter_user_id",
    ).execute()


def get_daily_follow_count() -> int:
    today = datetime.now(tz=timezone.utc).date()
    day_start = datetime.combine(today, datetime.min.time(), tzinfo=timezone.utc).isoformat()
    day_end = datetime.combine(today + timedelta(days=1), datetime.min.time(), tzinfo=timezone.utc).isoformat()
    response = (
        get_client()
        .table("followed_accounts")
        .select("id", count="exact")
        .gte("followed_at", day_start)
        .lt("followed_at", day_end)
        .execute()
    )
    return response.count or 0


# ── Content Items ────────────────────────────────────────────────────────────

def get_content_items(type: str) -> list[dict]:
    response = (
        get_client()
        .table("content_items")
        .select("*")
        .eq("type", type)
        .eq("active", True)
        .execute()
    )
    return response.data


def insert_generated_item(content_id: str, type: str, text: str, emoji: str, topic: str):
    get_client().table("content_items").insert({
        "content_id": content_id,
        "type": type,
        "text": text,
        "emoji": emoji,
        "topic": topic,
        "source": "generated",
    }).execute()


# ── Research Posts ───────────────────────────────────────────────────────────

def upsert_research_post(
    tweet_id: str,
    author_username: str,
    text: str,
    like_count: int,
    retweet_count: int,
    reply_count: int,
    source: str,
    source_query: str,
):
    get_client().table("research_posts").upsert(
        {
            "tweet_id": tweet_id,
            "author_username": author_username,
            "text": text,
            "like_count": like_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
            "source": source,
            "source_query": source_query,
        },
        on_conflict="tweet_id",
    ).execute()


def get_todays_research_posts() -> list[dict]:
    today = datetime.now(tz=timezone.utc).date().isoformat()
    response = (
        get_client()
        .table("research_posts")
        .select("tweet_id, text, like_count")
        .gte("discovered_at", today)
        .execute()
    )
    return response.data


# ── Configured Accounts ──────────────────────────────────────────────────────

def get_research_accounts() -> list[dict]:
    response = (
        get_client()
        .table("configured_accounts")
        .select("*")
        .eq("is_research", True)
        .execute()
    )
    return response.data


def cache_account_user_id(username: str, twitter_user_id: str):
    get_client().table("configured_accounts").upsert(
        {
            "username": username,
            "twitter_user_id": twitter_user_id,
            "last_checked_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        on_conflict="username",
    ).execute()


def update_account_checked_at(username: str):
    get_client().table("configured_accounts").upsert(
        {
            "username": username,
            "last_checked_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        on_conflict="username",
    ).execute()


# ── Configured Queries ───────────────────────────────────────────────────────

def get_follow_queries() -> list[str]:
    response = (
        get_client()
        .table("configured_queries")
        .select("query")
        .eq("purpose", "follow")
        .eq("active", True)
        .execute()
    )
    return [row["query"] for row in response.data]


def get_research_queries(purpose: str) -> list[str]:
    response = (
        get_client()
        .table("configured_queries")
        .select("query")
        .eq("purpose", purpose)
        .eq("active", True)
        .execute()
    )
    return [row["query"] for row in response.data]


# ── Reply Templates ──────────────────────────────────────────────────────────

def get_reply_template(intent: str) -> str | None:
    response = (
        get_client()
        .table("reply_templates")
        .select("text")
        .eq("intent", intent)
        .eq("active", True)
        .execute()
    )
    if not response.data:
        return None
    return random.choice(response.data)["text"]
