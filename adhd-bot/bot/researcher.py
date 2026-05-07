"""
researcher.py — Daily research agent for ADHD Bot.

Runs once per day (06:00 ET). Discovers high-engagement posts from X,
extracts content signals via Claude, and generates original posts stored
in Supabase as ready-to-post candidates.
"""

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from loguru import logger

import anthropic

from bot.auth import get_client as get_xdk_client
from bot.database import (
    get_research_queries,
    get_research_accounts,
    upsert_research_post,
    cache_account_user_id,
    update_account_checked_at,
    get_todays_research_posts,
    insert_generated_item,
)

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY")
CLAUDE_MODEL = "claude-sonnet-4-6"
MIN_LIKES = 5
POSTS_PER_QUERY = 3
GENERATED_FACTS = 3
GENERATED_TIPS = 3


# ── Phase 1 — Keyword Search ─────────────────────────────────────────────────

def _phase1_keyword_search(xdk):
    keywords = get_research_queries("research_keyword")
    logger.info(f"Phase 1: searching {len(keywords)} keywords")

    for keyword in keywords:
        try:
            page = next(
                xdk.posts.search_recent(
                    query=keyword + " lang:en -is:retweet",
                    max_results=POSTS_PER_QUERY,
                    tweet_fields=["public_metrics", "author_id", "text"],
                    expansions=["author_id"],
                    user_fields=["username"],
                )
            )
        except StopIteration:
            logger.warning(f"  No results for keyword: {keyword}")
            continue
        except Exception as e:
            logger.error(f"  ❌ Keyword search failed for '{keyword}': {e}")
            continue

        tweets = page.data or []
        users = {u["id"]: u["username"] for u in (page.includes or {}).get("users", [])}

        for tweet in tweets:
            metrics = tweet.get("public_metrics", {})
            if metrics.get("like_count", 0) < MIN_LIKES:
                continue
            upsert_research_post(
                tweet_id=str(tweet["id"]),
                author_username=users.get(str(tweet.get("author_id", "")), ""),
                text=tweet["text"],
                like_count=metrics.get("like_count", 0),
                retweet_count=metrics.get("retweet_count", 0),
                reply_count=metrics.get("reply_count", 0),
                source="keyword",
                source_query=keyword,
            )

    logger.info("Phase 1 complete.")


# ── Phase 2 — Key People Timelines ───────────────────────────────────────────

def _phase2_key_people(xdk):
    accounts = get_research_accounts()
    logger.info(f"Phase 2: checking {len(accounts)} key people")

    since = (datetime.now(tz=timezone.utc) - timedelta(hours=24)).strftime("%Y-%m-%dT%H:%M:%SZ")

    for account in accounts:
        username = account["username"]
        user_id = account.get("twitter_user_id")

        try:
            if not user_id:
                resp = xdk.users.get_by_username(username=username)
                if not resp.data:
                    logger.warning(f"  Could not resolve @{username}")
                    continue
                user_id = str(resp.data["id"])
                cache_account_user_id(username, user_id)

            page = next(
                xdk.users.get_posts(
                    id=user_id,
                    max_results=POSTS_PER_QUERY,
                    start_time=since,
                    tweet_fields=["public_metrics", "text"],
                )
            )
        except StopIteration:
            logger.info(f"  No recent posts from @{username}")
            update_account_checked_at(username)
            continue
        except Exception as e:
            logger.error(f"  ❌ Timeline fetch failed for @{username}: {e}")
            continue

        tweets = page.data or []
        for tweet in tweets:
            metrics = tweet.get("public_metrics", {})
            upsert_research_post(
                tweet_id=str(tweet["id"]),
                author_username=username,
                text=tweet["text"],
                like_count=metrics.get("like_count", 0),
                retweet_count=metrics.get("retweet_count", 0),
                reply_count=metrics.get("reply_count", 0),
                source="key_person",
                source_query=username,
            )

        update_account_checked_at(username)
        logger.info(f"  ✅ @{username}: stored {len(tweets)} posts")

    logger.info("Phase 2 complete.")


# ── Phase 3 — Hashtag Top Posts ──────────────────────────────────────────────

def _phase3_hashtags(xdk):
    hashtags = get_research_queries("research_hashtag")
    logger.info(f"Phase 3: searching {len(hashtags)} hashtags")

    for hashtag in hashtags:
        try:
            page = next(
                xdk.posts.search_recent(
                    query=hashtag + " lang:en -is:retweet",
                    sort_order="relevancy",
                    max_results=POSTS_PER_QUERY,
                    tweet_fields=["public_metrics", "author_id", "text"],
                    expansions=["author_id"],
                    user_fields=["username"],
                )
            )
        except StopIteration:
            logger.warning(f"  No results for hashtag: {hashtag}")
            continue
        except Exception as e:
            logger.error(f"  ❌ Hashtag search failed for '{hashtag}': {e}")
            continue

        tweets = page.data or []
        users = {u["id"]: u["username"] for u in (page.includes or {}).get("users", [])}

        ranked = sorted(
            tweets,
            key=lambda t: t.get("public_metrics", {}).get("like_count", 0)
            + t.get("public_metrics", {}).get("retweet_count", 0) * 2,
            reverse=True,
        )

        for tweet in ranked[:3]:
            metrics = tweet.get("public_metrics", {})
            upsert_research_post(
                tweet_id=str(tweet["id"]),
                author_username=users.get(str(tweet.get("author_id", "")), ""),
                text=tweet["text"],
                like_count=metrics.get("like_count", 0),
                retweet_count=metrics.get("retweet_count", 0),
                reply_count=metrics.get("reply_count", 0),
                source="hashtag",
                source_query=hashtag,
            )

    logger.info("Phase 3 complete.")


