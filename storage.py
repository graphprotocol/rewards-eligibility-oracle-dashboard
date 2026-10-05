"""
Round-trips the generator's working state between runs.

Locally this is a no-op. The JSON working files and reo.db sit in the repository
root and persist because the directory does, so `python3 generate_dashboard.py`
behaves exactly as it always has.

On a serverless host the filesystem is per-invocation, which would silently
break every feature that compares one run to the last: status-change detection,
`last_status_change_date`, the cumulative activity log, streak calculation, and
the ENS cache. Each run would see a blank slate and conclude nothing had ever
changed. So the same files are pulled from Vercel Blob before a run and pushed
back after it.

Everything here keys off BLOB_READ_WRITE_TOKEN. Without it, pull() and push()
do nothing at all — that absence is what keeps local development unchanged.

Single-writer by construction: exactly one cron job ever writes this state, so
there is no read-modify-write race to worry about. Do not add a second writer
without replacing this with something that has real atomicity.
"""
from __future__ import annotations

import fnmatch
import os
from typing import Iterable

# Blob pathname prefix. Keeps working state namespaced away from the published
# assets (data.json, index.html) that live at the store root.
STATE_PREFIX = "state/"

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

    from vercel.blob import download_file, list_objects

    os.makedirs(state_dir, exist_ok=True)
    restored = 0

    cursor = None
    while True:
        page = list_objects(prefix=STATE_PREFIX, cursor=cursor)
        blobs = page.get("blobs", []) if isinstance(page, dict) else page.blobs
        for blob in blobs:
            pathname = blob["pathname"] if isinstance(blob, dict) else blob.pathname
            url = blob["url"] if isinstance(blob, dict) else blob.url
            name = pathname[len(STATE_PREFIX):]
            if not name or not _matches_state(name):
                continue
            download_file(url, os.path.join(state_dir, name), overwrite=True)
            restored += 1

        has_more = page.get("hasMore", False) if isinstance(page, dict) else page.has_more
        cursor = page.get("cursor") if isinstance(page, dict) else getattr(page, "cursor", None)
        if not has_more or not cursor:
            break

    print(f"✓ Restored {restored} state file(s) from Blob")
    return restored


def push(state_dir: str) -> int:
    """
    Upload the current state so the next run can compare against it. Returns the
    number of files stored.
    """
    if not is_enabled():
        return 0

    from vercel.blob import upload_file

    stored = 0
    for name in sorted(os.listdir(state_dir)):
        path = os.path.join(state_dir, name)
        if not os.path.isfile(path) or not _matches_state(name):
            continue
        # Working state is never fetched by a browser, so it must not sit in a
        # CDN cache that would hand a stale copy back to the next run.
        upload_file(path, f"{STATE_PREFIX}{name}", overwrite=True, cache_control_max_age=0)
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

    from vercel.blob import upload_file

    result = upload_file(
        local_path,
        blob_path,
        overwrite=True,
        content_type=content_type,
        cache_control_max_age=max_age,
    )
    url = result["url"] if isinstance(result, dict) else result.url
    print(f"✓ Published {blob_path} → {url}")
    return url


def state_files_present(state_dir: str) -> Iterable[str]:
    """Names of state files currently in state_dir. Used for logging."""
    if not os.path.isdir(state_dir):
        return []
    return [n for n in sorted(os.listdir(state_dir)) if _matches_state(n)]
