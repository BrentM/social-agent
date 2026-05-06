"""
auth.py — Twitter/X API authentication for ADHD Bot
"""

import os
import tweepy
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def get_client() -> tweepy.Client:
    """
    Returns an authenticated Tweepy Client (API v2).
    Used for most modern operations: posting, mentions, user search.
    """
    client = tweepy.Client(
        bearer_token=os.getenv("BEARER_TOKEN"),
        consumer_key=os.getenv("API_KEY"),
        consumer_secret=os.getenv("API_KEY_SECRET"),
        access_token=os.getenv("ACCESS_TOKEN"),
        access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
        wait_on_rate_limit=True,
    )
    logger.debug("Tweepy v2 Client initialized.")
    return client


def get_api_v1() -> tweepy.API:
    """
    Returns an authenticated Tweepy API v1.1 instance.
    Used for operations not yet available in v2 (e.g. follow).
    """
    auth = tweepy.OAuth1UserHandler(
        consumer_key=os.getenv("API_KEY"),
        consumer_secret=os.getenv("API_KEY_SECRET"),
        access_token=os.getenv("ACCESS_TOKEN"),
        access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
    )
    api = tweepy.API(auth, wait_on_rate_limit=True)
    logger.debug("Tweepy v1.1 API initialized.")
    return api


def verify_credentials() -> bool:
    """
    Verifies that the API credentials are valid.
    Returns True if authentication succeeds, False otherwise.
    """
    try:
        client = get_client()
        me = client.get_me()
        if me.data:
            logger.info(f"✅ Authenticated as @{me.data.username}")
            return True
        return False
    except tweepy.errors.Unauthorized:
        logger.error("❌ Authentication failed. Check your API keys in .env")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during auth: {e}")
        return False
