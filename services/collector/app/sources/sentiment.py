import os

REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID", "")
REDDIT_SECRET = os.getenv("REDDIT_SECRET", "")
REDDIT_USER_AGENT = "aurum-collector/1.0"

SUBREDDITS = ["Gold", "wallstreetbets", "Economics", "Forex"]
KEYWORDS = ["gold", "xau", "xauusd", "precious metal", "bullion"]


def fetch_reddit_sentiment() -> list[dict]:
    if not (REDDIT_CLIENT_ID and REDDIT_SECRET):
        return [{"source": "reddit", "error": "REDDIT_CLIENT_ID/SECRET not configured"}]

    try:
        import praw
        reddit = praw.Reddit(
            client_id=REDDIT_CLIENT_ID,
            client_secret=REDDIT_SECRET,
            user_agent=REDDIT_USER_AGENT,
        )
        posts = []
        for sub_name in SUBREDDITS:
            try:
                sub = reddit.subreddit(sub_name)
                for post in sub.hot(limit=25):
                    title = post.title.lower()
                    if any(kw in title for kw in KEYWORDS):
                        posts.append({
                            "subreddit": sub_name,
                            "title": post.title,
                            "score": post.score,
                            "upvote_ratio": post.upvote_ratio,
                            "num_comments": post.num_comments,
                        })
            except Exception:
                pass
        return posts
    except Exception as e:
        return [{"source": "reddit", "error": str(e)}]
