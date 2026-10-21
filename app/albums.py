"""Album detail view - public to view, owner-only controls for editing."""

import math
import re
from datetime import datetime, timezone
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
from flask_login import current_user, login_required

from db import get_db

STATUS_LISTENED = "listened"
STATUS_WANT_TO_LISTEN = "want_to_listen"

albums_bp = Blueprint("albums", __name__)


@albums_bp.get("/search")
def search_albums():
    """Search albums by title or artist, optionally filtering by status."""
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    if status not in [STATUS_LISTENED, STATUS_WANT_TO_LISTEN]:
        status = ""

    album_filter: dict[str, Any] = {}
    if query:
        escaped_query = re.escape(query)
        album_filter["$or"] = [
            {"title": {"$regex": escaped_query, "$options": "i"}},
            {"artist": {"$regex": escaped_query, "$options": "i"}},
        ]
    if status:
        album_filter["status"] = status

    db = get_db()
    albums = list(db.albums.find(album_filter).sort("created_at", -1).limit(50))
    user_ids = {album["user_id"] for album in albums if "user_id" in album}
    owners = {
        owner["_id"]: owner["username"]
        for owner in db.users.find(
            {"_id": {"$in": list(user_ids)}}, {"username": 1}
        )
    }
    results = [
        {**album, "owner_username": owners[album["user_id"]]}
        for album in albums
        if album.get("user_id") in owners
    ]

    return render_template(
        "search.html",
        query=query,
        status=status,
        results=results,
    )


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


def parse_rating(rating_str: str) -> Optional[float]:
    """Parse a rating from form input.

    Returns None for blank input. Raises ValueError if the value is not a
    finite number from 1 to 5 in steps of 0.5.
    """
    if not rating_str:
        return None
    rating = float(rating_str)
    if not math.isfinite(rating) or not 1.0 <= rating <= 5.0:
        raise ValueError("rating out of range")
    if rating * 2 != int(rating * 2):
        raise ValueError("rating not a multiple of 0.5")
    return rating


def format_created_date(created_at: datetime) -> str:
    """Format created_at timestamp for display.

    pymongo returns naive datetimes that hold UTC, so treat a missing tzinfo as UTC.
    """
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=timezone.utc)
    diff = datetime.now(timezone.utc) - created_at

    if diff.days <= 0:
        return "Today"
    elif diff.days == 1:
        return "Yesterday"
    elif diff.days < 7:
        return f"{diff.days} days ago"
    else:
        return created_at.strftime("%B %d, %Y")


@albums_bp.route("/a/add", methods=["GET", "POST"])
@login_required
def add_album():
    """Display the add-album form and save albums for the logged-in user."""
    if request.method == "GET":
        return render_template("add_album.html")

    title = request.form.get("title", "").strip()
    artist = request.form.get("artist", "").strip()
    year_str = request.form.get("year", "").strip()
    status = request.form.get("status", "").strip()
    rating_str = request.form.get("rating", "").strip()
    review = request.form.get("review", "").strip()

    if not title or not artist:
        flash("Title and artist are required", "error")
        return render_template("add_album.html")

    year = None
    if year_str:
        try:
            year = int(year_str)
        except ValueError:
            flash("Year must be a number from 1900 to 9999", "error")
            return render_template("add_album.html")
        if not 1900 <= year <= 9999:
            flash("Year must be a number from 1900 to 9999", "error")
            return render_template("add_album.html")

    if status not in [STATUS_LISTENED, STATUS_WANT_TO_LISTEN]:
        flash("Invalid status", "error")
        return render_template("add_album.html")

    try:
        rating = parse_rating(rating_str)
    except ValueError:
        flash("Rating must be a number from 1 to 5 in steps of 0.5", "error")
        return render_template("add_album.html")

    if status == STATUS_WANT_TO_LISTEN:
        rating = None

    result = get_db().albums.insert_one(
        {
            "title": title,
            "artist": artist,
            "year": year,
            "status": status,
            "rating": rating,
            "review": review or None,
            "user_id": current_user._id,
            "created_at": datetime.now(timezone.utc),
        }
    )
    return redirect(url_for("albums.view_album", album_id=str(result.inserted_id)))


@albums_bp.route("/a/<album_id>/edit", methods=["GET", "POST"])
@login_required
def edit_album(album_id: str):
    """Edit album details (title, artist, year) - owner only."""
    # Fetch album
    album = get_album_by_id(album_id)
    if album is None:
        abort(404)

    # Check if user is owner
    current_uid = _current_user_id()
    if current_uid != str(album["user_id"]):
        abort(403)

    # Handle GET request (display edit form)
    if request.method == "GET":
        return render_template("edit_album.html", album=album)

    # Handle POST request (update album details)
    title = request.form.get("title", "").strip()
    artist = request.form.get("artist", "").strip()
    year_str = request.form.get("year", "").strip()

    # Validate required fields
    if not title or not artist:
        flash("Title and artist are required", "error")
        return redirect(url_for("albums.edit_album", album_id=album_id))

    # Validate year
    year = None
    if year_str:
        try:
            year = int(year_str)
        except ValueError:
            flash("Year must be a number from 1900 to 9999", "error")
            return redirect(url_for("albums.edit_album", album_id=album_id))
        if not 1900 <= year <= 9999:
            flash("Year must be a number from 1900 to 9999", "error")
            return redirect(url_for("albums.edit_album", album_id=album_id))

    # Update album
    get_db().albums.update_one(
        {"_id": ObjectId(album_id)},
        {
            "$set": {
                "title": title,
                "artist": artist,
                "year": year,
            }
        },
    )

    flash("Album details updated successfully!", "success")
    return redirect(url_for("albums.view_album", album_id=album_id))

@albums_bp.route("/a/<album_id>/delete", methods=["GET", "POST"])
@login_required
def delete_album(album_id: str):
    album = get_album_by_id(album_id)

    if album is None:
        abort(404)

    if str(current_user._id) != str(album["user_id"]):
        abort(403)

    if request.method == "GET":
        return render_template("delete_album.html", album=album)

    get_db().albums.delete_one(
        {"_id": ObjectId(album_id)}
    )

    flash("Album deleted successfully!", "success")

    return redirect(url_for("profiles.my_profile"))

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
            flash("Invalid status", "review-error")
            return redirect(url_for("albums.view_album", album_id=album_id, _anchor="review-form"))

        # Validate and parse rating
        try:
            rating = parse_rating(rating_str)
        except ValueError:
            flash("Rating must be a number from 1 to 5 in steps of 0.5", "review-error")
            return redirect(url_for("albums.view_album", album_id=album_id, _anchor="review-form"))

        # Only listened albums carry a rating
        if status == STATUS_WANT_TO_LISTEN:
            rating = None

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

        flash("Review updated successfully!", "review-success")
        return redirect(url_for("albums.view_album", album_id=album_id, _anchor="review-form"))

    # Handle GET request (display album)
    # Fetch owner info
    owner = get_db().users.find_one({"_id": album["user_id"]})
    if owner is None:
        abort(404)

    # Determine if current user is owner
    is_owner = _current_user_id() == str(album["user_id"])

    # Format created date
    created_date = format_created_date(album.get("created_at", datetime.now(timezone.utc)))

    return render_template(
        "album.html",
        album=album,
        owner=owner,
        is_owner=is_owner,
        created_date=created_date,
    )
