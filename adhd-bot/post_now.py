"""
post_now.py — Immediately posts the next scheduled item.

Determines the upcoming cycle slot based on the current time (America/New_York)
and the POST_TIMES schedule, then calls post_scheduled with that cycle index.

Run with: python post_now.py
"""

import sys
import os
from datetime import datetime
import zoneinfo

from dotenv import load_dotenv

load_dotenv()

from loguru import logger
from bot.database import init_db
from bot.poster import post_scheduled

POST_TIMES = os.getenv("POST_TIMES", "08:00,13:00,19:00").split(",")
TZ = zoneinfo.ZoneInfo("America/New_York")


def next_cycle_index() -> int:
    """Returns the cycle_index for the next upcoming post slot today."""
    now = datetime.now(tz=TZ)
    current_minutes = now.hour * 60 + now.minute

    for index, time_str in enumerate(POST_TIMES):
        hour, minute = map(int, time_str.strip().split(":"))
        if current_minutes < hour * 60 + minute:
            return index

    # All slots have passed — return the first slot for the next day
    return 0


def main():
    init_db()

    index = next_cycle_index()
    time_str = POST_TIMES[index].strip()
    logger.info(f"Posting next scheduled slot: #{index + 1} ({time_str}), cycle_index={index}")

    post_scheduled(cycle_index=index)


if __name__ == "__main__":
    main()
