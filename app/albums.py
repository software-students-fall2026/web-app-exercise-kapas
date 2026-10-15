"""Album detail view - public to view, owner-only controls for editing."""

from datetime import datetime
from typing import Any, Optional

from bson import ObjectId
from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user

from db import get_db

STATUS_LISTENED = "listened"
STATUS_WANT_TO_LISTEN = "want_to_listen"

albums_bp = Blueprint("albums", __name__)


def _current_user_id() -> Optional[str]:
    """Return the logged-in user's id, or None if nobody is logged in with Flask-Login."""
    if getattr(current_app, "login_manager", None) is None:
        return None
    if not current_user.is_authenticated:
        return None
    return str(current_user.get_id())


def get_album_by_id(album_id: str) -> Optional[dict[str, Any]]:
    """Look up an album by the string form of its _id."""
    if not ObjectId.is_valid(album_id):
        return None
    return get_db().albums.find_one({"_id": ObjectId(album_id)})


def format_created_date(created_at: datetime) -> str:
    """Format created_at timestamp for display."""
    now = datetime.now()
    diff = now - created_at

    if diff.days == 0:
        return "Today"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    else:
        return created_at.strftime("%B %d, %Y")


@albums_bp.route("/a/<album_id>", methods=["GET", "POST"])
def view_album(album_id: str):
    """View album details and allow owner to edit rating/review."""
    # Fetch album
    album = get_album_by_id(album_id)
    if album is None:
        abort(404)

    # Handle POST request (update rating/review)
    if request.method == "POST":
        # Check if user is owner
        current_uid = _current_user_id()
        if current_uid != str(album["user_id"]):
            abort(403)

        # Extract form data
        status = request.form.get("status", "").strip()
        rating_str = request.form.get("rating", "").strip()
        review = request.form.get("review", "").strip()

        # Validate status
        if status not in [STATUS_LISTENED, STATUS_WANT_TO_LISTEN]:
            flash("Invalid status", "error")
            return redirect(url_for("albums.view_album", album_id=album_id))

        # Validate and parse rating
        rating = None
        if rating_str:
            try:
                rating = float(rating_str)
                if rating < 1.0 or rating > 5.0:
                    flash("Rating must be between 1 and 5", "error")
                    return redirect(url_for("albums.view_album", album_id=album_id))
            except ValueError:
                flash("Invalid rating", "error")
                return redirect(url_for("albums.view_album", album_id=album_id))

        # Update album
        get_db().albums.update_one(
            {"_id": ObjectId(album_id)},
            {
                "$set": {
                    "status": status,
                    "rating": rating,
                    "review": review if review else None,
                }
            },
        )

        flash("Album updated successfully!", "success")
        return redirect(url_for("albums.view_album", album_id=album_id))

    # Handle GET request (display album)
    # Fetch owner info
    owner = get_db().users.find_one({"_id": album["user_id"]})
    if owner is None:
        abort(404)

    # Determine if current user is owner
    is_owner = _current_user_id() == str(album["user_id"])

    # Format created date
    created_date = format_created_date(album.get("created_at", datetime.now()))

    return render_template(
        "album.html",
        album=album,
        owner=owner,
        is_owner=is_owner,
        created_date=created_date,
    )
