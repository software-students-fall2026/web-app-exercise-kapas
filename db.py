from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv()

def get_db():
    """
    Get MongoDB database connection
    """
    client = MongoClient(os.getenv("MONGO_URI"))
    db = client[os.getenv("MONGO_DBNAME")]
    return db
