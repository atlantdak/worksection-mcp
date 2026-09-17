from __future__ import annotations

import httpx

from worksection_mcp.http.params import normalize_params


def test_none_values_are_dropped() -> None:
    assert normalize_params({"a": "1", "b": None}) == {"a": "1"}


def test_booleans_become_one_and_zero() -> None:
    assert normalize_params({"yes": True, "no": False}) == {"yes": "1", "no": "0"}


def test_sequences_are_comma_joined() -> None:
    assert normalize_params({"ids": [1, 2, 3]}) == {"ids": "1,2,3"}


def test_numbers_are_stringified() -> None:
    assert normalize_params({"limit": 25}) == {"limit": "25"}


def test_none_argument_yields_an_empty_mapping() -> None:
    assert normalize_params(None) == {}


def test_hostile_values_survive_round_trip_encoded_by_httpx() -> None:
    params = normalize_params({"title": "a&b=c d?e#f", "text": "100% done"})
    request = httpx.Request("GET", "https://example.test/api/", params=params)
    assert "a%26b%3Dc" in str(request.url)
    assert request.url.params["title"] == "a&b=c d?e#f"
    assert request.url.params["text"] == "100% done"
