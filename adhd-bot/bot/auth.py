"""
auth.py — Twitter/X API authentication for ADHD Bot
"""

import os
import requests
import xdk
from xdk.oauth1_auth import OAuth1
from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def get_client() -> xdk.Client:
    """
    Returns an authenticated xdk Client (API v2).
    Uses OAuth1 for write operations and bearer token for read operations.
    """
    base_url = os.getenv("X_API_BASE_URL", "https://api.x.com")

    oauth1 = OAuth1(
        api_key=os.getenv("API_KEY"),
        api_secret=os.getenv("API_KEY_SECRET"),
        callback="oob",
        access_token=os.getenv("ACCESS_TOKEN"),
        access_token_secret=os.getenv("ACCESS_TOKEN_SECRET"),
    )

    client = xdk.Client(
        base_url=base_url,
        bearer_token=os.getenv("BEARER_TOKEN"),
        auth=oauth1,
    )
    logger.debug("xdk Client initialized.")
    return client


def verify_credentials() -> bool:
    """
    Verifies that the API credentials are valid.
    Returns True if authentication succeeds, False otherwise.
    """
    try:
        client = get_client()
        me = client.users.get_me()
        if me.data:
            logger.info(f"✅ Authenticated as @{me.data['username']}")
            return True
        return False
    except requests.exceptions.HTTPError as e:
        if e.response is not None and e.response.status_code == 401:
            logger.error("❌ Authentication failed. Check your API keys in .env")
        else:
            logger.error(f"❌ HTTP error during auth: {e}")
        return False
    except Exception as e:
        logger.error(f"❌ Unexpected error during auth: {e}")
        return False
