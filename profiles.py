"""Profile is public to view, has owner-only controls (eg editing)."""

from typing import Any, Optional

from bson import ObjectId
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    redirect,
    render_template,
    url_for,
)
from flask_login import current_user

from db import db

STATUS_LISTENED = "listened"
STATUS_WANT_TO_LISTEN = "want_to_listen"

profiles_bp = Blueprint("profiles", __name__)


def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """Look up a user by username, case-insensitively."""
    return db.users.find_one({"username": username.strip().lower()})


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    """Look up a user by the string form of their _id."""
    if not ObjectId.is_valid(user_id):
        return None
    return db.users.find_one({"_id": ObjectId(user_id)})


def get_profile_data(user: dict[str, Any]) -> dict[str, Any]:
    """Build the profile dict the template needs for user.
    """
    albums = list(
        db.albums.find({"user_id": user["_id"]}).sort("created_at", -1)
    )
    listened = [a for a in albums if a.get("status") == STATUS_LISTENED]
    want_to_listen = [
        a for a in albums if a.get("status") == STATUS_WANT_TO_LISTEN
    ]
    listened.sort(key=lambda a: -a["rating"] if a.get("rating") else 1)

    ratings = [a["rating"] for a in listened if a.get("rating")]
    average = round(sum(ratings) / len(ratings), 1) if ratings else None

    return {
        "username": user["username"],
        "listened": listened,
        "want_to_listen": want_to_listen,
        "album_count": len(listened) + len(want_to_listen),
        "average_rating": average,
    }


def _current_user_id() -> Optional[str]:
    """Return the logged-in user's id, or None if nobody is logged in with Flask-Login.
    """
    if getattr(current_app, "login_manager", None) is None:
        return None
    if not current_user.is_authenticated:
        return None
    return str(current_user.get_id())


@profiles_bp.get("/profile")
def my_profile() -> Response:
    """Send the logged-in user to their own profile."""
    user_id = _current_user_id()
    if user_id is None:
        manager = getattr(current_app, "login_manager", None)
        if manager is not None:
            return manager.unauthorized()
        abort(401)
    user = get_user_by_id(user_id)
    if user is None:
        abort(404)
    return redirect(url_for("profiles.view_profile", username=user["username"]))


@profiles_bp.get("/u/<username>")
def view_profile(username: str) -> str:
    """Show a user's profile."""
    user = get_user_by_username(username)
    if user is None:
        abort(404)
    return render_template(
        "profile.html",
        profile=get_profile_data(user),
        is_owner=_current_user_id() == str(user["_id"]),
    )
