"""Profile is public to view, has owner-only controls (eg editing)."""

from typing import Any, Optional

from bson import ObjectId
from pymongo.errors import DuplicateKeyError, PyMongoError
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from werkzeug.exceptions import RequestEntityTooLarge

from covers import (
    ProfilePictureError,
    delete_profile_picture,
    store_profile_picture,
)
from db import get_db

STATUS_LISTENED = "listened"
STATUS_WANT_TO_LISTEN = "want_to_listen"

SORT_RECENT = "recent"
SORT_TITLE = "title"
SORT_ARTIST = "artist"
SORT_RATING = "rating"

profiles_bp = Blueprint("profiles", __name__)


@profiles_bp.errorhandler(RequestEntityTooLarge)
def profile_upload_too_large(_error: RequestEntityTooLarge):
    flash("Profile picture must be 2 MB or smaller", "error")
    return redirect(url_for("profiles.edit_profile"))


def get_user_by_username(username: str) -> Optional[dict[str, Any]]:
    """Look up a user by exact username, as the login code does."""
    return get_db().users.find_one({"username": username.strip()})


def get_user_by_id(user_id: str) -> Optional[dict[str, Any]]:
    """Look up a user by the string form of their _id."""
    if not ObjectId.is_valid(user_id):
        return None
    return get_db().users.find_one({"_id": ObjectId(user_id)})


def sort_albums(albums: list[dict[str, Any]], sort: str) -> None:
    """Sort albums in place. Albums should already be newest first, so ties keep that order."""
    if sort == SORT_TITLE:
        albums.sort(key=lambda a: a.get("title", "").lower())
    elif sort == SORT_ARTIST:
        albums.sort(key=lambda a: a.get("artist", "").lower())
    elif sort == SORT_RATING:
        # Highest first, unrated albums last.
        albums.sort(key=lambda a: -a["rating"] if a.get("rating") else 1)


def get_profile_data(user: dict[str, Any], sort: str = SORT_RATING) -> dict[str, Any]:
    """Build the profile dict the template needs for user.
    """
    albums = list(
        get_db().albums.find({"user_id": user["_id"]}).sort("created_at", -1)
    )
    listened = [a for a in albums if a.get("status") == STATUS_LISTENED]
    want_to_listen = [
        a for a in albums if a.get("status") == STATUS_WANT_TO_LISTEN
    ]
    sort_albums(listened, sort)
    sort_albums(want_to_listen, sort)

    ratings = [a["rating"] for a in listened if a.get("rating")]
    average = round(sum(ratings) / len(ratings), 1) if ratings else None

    return {
        "username": user["username"],
        "profile_picture_id": user.get("profile_picture_id"),
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


def _cleanup_uploaded_picture(picture_id: Optional[ObjectId]) -> None:
    """Remove a newly uploaded image when the user document could not be updated."""
    if picture_id is None:
        return
    try:
        delete_profile_picture(picture_id)
    except PyMongoError:
        current_app.logger.exception(
            "Could not clean up orphaned profile picture %s", picture_id
        )


@profiles_bp.route("/profile/edit", methods=["GET", "POST"])
@login_required
def edit_profile():
    """Edit the logged-in user's username and profile picture."""
    if request.method == "GET":
        return render_template(
            "edit_profile.html",
            username=current_user.username,
            profile_picture_id=current_user.profile_picture_id,
        )

    username = request.form.get("username", "").strip()
    if not username:
        flash("Username is required", "error")
        return render_template(
            "edit_profile.html",
            username=username,
            profile_picture_id=current_user.profile_picture_id,
        )

    duplicate = get_db().users.find_one(
        {"username": username, "_id": {"$ne": current_user._id}},
        {"_id": 1},
    )
    if duplicate is not None:
        flash("Username already exists", "error")
        return render_template(
            "edit_profile.html",
            username=username,
            profile_picture_id=current_user.profile_picture_id,
        )

    try:
        new_picture_id = store_profile_picture(request.files.get("profile_picture"))
    except ProfilePictureError as error:
        flash(str(error), "error")
        return render_template(
            "edit_profile.html",
            username=username,
            profile_picture_id=current_user.profile_picture_id,
        )
    except PyMongoError:
        current_app.logger.exception("Could not upload profile picture")
        flash("Profile picture could not be uploaded. Please try again.", "error")
        return render_template(
            "edit_profile.html",
            username=username,
            profile_picture_id=current_user.profile_picture_id,
        )

    old_picture_id = current_user.profile_picture_id
    remove_picture = request.form.get("remove_profile_picture") == "yes"
    updates: dict[str, Any] = {"username": username}
    if new_picture_id is not None:
        updates["profile_picture_id"] = new_picture_id
        update = {"$set": updates}
    elif remove_picture:
        update = {"$set": updates, "$unset": {"profile_picture_id": ""}}
    else:
        update = {"$set": updates}

    try:
        result = get_db().users.update_one({"_id": current_user._id}, update)
    except DuplicateKeyError:
        _cleanup_uploaded_picture(new_picture_id)
        flash("Username already exists", "error")
        return render_template(
            "edit_profile.html",
            username=username,
            profile_picture_id=old_picture_id,
        )
    except PyMongoError:
        _cleanup_uploaded_picture(new_picture_id)
        current_app.logger.exception("Could not update profile")
        flash("Your profile could not be saved. Please try again.", "error")
        return render_template(
            "edit_profile.html",
            username=username,
            profile_picture_id=old_picture_id,
        )

    if result.matched_count != 1:
        _cleanup_uploaded_picture(new_picture_id)
        abort(404)

    if new_picture_id is not None or remove_picture:
        try:
            delete_profile_picture(old_picture_id)
        except PyMongoError:
            current_app.logger.exception(
                "Could not delete replaced profile picture %s", old_picture_id
            )

    current_user.username = username
    if new_picture_id is not None:
        current_user.profile_picture_id = new_picture_id
    elif remove_picture:
        current_user.profile_picture_id = None
    flash("Profile updated successfully!", "success")
    return redirect(url_for("profiles.view_profile", username=username))


@profiles_bp.get("/u/<username>")
def view_profile(username: str) -> str:
    """Show a user's profile."""
    user = get_user_by_username(username)
    if user is None:
        abort(404)
    sort = request.args.get("sort", "").strip()
    if sort not in [SORT_RECENT, SORT_TITLE, SORT_ARTIST]:
        sort = SORT_RATING
    return render_template(
        "profile.html",
        profile=get_profile_data(user, sort),
        sort=sort,
        is_owner=_current_user_id() == str(user["_id"]),
    )
