import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config/env.js';
import { evaluateSignal } from '../src/core/signals.js';
import type { SignalContext } from '../src/types.js';

const config = loadConfig({
  SERVICE_MODE: 'paper',
  MANUAL_ENTRY_CENTS: '60',
  BAND_EXIT_CENTS: '80',
  MANUAL_PROFIT_TARGET_DOLLARS: '10',
  STOP_LOSS_DOLLARS: '15',
  STOP_LOSS_CENTS: '3',
  FORCE_EXIT_REMAINING_SEC: '180',
  PAPER_DEFAULT_SIZE: '100',
  BTC_SPOT_SLOPE_THRESHOLD: '25',
  BTC_SPOT_ACCELERATION_THRESHOLD: '10'
});

function baseContext(): SignalContext {
  return {
    market: {
      marketTicker: 'KXBTCD-TEST',
      yesBidCents: 57,
      yesAskCents: 58,
      noBidCents: 82,
      noAskCents: 83,
      timeRemainingSec: 420
    },
    derivatives: {
      slopePerSecond: 1,
      accelerationPerSecond2: 0.2,
      volatilityPerSqrtSecond: 0.5,
      sampleCount: 10
    },
    state: {
      position: null,
      lastCompletedTicker: null,
      marketRoundTripComplete: false
    },
    unrealizedPnlDollars: 0
  };
}

describe('evaluateSignal', () => {
  it('prefers the side closest to the intended YES-price entry band', () => {
    const decision = evaluateSignal(baseContext(), config);
    expect(decision).toEqual({
      action: 'ENTER',
      side: 'YES',
      reason: 'manual entry: buy YES at 58c (intended YES price 58c) near 60c'
    });
  });

  it('uses YES-equivalent pricing for NO entries', () => {
    const context = baseContext();
    context.market = {
      ...context.market,
      yesBidCents: 43,
      yesAskCents: 44,
      noBidCents: 43,
      noAskCents: 44
    };

    const decision = evaluateSignal(context, config);
    expect(decision).toEqual({
      action: 'ENTER',
      side: 'NO',
      reason: 'manual entry: buy NO at 44c (intended YES price 56c) near 60c'
    });
  });

  it('blocks entries outside the configured intended YES-price band', () => {
    const context = baseContext();
    context.market = {
      ...context.market,
      yesBidCents: 1,
      yesAskCents: 1,
      noBidCents: 99,
      noAskCents: 99
    };

    const decision = evaluateSignal(context, config);
    expect(decision.action).toBe('WAIT');
    expect(decision.reason).toContain('entry band');
  });

  it('blocks re-entry after a completed round trip on the same market', () => {
    const context = baseContext();
    context.state.lastCompletedTicker = 'KXBTCD-TEST';
    context.state.marketRoundTripComplete = true;

    const decision = evaluateSignal(context, config);
    expect(decision).toEqual({ action: 'WAIT', reason: 'round trip for this market already completed' });
  });

  it('blocks YES entries when BTC slope/acceleration still move against the mean-reversion entry', () => {
    const context = baseContext();
    context.derivatives.slopePerSecond = 30;
    context.derivatives.accelerationPerSecond2 = 12;

    const decision = evaluateSignal(context, config);
    expect(decision.action).toBe('WAIT');
    expect(decision.reason).toContain('BTC trend filter blocked YES');
  });

  it('forces time exit before close when a position is open', () => {
    const context = baseContext();
    context.market.timeRemainingSec = 120;
    context.state.position = {
      marketTicker: 'KXBTCD-TEST',
      side: 'NO',
      entryPriceCents: 60,
      quantity: 100,
      enteredAtMs: 0
    };

    const decision = evaluateSignal(context, config);
    expect(decision).toEqual({ action: 'EXIT', reason: 'forced time exit at 3-minute cutoff' });
  });

  it('exits when unrealized PnL reaches the manual profit target', () => {
    const context = baseContext();
    context.state.position = {
      marketTicker: 'KXBTCD-TEST',
      side: 'NO',
      entryPriceCents: 15,
      quantity: 100,
      enteredAtMs: 0
    };
    context.unrealizedPnlDollars = 75;

    const decision = evaluateSignal(context, config);
    expect(decision).toEqual({ action: 'EXIT', reason: 'manual profit target reached' });
  });

  it('exits when unrealized PnL breaches the hard stop', () => {
    const context = baseContext();
    context.state.position = {
      marketTicker: 'KXBTCD-TEST',
      side: 'YES',
      entryPriceCents: 60,
      quantity: 100,
      enteredAtMs: 0
    };
    context.unrealizedPnlDollars = -16;

    const decision = evaluateSignal(context, config);
    expect(decision).toEqual({ action: 'EXIT', reason: 'hard stop hit' });
  });
});
