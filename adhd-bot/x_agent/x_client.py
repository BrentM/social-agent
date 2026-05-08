"""
x_client.py — Thin wrapper around xdk for the growth agent system.
"""

import os
import xdk
from xdk.oauth1_auth import OAuth1
from xdk.posts.models import CreateRequest
from xdk.users.models import FollowUserRequest
from loguru import logger


class XClient:
    def __init__(self):
        oauth1 = OAuth1(
            api_key=os.environ["CONSUMER_KEY"],
            api_secret=os.environ["CONSUMER_KEY_SECRET"],
            callback="oob",
            access_token=os.environ["ACCESS_TOKEN"],
            access_token_secret=os.environ["ACCESS_TOKEN_SECRET"],
        )
        self._client = xdk.Client(
            base_url=os.getenv("X_API_BASE_URL", "https://api.x.com"),
            bearer_token=os.environ["BEARER_TOKEN"],
            auth=oauth1,
        )
        self._my_user_id: str | None = None

    def get_my_user_id(self) -> str:
        if self._my_user_id is None:
            me = self._client.users.get_me()
            self._my_user_id = me.data["id"]
            logger.debug(f"Authenticated as user ID {self._my_user_id}")
        return self._my_user_id

    def search_posts(self, query: str, max_results: int = 10) -> dict:
        """
        Search recent posts and return structured data for both Claude and the DB.
        Returns {"posts": [...], "users": [...]}.
        """
        posts = []
        users_by_id: dict[str, dict] = {}

        for page in self._client.posts.search_recent(
            query=query + " lang:en -is:retweet",
            max_results=max(10, min(max_results, 100)),
            tweet_fields=["public_metrics", "author_id"],
            expansions=["author_id"],
            user_fields=["description", "public_metrics", "username"],
        ):
            if not page.data:
                break

            # includes.users is a raw JSON list of user dicts (Expansions = Any)
            includes = page.includes or {}
            raw_users = (
                includes.get("users", []) if isinstance(includes, dict)
                else getattr(includes, "users", None) or []
            )
            for user in raw_users:
                metrics = user.get("public_metrics") or {}
                users_by_id[user["id"]] = {
                    "x_user_id": user["id"],
                    "username": user.get("username", ""),
                    "bio": user.get("description", ""),
                    "followers_count": metrics.get("followers_count", 0),
                }

            for tweet in page.data:
                author_id = tweet.get("author_id", "")
                author = users_by_id.get(author_id, {})
                metrics = tweet.get("public_metrics") or {}
                posts.append({
                    "x_post_id": tweet["id"],
                    "author_x_id": author_id,
                    "text": tweet.get("text", ""),
                    "like_count": metrics.get("like_count", 0),
                    "search_query": query,
                    "author_username": author.get("username", ""),
                    "author_followers": author.get("followers_count", 0),
                    "author_bio": author.get("bio", ""),
                })
            break  # One page is enough per search

        return {"posts": posts, "users": list(users_by_id.values())}

    def post_tweet(self, text: str) -> dict:
        response = self._client.posts.create(body=CreateRequest(text=text))
        return {"x_post_id": response.data.id}

    def follow_user(self, user_id: str) -> None:
        my_id = self.get_my_user_id()
        self._client.users.follow_user(
            id=my_id,
            body=FollowUserRequest(target_user_id=user_id),
        )
