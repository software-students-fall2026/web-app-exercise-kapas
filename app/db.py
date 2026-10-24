from pymongo import MongoClient
from dotenv import load_dotenv
import os


load_dotenv()


client = MongoClient(os.getenv("MONGO_URI"))
db = client[os.getenv("MONGO_DBNAME")]


def get_db():
    """
    Get MongoDB database connection
    """
    return db


def ensure_indexes():
    """
    ensures usernames/emails are unique
    """
    db = get_db()
    db.users.create_index("username", unique=True)
    db.users.create_index("email", unique=True)