from __future__ import annotations

import math

import pandas as pd


def _expected(r1: float, r2: float) -> float:
    return 1.0 / (1.0 + 10 ** ((r2 - r1) / 400))


def build_team_ratings(matches: pd.DataFrame, k: float = 20.0) -> tuple[pd.DataFrame, dict[str, float]]:
    ratings: dict[str, float] = {}
    rows = []

    for _, row in matches.sort_values("date").iterrows():
        t1, t2, winner = row["team1"], row["team2"], row["winner"]
        r1, r2 = ratings.get(t1, 1500.0), ratings.get(t2, 1500.0)
        p1 = _expected(r1, r2)
        s1 = 1.0 if winner == t1 else 0.0 if winner == t2 else 0.5
        s2 = 1.0 - s1
        nr1 = r1 + k * (s1 - p1)
        nr2 = r2 + k * (s2 - (1 - p1))
        ratings[t1], ratings[t2] = nr1, nr2
        rows.append(
            {
                "date": row["date"],
                "match_id": row["match_id"],
                "team1": t1,
                "team2": t2,
                "winner": winner,
                "team1_pre_elo": r1,
                "team2_pre_elo": r2,
                "team1_win_prob_pre": p1,
                "team1_post_elo": nr1,
                "team2_post_elo": nr2,
            }
        )

    return pd.DataFrame(rows), ratings


def add_recent_form(matches: pd.DataFrame, window: int = 5) -> pd.DataFrame:
    out = matches.copy()
    out = out.sort_values("date")
    for team_col in ["team1", "team2"]:
        form_col = f"{team_col}_form"
        vals = []
        history: dict[str, list[int]] = {}
        for _, row in out.iterrows():
            team = row[team_col]
            winner = row["winner"]
            h = history.get(team, [])
            vals.append(sum(h[-window:]) / max(1, len(h[-window:])))
            result = 1 if winner == team else 0
            history.setdefault(team, []).append(result)
        out[form_col] = vals
    return out


def implied_prob_from_elo(team_a_elo: float, team_b_elo: float, home_advantage_elo: float = 0.0) -> float:
    return 1.0 / (1.0 + math.pow(10, ((team_b_elo - (team_a_elo + home_advantage_elo)) / 400)))
