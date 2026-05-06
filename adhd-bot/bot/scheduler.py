"""
scheduler.py — Defines and starts all scheduled jobs for ADHD Bot
"""

import os
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from loguru import logger

from bot.poster import post_scheduled
from bot.listener import poll_mentions
from bot.follower import run_follow_job

# Post times — can be overridden via .env
POST_TIMES = os.getenv("POST_TIMES", "08:00,13:00,19:00").split(",")
REPLY_POLL_MINUTES = int(os.getenv("REPLY_POLL_MINUTES", 15))


def build_scheduler() -> BlockingScheduler:
    scheduler = BlockingScheduler(timezone="America/New_York")

    # ── Posting Jobs ──────────────────────────────────────────────────────────
    for index, time_str in enumerate(POST_TIMES):
        hour, minute = map(int, time_str.strip().split(":"))
        scheduler.add_job(
            func=post_scheduled,
            trigger=CronTrigger(hour=hour, minute=minute),
            kwargs={"cycle_index": index},
            id=f"post_{index}",
            name=f"Post tweet #{index + 1} at {time_str}",
            misfire_grace_time=300,  # 5 min grace if job is missed
        )
        logger.info(f"📅 Scheduled post #{index + 1} at {time_str}")

    # ── Mention Polling ───────────────────────────────────────────────────────
    scheduler.add_job(
        func=poll_mentions,
        trigger="interval",
        minutes=REPLY_POLL_MINUTES,
        id="poll_mentions",
        name=f"Poll mentions every {REPLY_POLL_MINUTES} min",
        misfire_grace_time=60,
    )
    logger.info(f"📅 Scheduled mention polling every {REPLY_POLL_MINUTES} minutes")

    # ── Daily Follow Job ──────────────────────────────────────────────────────
    scheduler.add_job(
        func=run_follow_job,
        trigger=CronTrigger(hour=10, minute=30),
        id="follow_job",
        name="Daily follow job at 10:30",
        misfire_grace_time=600,
    )
    logger.info("📅 Scheduled daily follow job at 10:30 AM")

    return scheduler
