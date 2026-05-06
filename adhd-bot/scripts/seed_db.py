"""
scripts/seed_db.py — Verify Supabase connectivity.
Ensure scripts/migration.sql has been run in the Supabase SQL editor first.
Run with: python scripts/seed_db.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from bot.database import init_db
from loguru import logger


def main():
    logger.info("Verifying Supabase connection and tables...")
    init_db()
    logger.info("✅ Supabase ready.")


if __name__ == "__main__":
    main()
