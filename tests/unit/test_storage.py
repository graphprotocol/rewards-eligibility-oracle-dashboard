"""
Tests for storage.py, which keeps the hourly refresh's working files and its
published data.json in Vercel Blob between runs.

These drive storage.py through the real Vercel Blob SDK, with an in-memory
stand-in for the Blob service plugged in underneath it as the SDK's HTTP
transport. A release of the SDK that renames or reshapes the functions
storage.py calls then fails here instead of in production, where it stops the
dashboard refreshing while the page keeps showing the last data it had.
"""

import json
import os
import sys
from datetime import UTC, datetime
from urllib.parse import quote, unquote, urlsplit

import httpx2 as httpx
import pytest
from vercel.api import session

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

import storage

STORE_ID = "teststore"
TOKEN = f"vercel_blob_rw_{STORE_ID}_secret"
API_HOST = "vercel.com"
DELIVERY_HOST = f"{STORE_ID}.public.blob.vercel-storage.com"

# One file per state pattern, plus files that must never be stored.
STATE_FILES = {
    "reo.db": b"SQLite format 3\x00 binary payload \xff\xfe",
    "ens_resolution.json": b'{"0xabc": "indexer.eth"}',
    "last_transaction.json": b'{"block": 1}',
    "active_indexers_mainnet.json": b'[{"address": "0xabc"}]',
    "activity_log_indexers_status_changes_testnet.json": b"[]",
}
NOT_STATE_FILES = {
    "notes.txt": b"scratch",
    "active_indexers.json.example": b"{}",
}


class FakeBlobService:
    """
    Answers the SDK's requests the way the Blob service does: PUT to the API
    stores an object, GET on the API lists objects a page at a time, and GET on
    the store's public domain downloads one.
    """

    def __init__(self, page_size=2):
        self.page_size = page_size
        self.objects = {}  # pathname -> {"body", "access", "content_type", "max_age"}
        self.requests = []

    def handle(self, request):
        self.requests.append(request)
        url = urlsplit(str(request.url))
        if url.hostname == API_HOST:
            if request.headers.get("authorization") != f"Bearer {TOKEN}":
                return self._error(403, "forbidden", "Access denied")
            if request.method == "PUT":
                return self._put(request)
            if request.method == "GET":
                return self._list(request)
        if url.hostname == DELIVERY_HOST and request.method == "GET":
            return self._download(url.path)
        return self._error(400, "bad_request", f"Unexpected {request.method} {request.url}")

    def put_object(self, pathname, body, content_type="application/octet-stream"):
        self.objects[pathname] = {
            "body": body,
            "access": "public",
            "content_type": content_type,
            "max_age": None,
        }

    def _url(self, pathname):
        return f"https://{DELIVERY_HOST}/{quote(pathname)}"

    def _put(self, request):
        pathname = request.url.params["pathname"]
        if pathname in self.objects and request.headers.get("x-allow-overwrite") != "1":
            return self._error(400, "bad_request", "This blob already exists")
        content_type = request.headers.get("x-content-type", "application/octet-stream")
        max_age = request.headers.get("x-cache-control-max-age")
        self.objects[pathname] = {
            "body": request.read(),
            "access": request.headers.get("x-vercel-blob-access"),
            "content_type": content_type,
            "max_age": int(max_age) if max_age is not None else None,
        }
        return httpx.Response(200, json={
            "url": self._url(pathname),
            "downloadUrl": self._url(pathname) + "?download=1",
            "pathname": pathname,
            "contentType": content_type,
            "contentDisposition": f'inline; filename="{pathname.rsplit("/", 1)[-1]}"',
            "etag": f'"{len(self.objects)}"',
        })

    def _list(self, request):
        prefix = request.url.params.get("prefix", "")
        start = int(request.url.params.get("cursor", "0"))
        names = sorted(n for n in self.objects if n.startswith(prefix))
        page = names[start:start + self.page_size]
        has_more = start + self.page_size < len(names)
        uploaded = datetime(2026, 11, 20, tzinfo=UTC).isoformat().replace("+00:00", "Z")
        body = {
            "blobs": [{
                "url": self._url(n),
                "downloadUrl": self._url(n) + "?download=1",
                "pathname": n,
                "size": len(self.objects[n]["body"]),
                "uploadedAt": uploaded,
                "etag": f'"{n}"',
            } for n in page],
            "hasMore": has_more,
        }
        if has_more:
            body["cursor"] = str(start + self.page_size)
        return httpx.Response(200, json=body)

    def _download(self, path):
        pathname = unquote(path.lstrip("/"))
        obj = self.objects.get(pathname)
        if obj is None:
            return self._error(404, "not_found", "The requested blob does not exist")
        return httpx.Response(200, content=obj["body"], headers={
            "content-type": obj["content_type"],
            "etag": f'"{pathname}"',
        })

    @staticmethod
    def _error(status, code, message):
        return httpx.Response(status, json={"error": {"code": code, "message": message}})


