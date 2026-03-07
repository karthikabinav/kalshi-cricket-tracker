from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import pandas as pd
import requests

from kalshi_cricket_tracker.config import WinProbConfig


class WinProbAdapter(Protocol):
    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        """Return columns: event_id, external_prob_team1, prob_source"""


@dataclass
class EloOnlyWinProbAdapter:
    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        return pd.DataFrame(columns=["event_id", "external_prob_team1", "prob_source"])


@dataclass
class CsvWinProbAdapter:
    csv_path: str

    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        p = Path(self.csv_path)
        if not p.exists():
            raise FileNotFoundError(f"Win-prob CSV not found: {p}")
        df = pd.read_csv(p)
        required = {"event_id", "external_prob_team1"}
        missing = required - set(df.columns)
        if missing:
            raise ValueError(f"Win-prob CSV missing required columns: {sorted(missing)}")
        out = fixtures[["event_id"]].merge(df[["event_id", "external_prob_team1"]], on="event_id", how="left")
        out["prob_source"] = "csv"
        return out


@dataclass
class CricinfoWinProbAdapter:
    endpoint_template: str
    timeout_s: int = 12

    def _extract_prob(self, payload: dict, team_name: str) -> float | None:
        # Generic parser across common Cricinfo payload patterns.
        candidates: list[tuple[str, float]] = []

        def walk(node):
            if isinstance(node, dict):
                name = node.get("teamName") or node.get("name") or node.get("shortName")
                for key in ("winProbability", "winningProbability", "probability", "winChance"):
                    if key in node and isinstance(node[key], (int, float)):
                        val = float(node[key])
                        if val > 1:
                            val = val / 100.0
                        if name:
                            candidates.append((str(name), val))
                for v in node.values():
                    walk(v)
            elif isinstance(node, list):
                for it in node:
                    walk(it)

        walk(payload)
        if not candidates:
            return None

        tn = str(team_name).strip().lower()
        for n, p in candidates:
            if n.strip().lower() == tn:
                return float(min(max(p, 0.0), 1.0))
        # fuzzy fallback
        for n, p in candidates:
            if tn in n.lower() or n.lower() in tn:
                return float(min(max(p, 0.0), 1.0))
        return None

    def fetch_probabilities(self, fixtures: pd.DataFrame) -> pd.DataFrame:
        if fixtures.empty:
            return pd.DataFrame(columns=["event_id", "external_prob_team1", "prob_source"])

        rows = []
        for _, fx in fixtures.iterrows():
            event_id = str(fx.get("event_id", ""))
            team1 = str(fx.get("team1", "")).strip()
            if not event_id or not team1:
                rows.append({"event_id": event_id, "external_prob_team1": None, "prob_source": "cricinfo"})
                continue

            url = self.endpoint_template.format(event_id=event_id)
            try:
                r = requests.get(url, timeout=self.timeout_s)
                r.raise_for_status()
                payload = r.json()
                prob = self._extract_prob(payload, team1)
            except Exception:
                prob = None

            rows.append({"event_id": event_id, "external_prob_team1": prob, "prob_source": "cricinfo"})

        return pd.DataFrame(rows)


def create_winprob_adapter(cfg: WinProbConfig) -> WinProbAdapter:
    if cfg.provider == "elo_only":
        return EloOnlyWinProbAdapter()
    if cfg.provider == "csv":
        if not cfg.csv_path:
            raise ValueError("winprob.csv_path must be set when winprob.provider=csv")
        return CsvWinProbAdapter(csv_path=cfg.csv_path)
    if cfg.provider == "cricinfo":
        if not cfg.cricinfo_endpoint_template:
            raise ValueError("winprob.cricinfo_endpoint_template must be set when winprob.provider=cricinfo")
        return CricinfoWinProbAdapter(
            endpoint_template=cfg.cricinfo_endpoint_template,
            timeout_s=cfg.cricinfo_timeout_s,
        )
    raise ValueError(f"Unsupported winprob provider: {cfg.provider}")
