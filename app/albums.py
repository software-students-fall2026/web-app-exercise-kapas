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
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required

from covers import CoverError, delete_cover, store_cover
from db import get_db

STATUS_LISTENED = "listened"
STATUS_WANT_TO_LISTEN = "want_to_listen"

SORT_RECENT = "recent"
SORT_TITLE = "title"
SORT_ARTIST = "artist"
SORT_RATING = "rating"

albums_bp = Blueprint("albums", __name__)


@albums_bp.get("/search")
def search_albums():
    """Search albums by title or artist, optionally filtering by status and sorting."""
    query = request.args.get("q", "").strip()
    status = request.args.get("status", "").strip()
    # The status filter means "albums I marked as ...", so it needs a logged-in user.
    user_id = current_user._id if current_user.is_authenticated else None
    if user_id is None or status not in [STATUS_LISTENED, STATUS_WANT_TO_LISTEN]:
        status = ""
    sort = request.args.get("sort", "").strip()
    if sort not in [SORT_TITLE, SORT_ARTIST, SORT_RATING]:
        sort = SORT_RECENT

    db = get_db()
    album_filter: dict[str, Any] = {}
    if query:
        escaped_query = re.escape(query)
        album_filter["$or"] = [
            {"title": {"$regex": escaped_query, "$options": "i"}},
            {"artist": {"$regex": escaped_query, "$options": "i"}},
        ]
    if status:
        album_filter["_id"] = {
            "$in": db.reviews.distinct("album_id", {"user_id": user_id, "status": status})
        }

    results = list(db.albums.find(album_filter).sort("created_at", -1).limit(50))
    reviews_by_album = get_reviews_for_albums([album["_id"] for album in results])
    creators = get_usernames([album["user_id"] for album in results])
    current_uid = _current_user_id()

    for album in results:
        album["owner_username"] = creators.get(album["user_id"])
        album["entries"] = reviews_by_album.get(album["_id"], [])
        # The logged-in user's own review, so results can show it or offer quick-add.
        album["my_review"] = next(
            (e for e in album["entries"] if str(e["user_id"]) == current_uid), None
        )
        album["user_count"] = len(album["entries"])
        album["average_rating"] = average_rating(album["entries"])

    # Results are already newest first, and sort() is stable, so ties keep that order.
    if sort == SORT_TITLE:
        results.sort(key=lambda a: a.get("title", "").lower())
    elif sort == SORT_ARTIST:
        results.sort(key=lambda a: a.get("artist", "").lower())
    elif sort == SORT_RATING:
        # Highest first, unrated albums last.
        results.sort(
            key=lambda a: -a["average_rating"]
            if a["average_rating"] is not None
            else 1
        )

    return render_template(
        "search.html",
        query=query,
        status=status,
        sort=sort,
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


def find_matching_album(
    title: str, artist: str, year: Optional[int]
) -> Optional[dict[str, Any]]:
    """Find an album already added with the same title, artist (any case) and year."""
    return get_db().albums.find_one(
        {
            "title": {"$regex": f"^{re.escape(title)}$", "$options": "i"},
            "artist": {"$regex": f"^{re.escape(artist)}$", "$options": "i"},
            "year": year,
        }
    )


def get_usernames(user_ids: list[ObjectId]) -> dict[ObjectId, str]:
    """Map user ids to usernames. Ids of deleted users are left out."""
    return {
        user["_id"]: user["username"]
        for user in get_db().users.find(
            {"_id": {"$in": list(set(user_ids))}}, {"username": 1}
        )
    }


def get_reviews_for_albums(
    album_ids: list[ObjectId],
) -> dict[ObjectId, list[dict[str, Any]]]:
    """Group every user's review of the given albums by album id, oldest first.

    Each review gets a "username" key; reviews by deleted users are left out.
    """
    reviews = list(
        get_db().reviews.find({"album_id": {"$in": album_ids}}).sort("created_at", 1)
    )
    usernames = get_usernames([review["user_id"] for review in reviews])

    grouped: dict[ObjectId, list[dict[str, Any]]] = {}
    for review in reviews:
        if review["user_id"] not in usernames:
            continue
        review["username"] = usernames[review["user_id"]]
        grouped.setdefault(review["album_id"], []).append(review)
    return grouped


def average_rating(reviews: list[dict[str, Any]]) -> Optional[float]:
    """Average of the ratings in reviews, or None if nobody has rated it."""
    ratings = [review["rating"] for review in reviews if review.get("rating") is not None]
    return round(sum(ratings) / len(ratings), 1) if ratings else None


def save_review(
    album_id: ObjectId,
    user_id: ObjectId,
    status: str,
    rating: Optional[float],
    review: str,
) -> None:
    """Create or replace user_id's review of album_id."""
    now = datetime.now(timezone.utc)
    get_db().reviews.update_one(
        {"album_id": album_id, "user_id": user_id},
        {
            "$set": {
                "status": status,
                "rating": rating,
                "review": review or None,
                "updated_at": now,
            },
            "$setOnInsert": {"created_at": now},
        },
        upsert=True,
    )


def remove_album(album: dict[str, Any]) -> None:
    """Delete an album along with every review of it and its cover."""
    db = get_db()
    db.reviews.delete_many({"album_id": album["_id"]})
    db.albums.delete_one({"_id": album["_id"]})
    delete_cover(album.get("cover_id"))


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


@albums_bp.get("/a/search-existing")
@login_required
def search_existing_albums():
    query = request.args.get("q", "").strip()

    if len(query) < 2:
        return jsonify([])

    albums = get_db().albums.find(
        {"title": {"$regex": re.escape(query), "$options": "i"}}
    ).limit(10)

    results = []
    seen = set()

    for album in albums:
        key = (
            album.get("title", "").lower(),
            album.get("artist", "").lower(),
            album.get("year"),
        )

        if key not in seen:
            seen.add(key)
            results.append(
                {
                    "title": album.get("title", ""),
                    "artist": album.get("artist", ""),
                    "year": album.get("year"),
                }
            )

    return jsonify(results)


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

    db = get_db()
    # An album someone already added is shared: add this user's review to it
    # instead of creating a duplicate.
    album = find_matching_album(title, artist, year)

    # Stored last so a rejected form never leaves an orphaned image behind. An
    # existing album keeps its cover; an upload only fills in a missing one.
    cover_id = None
    if album is None or album.get("cover_id") is None:
        try:
            cover_id = store_cover(request.files.get("cover"))
        except CoverError as error:
            flash(str(error), "error")
            return render_template("add_album.html")

    if album is None:
        album_id = db.albums.insert_one(
            {
                "title": title,
                "artist": artist,
                "year": year,
                "cover_id": cover_id,
                "user_id": current_user._id,
                "created_at": datetime.now(timezone.utc),
            }
        ).inserted_id
    else:
        album_id = album["_id"]
        if cover_id is not None:
            db.albums.update_one({"_id": album_id}, {"$set": {"cover_id": cover_id}})
        if db.reviews.find_one({"album_id": album_id, "user_id": current_user._id}):
            flash("This album was already in your list, so your review was updated.", "success")

    save_review(album_id, current_user._id, status, rating, review)

    return redirect(url_for("albums.view_album", album_id=str(album_id)))


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

    try:
        new_cover_id = store_cover(request.files.get("cover"))
    except CoverError as error:
        flash(str(error), "error")
        return redirect(url_for("albums.edit_album", album_id=album_id))

    # Update album
    updates: dict[str, Any] = {"title": title, "artist": artist, "year": year}
    if new_cover_id is not None:
        updates["cover_id"] = new_cover_id
    get_db().albums.update_one({"_id": ObjectId(album_id)}, {"$set": updates})
    if new_cover_id is not None:
        delete_cover(album.get("cover_id"))

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

    if album_has_other_reviewers(album, current_user._id):
        flash(
            "Other people have reviewed this album, so it can't be deleted. "
            "You can remove your own review instead.",
            "error",
        )
        return redirect(url_for("albums.view_album", album_id=album_id))

    if request.method == "GET":
        return render_template("delete_album.html", album=album)

    remove_album(album)

    flash("Album deleted successfully!", "success")

    return redirect(url_for("profiles.my_profile"))


def album_has_other_reviewers(album: dict[str, Any], user_id: ObjectId) -> bool:
    """True if anyone other than user_id has reviewed the album."""
    return (
        get_db().reviews.find_one(
            {"album_id": album["_id"], "user_id": {"$ne": user_id}}, {"_id": 1}
        )
        is not None
    )


@albums_bp.route("/a/<album_id>/review/delete", methods=["GET", "POST"])
@login_required
def delete_review(album_id: str):
    """Remove the logged-in user's review. The album goes too once nobody has it."""
    album = get_album_by_id(album_id)
    if album is None:
        abort(404)

    db = get_db()
    review = db.reviews.find_one({"album_id": album["_id"], "user_id": current_user._id})
    if review is None:
        abort(404)

    is_last_review = not album_has_other_reviewers(album, current_user._id)

    if request.method == "GET":
        return render_template(
            "delete_review.html", album=album, is_last_review=is_last_review
        )

    db.reviews.delete_one({"_id": review["_id"]})
    if is_last_review:
        remove_album(album)
        flash("Album removed from your list.", "success")
        return redirect(url_for("profiles.my_profile"))

    flash("Your review was removed.", "success")
    return redirect(url_for("albums.view_album", album_id=album_id))


@albums_bp.route("/a/<album_id>", methods=["GET", "POST"])
def view_album(album_id: str):
    """View an album with everyone's reviews; logged-in users can save their own."""
    # Fetch album
    album = get_album_by_id(album_id)
    if album is None:
        abort(404)

    # Handle POST request (save the logged-in user's rating/review)
    if request.method == "POST":
        if _current_user_id() is None:
            return current_app.login_manager.unauthorized()

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

        save_review(album["_id"], current_user._id, status, rating, review)

        flash("Review saved successfully!", "review-success")
        return redirect(url_for("albums.view_album", album_id=album_id, _anchor="review-form"))

    # Handle GET request (display album)
    # The creator may have deleted their account; the album still shows.
    owner = get_db().users.find_one({"_id": album["user_id"]})

    current_uid = _current_user_id()
    is_owner = current_uid == str(album["user_id"])

    reviews = get_reviews_for_albums([album["_id"]]).get(album["_id"], [])
    my_review = next(
        (review for review in reviews if str(review["user_id"]) == current_uid), None
    )
    can_delete = is_owner and all(
        str(review["user_id"]) == current_uid for review in reviews
    )

    # Format created date
    created_date = format_created_date(album.get("created_at", datetime.now(timezone.utc)))

    return render_template(
        "album.html",
        album=album,
        owner=owner,
        is_owner=is_owner,
        can_delete=can_delete,
        reviews=reviews,
        my_review=my_review,
        average_rating=average_rating(reviews),
        created_date=created_date,
    )