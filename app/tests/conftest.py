"""Shared pytest fixtures."""
import os
import sys

import pytest

# Make "app.py" importable when pytest is run from the repository root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import app as notes_app  # noqa: E402


@pytest.fixture
def client():
    """A Flask test client with an empty notes store for every test."""
    notes_app.NOTES.clear()
    notes_app.app.config["TESTING"] = True
    with notes_app.app.test_client() as test_client:
        yield test_client
