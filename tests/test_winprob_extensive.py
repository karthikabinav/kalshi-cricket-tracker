from __future__ import annotations

import pandas as pd

from kalshi_cricket_tracker.config import WinProbConfig
from kalshi_cricket_tracker.winprob import CricinfoWinProbAdapter, create_winprob_adapter


class _Resp:
    def __init__(self, payload: dict, status_code: int = 200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    def json(self):
        return self._payload


def test_create_adapter_validation_errors():
    try:
        create_winprob_adapter(WinProbConfig(provider="csv", csv_path=None))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "csv_path" in str(exc)

    try:
        create_winprob_adapter(WinProbConfig(provider="cricinfo", cricinfo_endpoint_template=None))
        raise AssertionError("expected ValueError")
    except ValueError as exc:
        assert "cricinfo_endpoint_template" in str(exc)


def test_cricinfo_extract_prob_direct_team_name():
    adapter = CricinfoWinProbAdapter("https://example/{event_id}")
    payload = {
        "competitors": [
            {"teamName": "India", "winProbability": 61.2},
            {"teamName": "Australia", "winProbability": 38.8},
        ]
    }
    p = adapter._extract_prob(payload, "India")
    assert p is not None
    assert abs(p - 0.612) < 1e-9


def test_cricinfo_extract_prob_nested_and_fuzzy():
    adapter = CricinfoWinProbAdapter("https://example/{event_id}")
    payload = {
        "x": {
            "nodes": [
                {"name": "India Women", "probability": 0.57},
                {"name": "Australia Women", "probability": 0.43},
            ]
        }
    }
    p = adapter._extract_prob(payload, "India")
    assert p is not None
    assert abs(p - 0.57) < 1e-9


def test_cricinfo_fetch_probabilities_success(monkeypatch):
    adapter = CricinfoWinProbAdapter("https://example/{event_id}")

    def fake_get(url, timeout):
        assert "m1" in url
        return _Resp({"competitors": [{"teamName": "India", "winChance": 0.63}]})

    import kalshi_cricket_tracker.winprob as wp

    monkeypatch.setattr(wp.requests, "get", fake_get)

    fixtures = pd.DataFrame([{"event_id": "m1", "team1": "India"}])
    out = adapter.fetch_probabilities(fixtures)
    assert len(out) == 1
    assert out.iloc[0]["prob_source"] == "cricinfo"
    assert abs(float(out.iloc[0]["external_prob_team1"]) - 0.63) < 1e-9


def test_cricinfo_fetch_probabilities_http_error(monkeypatch):
    adapter = CricinfoWinProbAdapter("https://example/{event_id}")

    def fake_get(url, timeout):
        return _Resp({}, status_code=500)

    import kalshi_cricket_tracker.winprob as wp

    monkeypatch.setattr(wp.requests, "get", fake_get)
    fixtures = pd.DataFrame([{"event_id": "m1", "team1": "India"}])
    out = adapter.fetch_probabilities(fixtures)
    assert out.iloc[0]["external_prob_team1"] is None or pd.isna(out.iloc[0]["external_prob_team1"])


def test_cricinfo_fetch_probabilities_missing_event_or_team():
    adapter = CricinfoWinProbAdapter("https://example/{event_id}")
    fixtures = pd.DataFrame([{"event_id": "", "team1": "India"}, {"event_id": "m2", "team1": ""}])
    out = adapter.fetch_probabilities(fixtures)
    assert len(out) == 2
    assert out["prob_source"].eq("cricinfo").all()
