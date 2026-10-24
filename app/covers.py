"""Album cover images - stored in GridFS and served by id."""

from typing import Optional

import gridfs
from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, Response, abort
from gridfs.errors import NoFile
from werkzeug.datastructures import FileStorage

from db import get_db

MAX_COVER_BYTES = 2 * 1024 * 1024

covers_bp = Blueprint("covers", __name__)


class CoverError(ValueError):
    """Raised with a user-facing message when an uploaded cover is unusable."""


def _detect_image_type(data: bytes) -> Optional[str]:
    """Return the image MIME type from the file's magic bytes, or None.

    The browser-supplied filename and content type are user-controlled, so the
    bytes decide. SVG is deliberately unsupported because it can carry scripts.
    """
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if data.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if data.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def _bucket() -> gridfs.GridFS:
    return gridfs.GridFS(get_db(), collection="covers")


def store_cover(upload: Optional[FileStorage]) -> Optional[ObjectId]:
    """Validate and store an uploaded cover, returning its id.

    Returns None when no file was chosen. Raises CoverError if the file is too
    large or is not a PNG, JPEG, GIF, or WebP image.
    """
    if upload is None or not upload.filename:
        return None

    data = upload.stream.read(MAX_COVER_BYTES + 1)
    if len(data) > MAX_COVER_BYTES:
        raise CoverError(
            f"Cover image must be {MAX_COVER_BYTES // (1024 * 1024)} MB or smaller"
        )
    content_type = _detect_image_type(data)
    if content_type is None:
        raise CoverError("Cover must be a PNG, JPEG, GIF, or WebP image")

    return _bucket().put(data, content_type=content_type)


def delete_cover(cover_id: Optional[ObjectId]) -> None:
    """Remove a stored cover. Safe to call with None or an id that is gone."""
    if cover_id is not None:
        _bucket().delete(cover_id)


@covers_bp.get("/covers/<cover_id>")
def get_cover(cover_id: str) -> Response:
    """Serve a stored cover image."""
    try:
        stored = _bucket().get(ObjectId(cover_id))
    except (InvalidId, NoFile):
        abort(404)

    response = Response(stored.read(), mimetype=stored.content_type)
    # A cover's bytes never change for a given id, so it can be cached for good.
    response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
