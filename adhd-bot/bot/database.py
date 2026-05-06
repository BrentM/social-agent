"""
database.py — Supabase database helpers for ADHD Bot
"""

import os
from datetime import date, datetime, timedelta, timezone
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
