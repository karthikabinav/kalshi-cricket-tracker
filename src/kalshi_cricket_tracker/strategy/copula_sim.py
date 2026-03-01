from __future__ import annotations

import numpy as np


def _cholesky_psd(corr: np.ndarray) -> np.ndarray:
    # small jitter for numerical stability
    eye = np.eye(corr.shape[0])
    for eps in [0.0, 1e-8, 1e-6, 1e-4]:
        try:
            return np.linalg.cholesky(corr + eps * eye)
        except np.linalg.LinAlgError:
            continue
    raise ValueError("Correlation matrix not PSD")


def simulate_independent_outcomes(probs: list[float], n: int = 100_000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    p = np.asarray(probs, dtype=float)
    u = rng.random((n, len(p)))
    return (u < p[None, :]).astype(np.int8)


def simulate_gaussian_outcomes(probs: list[float], corr: np.ndarray, n: int = 100_000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = len(probs)
    l = _cholesky_psd(corr)
    z = rng.standard_normal((n, d)) @ l.T
    # empirical quantile threshold per marginal (avoids scipy dependency)
    p = np.asarray(probs, dtype=float)
    q = np.array([np.quantile(z[:, j], p[j]) for j in range(d)], dtype=float)
    return (z < q[None, :]).astype(np.int8)


def simulate_t_outcomes(probs: list[float], corr: np.ndarray, nu: float = 4.0, n: int = 100_000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    d = len(probs)
    l = _cholesky_psd(corr)
    z = rng.standard_normal((n, d)) @ l.T
    s = rng.chisquare(df=nu, size=n) / nu
    t = z / np.sqrt(s[:, None])
    p = np.asarray(probs, dtype=float)
    q = np.array([np.quantile(t[:, j], p[j]) for j in range(d)], dtype=float)
    return (t < q[None, :]).astype(np.int8)


def simulate_clayton_outcomes(probs: list[float], theta: float = 2.0, n: int = 100_000, seed: int = 42) -> np.ndarray:
    rng = np.random.default_rng(seed)
    p = np.asarray(probs, dtype=float)
    d = len(p)
    v = rng.gamma(shape=1.0 / theta, scale=1.0, size=n)
    e = rng.exponential(scale=1.0, size=(n, d))
    u = (1.0 + e / v[:, None]) ** (-1.0 / theta)
    return (u < p[None, :]).astype(np.int8)


def joint_tail_metrics(outcomes: np.ndarray) -> dict[str, float]:
    all_win = outcomes.all(axis=1).mean()
    all_lose = (1 - outcomes).all(axis=1).mean()
    return {"p_all_win": float(all_win), "p_all_lose": float(all_lose)}


def equicorr_matrix(d: int, rho: float) -> np.ndarray:
    m = np.full((d, d), rho, dtype=float)
    np.fill_diagonal(m, 1.0)
    return m
