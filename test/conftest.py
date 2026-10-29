"""Keep experimental configuration in one test from affecting later measurements."""

import os

import pytest


@pytest.fixture(autouse=True)
def isolated_environment():
    original = dict(os.environ)
    try:
        yield
    finally:
        os.environ.clear()
        os.environ.update(original)
