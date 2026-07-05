"""Shared fixtures for db-service tests."""

import pytest

from app.libs import signed_url_cache


@pytest.fixture(autouse=True)
def clear_signed_url_cache():
    signed_url_cache.clear_cache()
    yield
    signed_url_cache.clear_cache()
