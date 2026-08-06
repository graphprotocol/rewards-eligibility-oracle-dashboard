"""
Shared pytest fixtures for tests/unit/.
"""

import os
import shutil
import tempfile
from unittest.mock import patch

import pytest


@pytest.fixture
def clean_db():
    """
    Points database.DB_PATH at a fresh temp SQLite file and initializes the
    schema, so each test runs against an isolated, empty database. Mirrors
    the patch('database.DB_PATH', ...) pattern already used in
    test_multi_environment.py.
    """
    tmp_dir = tempfile.mkdtemp()
    test_db_path = os.path.join(tmp_dir, "test_reo.db")

    with patch("database.DB_PATH", test_db_path):
        from database import init_db

        init_db()
        yield

    shutil.rmtree(tmp_dir, ignore_errors=True)
