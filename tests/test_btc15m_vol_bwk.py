from kalshi_cricket_tracker.strategy.btc15m_vol_bwk import FeeSchedule, Position, VolBanditsWithKnapsackPolicy, VolSnapshot


def make_snapshot(**overrides):
    base = dict(
        yes_bid_cents=46,
        yes_ask_cents=47,
        no_bid_cents=53,
        no_ask_cents=54,
        spread_cents=1,
        depth_contracts=120,
        time_remaining_min=8.0,
        distance_from_target_cents=-3.0,
        microprice_cents=49.0,
        orderbook_imbalance=-0.2,
        recent_trade_buy_ratio=0.35,
        realized_vol_bps=65.0,
        local_mean_reversion_zscore=-1.4,
    )
    base.update(overrides)
    return VolSnapshot(**base)


def test_fee_schedule_matches_spec_mappings():
    fees = FeeSchedule(maker_fee_bps=10.0, taker_fee_bps=20.0)
    assert round(fees.buy_cost(ask_cents=47, qty=2), 4) == 94.094
    assert round(fees.sell_cost(bid_cents=49, qty=2), 4) == -97.804
    assert round(fees.sell_reward(entry_cents=47, bid_cents=49, qty=2), 4) == 3.71
    assert round(fees.round_trip_friction(entry_cents=47, exit_cents=49, qty=2), 4) == 0.29


def test_state_machine_exposes_spec_actions():
    policy = VolBanditsWithKnapsackPolicy(FeeSchedule())
    assert policy.feasible_actions(Position(state="FLAT")) == (
        "buy_yes_15",
        "buy_yes_8",
        "hold",
        "buy_no_8",
        "buy_no_15",
    )
    assert policy.feasible_actions(Position(state="LONG_YES", qty=1, entry_cents=47)) == ("sell_yes", "hold_position")
    assert policy.feasible_actions(Position(state="LONG_NO", qty=1, entry_cents=54)) == ("sell_no", "hold_position")


def test_negative_cost_sell_recycles_budget_and_flattens_position():
    policy = VolBanditsWithKnapsackPolicy(FeeSchedule())
    snap = make_snapshot(yes_bid_cents=50, yes_ask_cents=51)
    evaluation = policy.evaluate_action(
        position=Position(state="LONG_YES", qty=2, entry_cents=47),
        snapshot=snap,
        action="sell_yes",
        lambda_cost=0.1,
    )
    assert evaluation.cost < 0
    assert evaluation.reward > 0
    assert evaluation.next_state == "FLAT"


def test_choose_action_prefers_buy_on_yes_dip_when_flat():
    policy = VolBanditsWithKnapsackPolicy(FeeSchedule())
    chosen = policy.choose_action(
        position=Position(state="FLAT"),
        snapshot=make_snapshot(),
        lambda_cost=0.02,
        budget_remaining=100.0,
        expected_recovery_cents=1.5,
    )
    assert chosen.action in {"buy_yes_8", "buy_yes_15"}
    assert chosen.next_state == "LONG_YES"


def test_mark_to_market_works_for_long_no():
    policy = VolBanditsWithKnapsackPolicy(FeeSchedule())
    snap = make_snapshot(no_bid_cents=57)
    mtm = policy.mark_to_market(Position(state="LONG_NO", qty=3, entry_cents=54), snap)
    assert mtm == 9
