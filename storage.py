"""Round-trips the generator's working state between runs through Vercel Blob.

Locally this is a no-op: the JSON working files and reo.db persist in the
repository root, so `python3 generate_dashboard.py` behaves as it always has.
On a serverless host the filesystem is per-invocation, so each run would see a
blank slate and silently break everything that compares one run to the last
(status changes, the activity log, streaks, the ENS cache). The files are pulled
from Blob before a run and pushed back after it.

Everything keys off BLOB_READ_WRITE_TOKEN: without it, pull(), push() and
publish() do nothing. Single writer by construction: one cron job writes this
state and there are no locks, so do not add a second writer without replacing
this with something that has real atomicity.
"""
from __future__ import annotations

import fnmatch
import os
from collections.abc import Iterable

# Blob pathname prefix. Keeps working state namespaced away from the published
# assets (data.json, index.html) that live at the store root.
STATE_PREFIX = "state/"

# The store is public: api/render.js fetches data.json by its plain URL, with no
# token. The Blob SDK needs the access level on every read and write, and it must
# match the store's.
ACCESS = "public"

# Which files constitute run-to-run state. Globs, because the per-environment
# files are named after whichever networks are configured.
STATE_PATTERNS = (
    "reo.db",
    "ens_resolution.json",
    "last_transaction.json",
    "active_indexers_*.json",
    "activity_log_indexers_status_changes_*.json",
)


def is_enabled() -> bool:
    """True when running somewhere with Blob configured."""
    return bool(os.getenv("BLOB_READ_WRITE_TOKEN"))


def _matches_state(name: str) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in STATE_PATTERNS)


def pull(state_dir: str) -> int:
    """
    Download previous-run state into state_dir. Returns the number of files
    restored (0 on the very first run, which is expected and not an error).
    """
    if not is_enabled():
        return 0

    from vercel.blob.sync import get_blob, query_blobs

    os.makedirs(state_dir, exist_ok=True)
    restored = 0

    # query_blobs follows the listing from page to page itself.
    for blob in query_blobs(prefix=STATE_PREFIX):
        name = blob.pathname[len(STATE_PREFIX):]
        # State files sit directly under the prefix; fnmatch's "*" also matches
        # "/", so without this a nested name could match and fail to write.
        if not name or "/" in name or not _matches_state(name):
            continue
        result = get_blob(blob.url, access=ACCESS)
        with open(os.path.join(state_dir, name), "wb") as f:
            f.write(result.body)
        restored += 1

    print(f"✓ Restored {restored} state file(s) from Blob")
    return restored


def push(state_dir: str) -> int:
    """
    Upload the current state so the next run can compare against it. Returns the
    number of files stored.
    """
    if not is_enabled():
        return 0

    from vercel.blob.sync import put_blob

    stored = 0
    for name in sorted(os.listdir(state_dir)):
        path = os.path.join(state_dir, name)
        if not os.path.isfile(path) or not _matches_state(name):
            continue
        with open(path, "rb") as f:
            body = f.read()
        # Working state is never fetched by a browser, so it must not sit in a
        # CDN cache that would hand a stale copy back to the next run.
        put_blob(
            f"{STATE_PREFIX}{name}",
            body,
            access=ACCESS,
            allow_overwrite=True,
            cache_control_max_age=0,
        )
        stored += 1

    print(f"✓ Stored {stored} state file(s) to Blob")
    return stored


def publish(local_path: str, blob_path: str, *, content_type: str, max_age: int) -> str | None:
    """
    Publish a generated artifact (data.json) for the render function to read.

    Distinct from push(): this is output, not state, and it is served rather
    than restored. Returns the blob URL, or None when Blob is not configured.
    """
    if not is_enabled():
        return None

    from vercel.blob.sync import put_blob

    with open(local_path, "rb") as f:
        body = f.read()
    result = put_blob(
        blob_path,
        body,
        access=ACCESS,
        content_type=content_type,
        allow_overwrite=True,
        cache_control_max_age=max_age,
    )
    url = result.url
    print(f"✓ Published {blob_path} → {url}")
    return url


def state_files_present(state_dir: str) -> Iterable[str]:
    """Names of state files currently in state_dir. Used for logging."""
    if not os.path.isdir(state_dir):
        return []
    return [n for n in sorted(os.listdir(state_dir)) if _matches_state(n)]
