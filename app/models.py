from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId
from db import get_db

class User(UserMixin):
    """
    User model for authentication
    """
    def __init__(self, username, email, password_hash=None, _id=None):
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self._id = _id

    def get_id(self):
        """Required by flask-login"""
        return str(self._id)

    def set_password(self, password):
        """Hash and set password"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Check if password matches hash"""
        return check_password_hash(self.password_hash, password)

    def save(self):
        """Save user to database"""
        db = get_db()
        user_data = {
            "username": self.username,
            "email": self.email,
            "password_hash": self.password_hash
        }
        if self._id:
            db.users.update_one({"_id": ObjectId(self._id)}, {"$set": user_data})
        else:
            result = db.users.insert_one(user_data)
            self._id = result.inserted_id
        return self

    @staticmethod
    def find_by_username(username):
        """Find user by username"""
        db = get_db()
        user_data = db.users.find_one({"username": username})
        if user_data:
            return User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=user_data["password_hash"],
                _id=user_data["_id"]
            )
        return None

    @staticmethod
    def find_by_email(email):
        """Find user by email"""
        db = get_db()
        user_data = db.users.find_one({"email": email})
        if user_data:
            return User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=user_data["password_hash"],
                _id=user_data["_id"]
            )
        return None

    @staticmethod
    def find_by_id(user_id):
        """Find user by ID"""
        db = get_db()
        user_data = db.users.find_one({"_id": ObjectId(user_id)})
        if user_data:
            return User(
                username=user_data["username"],
                email=user_data["email"],
                password_hash=user_data["password_hash"],
                _id=user_data["_id"]
            )
        return None
