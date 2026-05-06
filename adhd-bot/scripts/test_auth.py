"""
scripts/test_auth.py — Verify your Twitter API credentials before running the bot.
Run with: python scripts/test_auth.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

from bot.auth import verify_credentials, get_client
from loguru import logger


def main():
    logger.info("Testing Twitter API authentication...")

    if not verify_credentials():
        logger.error("❌ Auth test FAILED. Check your .env keys.")
        sys.exit(1)

    client = get_client()

    # Try fetching your own user info
    me = client.get_me(user_fields=["public_metrics", "description"])
    if me.data:
        print(f"\n✅ Auth successful!")
        print(f"   Username: @{me.data.username}")
        print(f"   Name:     {me.data.name}")
        if hasattr(me.data, "public_metrics") and me.data.public_metrics:
            print(f"   Followers: {me.data.public_metrics.get('followers_count', 'N/A')}")
        print()
    else:
        logger.error("❌ Could not fetch user data.")
        sys.exit(1)


if __name__ == "__main__":
    main()
