"""
db.py — Supabase helpers for the x_agent growth system tables.
"""

import os
from datetime import datetime, timedelta, timezone
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


# ── Search query log ──────────────────────────────────────────────────────────

def log_search_query(query: str, result_count: int, strategy: str | None = None) -> None:
    get_client().table("search_queries").insert({
        "query": query,
        "result_count": result_count,
        "strategy": strategy,
    }).execute()


# ── Engagement replies ────────────────────────────────────────────────────────

def get_recent_unevaluated_posts() -> list[dict]:
    """Return discovered posts from the last 24 h with ≥10 likes that haven't been evaluated."""
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
    response = (
        get_client()
        .table("discovered_posts")
        .select("x_post_id, text, like_count, search_query, author_x_id")
        .eq("reply_attempted", False)
        .gte("discovered_at", cutoff)
        .gte("like_count", 10)
        .order("like_count", desc=True)
        .execute()
    )
    return response.data or []


def get_discovered_post_by_x_id(x_post_id: str) -> dict | None:
    """Return full post details joined with author info from discovered_users."""
    response = (
        get_client()
        .table("discovered_posts")
        .select(
            "x_post_id, text, like_count, search_query, discovered_at,"
            " discovered_users(username, bio, followers_count)"
        )
        .eq("x_post_id", x_post_id)
        .maybe_single()
        .execute()
    )
    return response.data if response is not None else None


def get_reply_count_today() -> int:
    """Count replies posted in the last 24 hours (rolling window)."""
    cutoff = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).isoformat()
    response = (
        get_client()
        .table("agent_replies")
        .select("id", count="exact")
        .eq("skipped", False)
        .gte("posted_at", cutoff)
        .execute()
    )
    return response.count or 0


def log_reply(x_post_id: str, in_reply_to: str, text: str, reason: str) -> None:
    get_client().table("agent_replies").insert({
        "x_post_id": x_post_id,
        "in_reply_to": in_reply_to,
        "text": text,
        "reason": reason,
        "skipped": False,
    }).execute()


def log_skipped_engagement(reason: str) -> None:
    get_client().table("agent_replies").insert({
        "reason": reason,
        "skipped": True,
    }).execute()


def mark_reply_attempted(x_post_id: str) -> None:
    get_client().table("discovered_posts").update(
        {"reply_attempted": True}
    ).eq("x_post_id", x_post_id).execute()


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
