# Contextual Bandit Strategy (Risk-Aware, Budget-Constrained)

## Objective
Given daily budget \(B\), choose bet/no-bet and stake \(a_t \in \mathcal{A}\) to maximize risk-adjusted return.

## Context Features
For match \(t\):
- \(p_t\): model win probability for team1 from Elo
- \(m_t\): proxy market probability
- edge: \(e_t = p_t - m_t\)
- recent form team1/team2
- Elo differential

Feature vector: \(x_t \in \mathbb{R}^d\).

## Action Space
Discrete stake arms:
\[
\mathcal{A} = \{0, 25, 50, 100, 150, 250\}\text{ USD}
\]
- \(a_t=0\): no bet.
- if \(a_t>0\): place BUY_YES if \(p_t\ge0.5\), else BUY_NO.

## Budget Constraint
Per day budget \(B\). For decision at time \(t\), feasible set:
\[
\mathcal{A}_t = \{a\in\mathcal{A}: a \le B_t^{rem}\}
\]
with \(B_{t+1}^{rem}=B_t^{rem}-a_t\).

## Risk Penalty
PnL for executed trade: \(\pi_t\).
Risk-adjusted reward:
\[
r_t = \pi_t - \lambda \pi_t^2
\]
where \(\lambda\ge0\) is mean-variance proxy risk aversion (CVaR proxy can be substituted).

## Online Update Rule (LinUCB per arm)
For each arm \(a\):
- Parameters \(A_a \in \mathbb{R}^{d\times d}\), \(b_a \in \mathbb{R}^{d}\)
- \(\theta_a=A_a^{-1}b_a\)
- Score:
\[
\hat U(x,a)=x^\top\theta_a + \alpha\sqrt{x^\top A_a^{-1}x}
\]
Choose feasible arm with max score.

After observing reward \(r_t\) for chosen arm \(a_t\):
\[
A_{a_t}\leftarrow A_{a_t}+x_tx_t^\top,
\quad
b_{a_t}\leftarrow b_{a_t}+r_tx_t
\]

## Assumptions
1. Binary contract payoff approximated as +stake/-stake minus fees.
2. Proxy market probabilities used when live Kalshi cricket contracts are unavailable.
3. Historical data quality depends on public source coverage.
4. This is research/paper-trading only, not live execution advice.
