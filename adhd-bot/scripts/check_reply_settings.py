"""
scripts/check_reply_settings.py — Check X reply_settings for a given author's recent posts.

Usage:
    python scripts/check_reply_settings.py <username>
    python scripts/check_reply_settings.py <user_id>

Fetches the author's most recent posts and reports the reply_settings value on each.
Saves the author to discovered_users and all posts to discovered_posts, overwriting any
existing records so reply_settings is always current.
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import xdk
from xdk.oauth1_auth import OAuth1
from x_agent import db


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/check_reply_settings.py <username|user_id>")
        sys.exit(1)

    arg = sys.argv[1].lstrip("@")
    by_id = arg.isdigit()

    oauth1 = OAuth1(
        api_key=os.environ["CONSUMER_KEY"],
        api_secret=os.environ["CONSUMER_KEY_SECRET"],
        callback="oob",
        access_token=os.environ["ACCESS_TOKEN"],
        access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
    )
    client = xdk.Client(
        base_url=os.getenv("X_API_BASE_URL", "https://api.x.com"),
        auth=oauth1,
    )

    print(f"Looking up {'user ID' if by_id else '@'}{arg} ...")
    try:
        if by_id:
            user_resp = client.users.get_by_id(
                id=arg,
                user_fields=["description", "public_metrics"],
            )
        else:
            user_resp = client.users.get_by_username(
                username=arg,
                user_fields=["description", "public_metrics"],
            )
    except Exception as e:
        print(f"Error fetching user {arg}: {e}")
        sys.exit(1)

    user_data = user_resp.data if hasattr(user_resp, "data") else None
    if not user_data:
        print(f"User {arg} not found.")
        sys.exit(1)

    user_id = user_data.get("id")
    if not user_id:
        print(f"Unexpected response: no user ID in response for {arg}.")
        sys.exit(1)

    username = user_data.get("username", arg)
    u_metrics = user_data.get("public_metrics") or {}
    user_record = {
        "x_user_id": user_id,
        "username": username,
        "bio": user_data.get("description", ""),
        "followers_count": u_metrics.get("followers_count", 0),
    }
    print(f"@{username} (ID: {user_id})\n")

    print("Fetching recent posts ...")
    try:
        posts_paginator = client.users.get_posts(
            id=user_id,
            max_results=10,
            tweet_fields=["reply_settings", "public_metrics", "created_at"],
            exclude=["retweets", "replies"],
        )
    except Exception as e:
        print(f"Error fetching posts for {arg}: {e}")
        sys.exit(1)

    raw_posts = []
    try:
        for page in posts_paginator:
            if not page.data:
                break
            raw_posts = page.data
            break
    except Exception as e:
        print(f"Error reading posts response for {arg}: {e}")
        sys.exit(1)

    if not raw_posts:
        print("No recent posts found.")
        sys.exit(0)

    post_records = []
    for post in raw_posts:
        post_id = post.get("id")
        if not post_id:
            continue
        pm = post.get("public_metrics") or {}
        post_records.append({
            "x_post_id": post_id,
            "author_x_id": user_id,
            "text": post.get("text", ""),
            "like_count": pm.get("like_count", 0),
            "search_query": f"user:{username}",
            "reply_settings": post.get("reply_settings", "unknown"),
        })

    try:
        db.upsert_posts_and_users(post_records, [user_record])
    except Exception as e:
        print(f"Error saving to database: {e}")
        sys.exit(1)
    print(f"Saved @{username} to discovered_users and {len(post_records)} posts to discovered_posts.\n")

    print(f"{'Post ID':<22} {'reply_settings':<18} {'Likes':>6}  Text preview")
    print("-" * 90)
    for pr in post_records:
        preview = pr["text"][:50].replace("\n", " ")
        print(f"{pr['x_post_id']:<22} {pr['reply_settings']:<18} {pr['like_count']:>6}  {preview}")


if __name__ == "__main__":
    main()
