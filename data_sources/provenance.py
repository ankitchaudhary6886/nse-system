"""Helpers for identifying and timestamping locally supplied source files."""

from datetime import datetime
from hashlib import sha256
from pathlib import Path


def file_metadata(path):
    """Return an artifact's content hash and local modification timestamp."""
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"Source artifact does not exist: {path}")

    digest = sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)

    modified_at = datetime.fromtimestamp(
        path.stat().st_mtime).astimezone().isoformat(timespec="seconds")
    return {
        "sha256": digest.hexdigest(),
        "modified_at": modified_at,
        "file_name": path.name,
    }
