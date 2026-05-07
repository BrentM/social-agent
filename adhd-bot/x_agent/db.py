"""
db.py — Supabase helpers for the x_agent growth system tables.
"""

import os
from datetime import datetime, timezone
from loguru import logger
from supabase import create_client, Client

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
    return _client


# ── Account stats ─────────────────────────────────────────────────────────────

def get_account_stats() -> dict:
    """Return stats used by the orchestrator to choose a strategy."""
    response = get_client().table("agent_tweets").select("id", count="exact").execute()
    return {"post_count": response.count or 0}


# ── Agent tweets ──────────────────────────────────────────────────────────────

def log_tweet(x_post_id: str, text: str) -> None:
    get_client().table("agent_tweets").insert({
        "x_post_id": x_post_id,
        "text": text,
    }).execute()


# ── Agent runs ────────────────────────────────────────────────────────────────

def log_agent_run(strategy: str, reason: str, post_count: int) -> None:
    get_client().table("agent_runs").insert({
        "strategy_selected": strategy,
        "reason": reason,
        "post_count_at_time": post_count,
    }).execute()


# ── Discovered users ──────────────────────────────────────────────────────────

def is_already_followed(x_user_id: str) -> bool:
    response = (
        get_client()
        .table("discovered_users")
        .select("followed_by_agent")
        .eq("x_user_id", x_user_id)
        .eq("followed_by_agent", True)
        .execute()
    )
    return len(response.data) > 0


def mark_followed(x_user_id: str) -> None:
    get_client().table("discovered_users").upsert(
        {
            "x_user_id": x_user_id,
            "followed_by_agent": True,
            "followed_at": datetime.now(tz=timezone.utc).isoformat(),
        },
        on_conflict="x_user_id",
    ).execute()


# ── Discovered posts + users ──────────────────────────────────────────────────

def save_posts_and_users(posts: list[dict], users: list[dict]) -> None:
    """Upsert discovered users first (FK target), then discovered posts."""
    client = get_client()

    for user in users:
        client.table("discovered_users").upsert(
            {
                "x_user_id": user["x_user_id"],
                "username": user.get("username"),
                "bio": user.get("bio"),
                "followers_count": user.get("followers_count", 0),
            },
            on_conflict="x_user_id",
            ignore_duplicates=True,
        ).execute()

    for post in posts:
        client.table("discovered_posts").upsert(
            {
                "x_post_id": post["x_post_id"],
                "author_x_id": post.get("author_x_id"),
                "text": post.get("text"),
                "like_count": post.get("like_count", 0),
                "search_query": post.get("search_query"),
            },
            on_conflict="x_post_id",
            ignore_duplicates=True,
        ).execute()
