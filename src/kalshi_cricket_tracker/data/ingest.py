from __future__ import annotations

import io
import json
import zipfile
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
import requests


@dataclass
class MatchRecord:
    match_id: str
    date: str
    team1: str
    team2: str
    winner: str | None
    venue: str | None
    city: str | None
    match_type: str | None


class CricSheetIngestor:
    """Loads historical cricket match outcomes from Cricsheet JSON zip."""

    def __init__(self, url: str, cache_dir: str | Path = "artifacts/raw"):
        self.url = url
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def download_zip(self, force: bool = False) -> Path:
        target = self.cache_dir / Path(self.url).name
        if target.exists() and not force:
            return target
        r = requests.get(self.url, timeout=90)
        r.raise_for_status()
        target.write_bytes(r.content)
        return target

    def parse_matches(self, zip_path: str | Path, limit: int | None = None) -> pd.DataFrame:
        rows: list[dict] = []
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = [n for n in zf.namelist() if n.endswith(".json")]
            if limit:
                names = names[-limit:]
            for name in names:
                with zf.open(name) as fh:
                    payload = json.load(io.TextIOWrapper(fh, encoding="utf-8"))
                info = payload.get("info", {})
                teams = info.get("teams", [None, None])
                outcome = info.get("outcome", {})
                winner = outcome.get("winner")
                dates = info.get("dates", [])
                date = dates[0] if dates else None
                rows.append(
                    {
                        "match_id": Path(name).stem,
                        "date": str(date) if date else None,
                        "team1": teams[0] if len(teams) > 0 else None,
                        "team2": teams[1] if len(teams) > 1 else None,
                        "winner": winner,
                        "venue": info.get("venue"),
                        "city": info.get("city"),
                        "match_type": info.get("match_type"),
                    }
                )

        df = pd.DataFrame(rows)
        if not df.empty:
            df["date"] = pd.to_datetime(df["date"], errors="coerce")
            df = df.dropna(subset=["date", "team1", "team2"]).sort_values("date")
        return df


class FixtureIngestor:
    """Fetches upcoming fixtures from ESPN public scoreboard endpoint (best-effort)."""

    def __init__(self, fixtures_url: str):
        self.fixtures_url = fixtures_url

    def fetch(self, limit: int = 20) -> pd.DataFrame:
        try:
            r = requests.get(self.fixtures_url, timeout=30)
            r.raise_for_status()
            data = r.json()
        except Exception:
            return pd.DataFrame(columns=["date", "team1", "team2", "venue", "competition", "event_id"])

        events = data.get("events", [])
        rows = []
        for ev in events[:limit]:
            comps = ev.get("competitions", [])
            if not comps:
                continue
            comp = comps[0]
            competitors = comp.get("competitors", [])
            if len(competitors) < 2:
                continue
            rows.append(
                {
                    "date": pd.to_datetime(ev.get("date"), errors="coerce"),
                    "team1": competitors[0].get("team", {}).get("displayName"),
                    "team2": competitors[1].get("team", {}).get("displayName"),
                    "venue": comp.get("venue", {}).get("fullName"),
                    "competition": ev.get("shortName"),
                    "event_id": ev.get("id"),
                }
            )
        return pd.DataFrame(rows).dropna(subset=["date", "team1", "team2"]) if rows else pd.DataFrame(
            columns=["date", "team1", "team2", "venue", "competition", "event_id"]
        )
