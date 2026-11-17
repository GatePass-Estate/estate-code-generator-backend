import pytest

from app.pipeline.data_wrangler import wrangle_visit_records


@pytest.mark.asyncio
async def test_drops_null_empty_and_whitespace_strings():
    raw = [
        {"a": 1, "b": None, "c": "", "d": "  "},
        {"a": None, "e": "ok"},
        {},
    ]
    out = await wrangle_visit_records(raw)
    assert out[0] == {"a": 1}
    assert out[1] == {"e": "ok"}
    assert out[2] == {}


@pytest.mark.asyncio
async def test_empty_input():
    assert await wrangle_visit_records([]) == []
