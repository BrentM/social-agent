"""
scripts/test_x_auth.py — Verify xdk OAuth1 credentials before running x_agent.
Run with: python scripts/test_x_auth.py
"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from dotenv import load_dotenv
load_dotenv()

import requests
from xdk.oauth1_auth import OAuth1


def main():
    url = "https://api.x.com/2/users/me"

    auth = OAuth1(
        api_key=os.environ["CONSUMER_KEY"],
        api_secret=os.environ["CONSUMER_KEY_SECRET"],
        callback="oob",
        access_token=os.environ["ACCESS_TOKEN"],
        access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
    )
    header = auth.build_request_header("GET", url, "")

    print(f"Sending OAuth1 request to {url} ...")
    r = requests.get(url, headers={"Authorization": header})

    if r.status_code == 200:
        data = r.json().get("data", {})
        print(f"\n✅ Auth successful!")
        print(f"   User ID:  {data.get('id')}")
        print(f"   Username: @{data.get('username')}")
        print(f"   Name:     {data.get('name')}")
    elif r.status_code == 401:
        print(f"\n❌ 401 Unauthorized — CONSUMER_KEY/ACCESS_TOKEN are mismatched or revoked.")
        print("   Regenerate Access Token & Secret in the X Developer Portal.")
        print(f"   Response: {r.text}")
        sys.exit(1)
    elif r.status_code == 403:
        print(f"\n❌ 403 Forbidden — OAuth 1.0a may not be enabled for this app.")
        print("   Check User authentication settings in the X Developer Portal.")
        print(f"   Response: {r.text}")
        sys.exit(1)
    else:
        print(f"\n❌ Unexpected {r.status_code}: {r.text}")
        sys.exit(1)


if __name__ == "__main__":
    main()
