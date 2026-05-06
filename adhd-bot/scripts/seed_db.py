"""
scripts/seed_db.py — Initialize the bot database.
Run once before starting the bot: python scripts/seed_db.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from bot.database import init_db
from loguru import logger


def main():
    logger.info("Initializing bot database...")
    init_db()
    logger.info("✅ Database ready at data/bot.db")


if __name__ == "__main__":
    main()
