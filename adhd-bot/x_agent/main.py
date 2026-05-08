"""
main.py — Scheduler entry point for the x_agent growth system.
Run with: python -m x_agent.main
"""

import sys
import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

os.makedirs("logs", exist_ok=True)
logger.add("logs/x_agent.log", rotation="1 week", retention="4 weeks", level="INFO")
logger.add(sys.stdout, level="INFO")

from apscheduler.schedulers.blocking import BlockingScheduler
from x_agent.x_client import XClient
from x_agent import db
from x_agent.orchestrator import run_orchestrator
from x_agent.config import SCHEDULER_INTERVAL_HOURS


def job():
    try:
        x_client = XClient()
        # Warm up the user ID cache before the agent loop starts
        x_client.get_my_user_id()
        run_orchestrator(x_client, db)
    except Exception:
        logger.exception("Orchestrator job failed.")


def main():
    logger.info("x_agent starting up...")
    scheduler = BlockingScheduler()
    scheduler.add_job(
        job,
        "interval",
        hours=SCHEDULER_INTERVAL_HOURS,
        id="orchestrator",
        misfire_grace_time=300,  # allow up to 5 min late; avoids skip if startup run runs long
        coalesce=True,           # if multiple fires were missed, run only once
    )

    # Run immediately on startup, then on the interval
    job()

    logger.info(f"Scheduled to run every {SCHEDULER_INTERVAL_HOURS}h. Press Ctrl+C to stop.")
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("x_agent stopped.")


if __name__ == "__main__":
    main()
