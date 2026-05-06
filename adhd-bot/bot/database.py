"""
database.py — SQLite database setup and helpers for ADHD Bot
"""

import sqlite3
import os
from loguru import logger

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "bot.db")


def get_connection() -> sqlite3.Connection:
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    return sqlite3.connect(DB_PATH)


def init_db():
    """Creates all tables if they don't exist."""
    with get_connection() as conn:
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS posted_content (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                content_id  TEXT NOT NULL,
                category    TEXT NOT NULL,
                tweet_id    TEXT,
                posted_at   DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mentions_seen (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                mention_id  TEXT NOT NULL UNIQUE,
                replied     BOOLEAN DEFAULT 0,
                seen_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS followed_accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                twitter_user_id TEXT NOT NULL UNIQUE,
                username        TEXT,
                followed_at     DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)

        conn.commit()
        logger.info("✅ Database initialized.")


# ── Posted Content ──────────────────────────────────────────────────────────

def mark_posted(content_id: str, category: str, tweet_id: str = None):
    with get_connection() as conn:
        conn.execute(
            "INSERT INTO posted_content (content_id, category, tweet_id) VALUES (?, ?, ?)",
            (content_id, category, tweet_id),
        )
        conn.commit()


def get_posted_ids(category: str) -> set:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT content_id FROM posted_content WHERE category = ?", (category,)
        ).fetchall()
    return {row[0] for row in rows}


# ── Mentions ────────────────────────────────────────────────────────────────

def has_seen_mention(mention_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM mentions_seen WHERE mention_id = ?", (mention_id,)
        ).fetchone()
    return row is not None


def mark_mention_seen(mention_id: str, replied: bool = False):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO mentions_seen (mention_id, replied) VALUES (?, ?)",
            (mention_id, int(replied)),
        )
        conn.commit()


# ── Follows ─────────────────────────────────────────────────────────────────

def has_followed(twitter_user_id: str) -> bool:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT id FROM followed_accounts WHERE twitter_user_id = ?",
            (twitter_user_id,),
        ).fetchone()
    return row is not None


def mark_followed(twitter_user_id: str, username: str = None):
    with get_connection() as conn:
        conn.execute(
            "INSERT OR IGNORE INTO followed_accounts (twitter_user_id, username) VALUES (?, ?)",
            (twitter_user_id, username),
        )
        conn.commit()


def get_daily_follow_count() -> int:
    with get_connection() as conn:
        row = conn.execute(
            "SELECT COUNT(*) FROM followed_accounts WHERE DATE(followed_at) = DATE('now')"
        ).fetchone()
    return row[0] if row else 0
