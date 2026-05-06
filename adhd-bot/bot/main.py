"""
main.py — Entry point for ADHD Bot 🚀
Run with: python -m bot.main
"""

import sys
import os
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Configure logging
os.makedirs("logs", exist_ok=True)
logger.add("logs/bot.log", rotation="1 week", retention="4 weeks", level="INFO")
logger.add(sys.stdout, level="INFO")

from bot.auth import verify_credentials
from bot.database import init_db
from bot.scheduler import build_scheduler


def main():
    logger.info("🚀 ADHD Bot starting up...")

    # Verify Twitter credentials
    if not verify_credentials():
        logger.error("Authentication failed. Please check your .env file and API keys.")
        sys.exit(1)

    # Initialize database
    init_db()

    # Build and start scheduler
    scheduler = build_scheduler()
    logger.info("✅ All jobs scheduled. Bot is running. Press Ctrl+C to stop.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Bot stopped gracefully.")


if __name__ == "__main__":
    main()