# ── Phase 4 — Signal Extraction ──────────────────────────────────────────────

def _phase4_extract_signals(claude: anthropic.Anthropic) -> dict:
    posts = get_todays_research_posts()
    logger.info(f"Phase 4: extracting signals from {len(posts)} posts")

    if not posts:
        logger.warning("No research posts found for today. Using default signals.")
        return {
            "hot_topics": ["time blindness", "dopamine", "executive function"],
            "effective_formats": ["quick tip", "did you know"],
            "tone_notes": "warm and empathetic",
            "avoid": [],
        }

    post_list = "\n".join(
        f"- [{p['tweet_id']}] (likes: {p['like_count']}) {p['text']}" for p in posts
    )

    prompt = f"""You are analyzing X posts to identify what content is working in the ADHD community right now.

Review these posts and identify:
1. TOPICS that are generating strong engagement (e.g. "time blindness", "rejection sensitive dysphoria", "dopamine regulation")
2. FORMATS that are resonating (e.g. "did you know + fact", "quick tip with numbered steps", "myth vs reality", "validation first then tip")
3. TONE that is landing well (e.g. "humor + empathy", "direct and punchy", "science-backed but accessible")

Return a JSON object with no markdown fencing:
{{
  "hot_topics": ["topic1", "topic2", ...],
  "effective_formats": ["format1", "format2", ...],
  "tone_notes": "brief observation",
  "avoid": ["anything overused or negative in tone"]
}}

Posts (tweet_id, likes, text):
{post_list}"""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        signals = json.loads(raw)
        logger.info(f"  Signals: {signals}")
        return signals
    except Exception as e:
        logger.error(f"  ❌ Signal extraction failed: {e}")
        return {
            "hot_topics": ["time blindness", "dopamine", "executive function"],
            "effective_formats": ["quick tip", "did you know"],
            "tone_notes": "warm and empathetic",
            "avoid": [],
        }


# ── Phase 5 — Content Generation ─────────────────────────────────────────────

def _phase5_generate_content(claude: anthropic.Anthropic, signals: dict):
    logger.info("Phase 5: generating new content")

    prompt = f"""You are writing content for @ADHDBrainBoost — an upbeat ADHD education bot for adults. Character: Boost. Voice: warm, punchy, science-backed, never lecturing, emoji-friendly (1-3 max).

Today's research shows these topics and formats are resonating:
- Hot topics: {", ".join(signals.get("hot_topics", []))}
- Effective formats: {", ".join(signals.get("effective_formats", []))}
- Tone: {signals.get("tone_notes", "")}
- Avoid: {", ".join(signals.get("avoid", []))}

Write {GENERATED_FACTS} ADHD facts and {GENERATED_TIPS} ADHD tips as original content (never copy or paraphrase the reference posts). Each item must:
- Be under 240 characters (hashtags are added separately)
- Follow Boost's voice — affirm the ADHD brain, no shame
- Cover a variety of the hot topics above

Return a JSON array with no markdown fencing:
[
  {{"category": "fact", "text": "...", "emoji": "🧠", "topic": "..."}},
  {{"category": "tip",  "text": "...", "emoji": "✨", "topic": "..."}},
  ...
]"""

    try:
        response = claude.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = response.content[0].text.strip()
        items = json.loads(raw)
    except Exception as e:
        logger.error(f"  ❌ Content generation failed: {e}")
        return

    stored = 0
    for item in items:
        try:
            content_id = f"gen_{uuid.uuid4().hex[:12]}"
            insert_generated_item(
                content_id=content_id,
                type=item["category"],
                text=item["text"],
                emoji=item.get("emoji", ""),
                topic=item.get("topic", ""),
            )
            stored += 1
        except Exception as e:
            logger.error(f"  ❌ Failed to store generated item: {e}")

    logger.info(f"Phase 5 complete. Stored {stored} generated posts.")


# ── Entry point ───────────────────────────────────────────────────────────────

def run_research_job():
    logger.info("🔬 Starting daily research job")

    xdk = get_xdk_client()
    claude = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    _phase1_keyword_search(xdk)
    _phase2_key_people(xdk)
    _phase3_hashtags(xdk)

    signals = _phase4_extract_signals(claude)
    _phase5_generate_content(claude, signals)

    logger.info("✅ Daily research job complete.")
