from functools import lru_cache
from pymongo import MongoClient
from dotenv import load_dotenv
import os


load_dotenv()

@lru_cache(maxsize=1)
def _get_client():
    """
    Create the MongoDB client once and reuse it. MongoClient is thread-safe
    and manages its own connection pool.
    """
    uri = os.getenv("MONGO_URI")
    if not uri:
        raise RuntimeError("MONGO_URI is not set. Add it to your .env file (see env.example).")
    return MongoClient(uri)

def get_db():
    """
    Get MongoDB database connection
    """
    dbname = os.getenv("MONGO_DBNAME")
    if not dbname:
        raise RuntimeError("MONGO_DBNAME is not set. Add it to your .env file (see env.example).")
    return _get_client()[dbname]


def ensure_indexes():
    """
    ensures usernames/emails are unique and each user reviews an album at most once
    """
    db = get_db()
    db.users.create_index("username", unique=True)
    db.users.create_index("email", unique=True)
    db.reviews.create_index([("album_id", 1), ("user_id", 1)], unique=True)
    db.reviews.create_index("user_id")