@pytest.fixture
def blob(monkeypatch):
    """A Blob store the SDK talks to for the length of one test."""
    for name in ("BLOB_STORE_ID", "VERCEL_OIDC_TOKEN", "VERCEL_BLOB_API_URL",
                 "NEXT_PUBLIC_VERCEL_BLOB_API_URL", "VERCEL_BLOB_READ_WRITE_TOKEN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("BLOB_READ_WRITE_TOKEN", TOKEN)
    service = FakeBlobService()

    def client():
        return httpx.Client(transport=httpx.MockTransport(service.handle))

    with session(httpx_client_factory=client):
        yield service


def write_files(directory, files):
    directory.mkdir(parents=True, exist_ok=True)
    for name, body in files.items():
        (directory / name).write_bytes(body)


def read_files(directory):
    return {p.name: p.read_bytes() for p in sorted(directory.iterdir())}


class TestPushAndPull:
    def test_round_trips_every_state_file(self, blob, tmp_path):
        write_files(tmp_path / "run1", {**STATE_FILES, **NOT_STATE_FILES})

        assert storage.push(str(tmp_path / "run1")) == len(STATE_FILES)
        assert storage.pull(str(tmp_path / "run2")) == len(STATE_FILES)

        assert read_files(tmp_path / "run2") == STATE_FILES

    def test_stores_state_under_its_prefix_uncached_and_public(self, blob, tmp_path):
        write_files(tmp_path / "run", {**STATE_FILES, **NOT_STATE_FILES})

        storage.push(str(tmp_path / "run"))

        assert sorted(blob.objects) == sorted(f"state/{n}" for n in STATE_FILES)
        for obj in blob.objects.values():
            # A cached copy would hand the next run stale state.
            assert obj["max_age"] == 0
            assert obj["access"] == "public"

    def test_later_run_overwrites_earlier_state(self, blob, tmp_path):
        write_files(tmp_path / "run1", {"ens_resolution.json": b'{"old": true}'})
        write_files(tmp_path / "run2", {"ens_resolution.json": b'{"new": true}'})

        storage.push(str(tmp_path / "run1"))
        storage.push(str(tmp_path / "run2"))
        storage.pull(str(tmp_path / "run3"))

        assert read_files(tmp_path / "run3") == {"ens_resolution.json": b'{"new": true}'}

    def test_pull_on_first_run_restores_nothing(self, blob, tmp_path):
        assert storage.pull(str(tmp_path / "run")) == 0
        assert read_files(tmp_path / "run") == {}

    def test_pull_skips_blobs_that_are_not_state(self, blob, tmp_path):
        blob.put_object("data.json", b"{}", "application/json")
        blob.put_object("state/unexpected.txt", b"x")
        blob.put_object("state/reo.db", b"db")

        assert storage.pull(str(tmp_path / "run")) == 1
        assert read_files(tmp_path / "run") == {"reo.db": b"db"}

    def test_pull_skips_names_that_point_into_a_subfolder(self, blob, tmp_path):
        # The state patterns' "*" also matches "/", so this name would match
        # active_indexers_*.json and be written to a folder that does not exist.
        blob.put_object("state/active_indexers_x/y.json", b"[]")
        blob.put_object("state/reo.db", b"db")

        assert storage.pull(str(tmp_path / "run")) == 1
        assert read_files(tmp_path / "run") == {"reo.db": b"db"}

    def test_pull_follows_every_page_of_the_listing(self, blob, tmp_path):
        blob.page_size = 1
        for name, body in STATE_FILES.items():
            blob.put_object(f"state/{name}", body)

        assert storage.pull(str(tmp_path / "run")) == len(STATE_FILES)

        lists = [r for r in blob.requests if r.method == "GET" and r.url.host == API_HOST]
        assert len(lists) == len(STATE_FILES)


class TestPublish:
    def test_publishes_data_json_with_its_headers(self, blob, tmp_path):
        data = tmp_path / "data.json"
        data.write_text(json.dumps({"environments": []}))

        url = storage.publish(str(data), "data.json", content_type="application/json", max_age=0)

        assert url == f"https://{DELIVERY_HOST}/data.json"
        assert blob.objects["data.json"] == {
            "body": data.read_bytes(),
            "access": "public",
            "content_type": "application/json",
            "max_age": 0,
        }

    def test_republishing_replaces_the_previous_copy(self, blob, tmp_path):
        data = tmp_path / "data.json"
        data.write_text("1")
        storage.publish(str(data), "data.json", content_type="application/json", max_age=0)
        data.write_text("2")
        storage.publish(str(data), "data.json", content_type="application/json", max_age=0)

        assert blob.objects["data.json"]["body"] == b"2"


class TestWithoutBlob:
    def test_does_nothing_without_a_token(self, blob, tmp_path, monkeypatch):
        monkeypatch.delenv("BLOB_READ_WRITE_TOKEN")
        write_files(tmp_path / "run", STATE_FILES)

        assert storage.pull(str(tmp_path / "other")) == 0
        assert storage.push(str(tmp_path / "run")) == 0
        assert storage.publish(str(tmp_path / "run" / "reo.db"), "data.json",
                               content_type="application/json", max_age=0) is None
        assert blob.requests == []
