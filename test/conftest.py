"""Keep environment changes in one test from changing later security decisions."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch):
    # Persistence tests opt in explicitly. Give them a synthetic journal key;
    # missing-key tests still remove it explicitly to exercise fail-closed paths.
    original = dict(os.environ)
    monkeypatch.setenv("JUNAS_JOURNAL_KEY", "synthetic-pytest-journal-key")
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)
