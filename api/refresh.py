"""Regenerates the dashboard data. Invoked hourly by Vercel Cron.

The serverless equivalent of scheduler.py: it runs the same pipeline main() has
always run, with 2 differences forced by a per-invocation filesystem.

  1. Working state is pulled from Blob before the run and pushed back after it,
     so run-to-run comparison keeps working (see storage.py).
  2. It does not render index.html: api/render.js does that per request from the
     published data.json, since a function cannot write into a deployment.

Idempotency: Vercel cron delivery is best effort, so a run may be missed or sent
twice. The pipeline recomputes everything from on-chain state rather than
incrementing anything, so a duplicate run gives the same result as a single one.
"""
import json
import os
import sys
import tempfile
import traceback
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler

# The function bundle has the project root as its working directory, so the
# repository's modules import normally.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import storage  # noqa: E402


def _authorized(headers) -> bool:
    """
    Vercel sends CRON_SECRET as a bearer token on cron invocations. Without it
    anyone could call this and burn a full pipeline run against the RPC endpoints
    and the Graph API key, so an unset CRON_SECRET denies rather than allows.
    """
    secret = os.getenv("CRON_SECRET")
    if not secret:
        return False
    return headers.get("authorization") == f"Bearer {secret}"


def run() -> dict:
    """Run the pipeline in a scratch directory, round-tripping state via Blob."""
    started = datetime.now(UTC)

    # Every working-file path in generate_dashboard.py is relative to the
    # working directory, so moving the process into a writable scratch dir
    # redirects all of them at once. /tmp is the only writable location.
    state_dir = os.path.join(tempfile.gettempdir(), "reo-state")
    output_dir = os.path.join(tempfile.gettempdir(), "reo-output")
    os.makedirs(state_dir, exist_ok=True)
    os.makedirs(output_dir, exist_ok=True)

    restored = storage.pull(state_dir)

    original_cwd = os.getcwd()
    os.chdir(state_dir)
    try:
        # Import only after chdir: database.py opens reo.db relative to the
        # working directory at import time, so importing earlier would use the
        # read-only project root instead of the reo.db just pulled from Blob.
        import generate_dashboard  # noqa: E402, PLC0415

        os.environ["REO_OUTPUT_DIR"] = output_dir
        # render=False: there is no node binary here and nothing to render into.
        # api/render.js builds the page per request from the data.json below.
        ok = generate_dashboard.main(render=False)
    finally:
        os.chdir(original_cwd)

    stored = storage.push(state_dir)

    data_path = os.path.join(output_dir, "data.json")
    published = None
    if os.path.isfile(data_path):
        # The render function reads this. Its own response carries the cache
        # headers that matter, so this copy is fetched fresh each time.
        published = storage.publish(
            data_path, "data.json", content_type="application/json", max_age=0
        )

    elapsed = (datetime.now(UTC) - started).total_seconds()
    return {
        "ok": bool(ok) and published is not None,
        "generated": bool(ok),
        "published": published is not None,
        "state_restored": restored,
        "state_stored": stored,
        "elapsed_seconds": round(elapsed, 1),
    }


class handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if not _authorized(self.headers):
            self._respond(401, {"ok": False, "error": "unauthorized"})
            return

        try:
            result = run()
        except Exception as error:  # noqa: BLE001 - surfaced in the response body
            traceback.print_exc()
            self._respond(500, {"ok": False, "error": f"{type(error).__name__}: {error}"})
            return

        # A run that fetched nothing must not report success, or a silently
        # empty dashboard looks like a healthy cron in the logs.
        self._respond(200 if result["ok"] else 500, result)

    def _respond(self, status: int, payload: dict) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)
