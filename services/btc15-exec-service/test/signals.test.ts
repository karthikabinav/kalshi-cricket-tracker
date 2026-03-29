import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config/env.js';
import { evaluateSignal } from '../src/core/signals.js';
import type { SignalContext } from '../src/types.js';

const config = loadConfig({
  SERVICE_MODE: 'paper',
  ENTRY_PRICE_MIN_CENTS: '58',
  ENTRY_PRICE_MAX_CENTS: '65',
  TAKE_PROFIT_DOLLARS: '10',
  STOP_LOSS_DOLLARS: '15',
  FORCE_EXIT_REMAINING_SEC: '180',
  PAPER_DEFAULT_SIZE: '10'
});

function baseContext(): SignalContext {
  return {
    market: {
      marketTicker: 'KXBTCD-TEST',
      yesBidCents: 59,
      yesAskCents: 60,
      noBidCents: 39,
      noAskCents: 40,
      timeRemainingSec: 420
    },
    derivatives: {
      slopePerSecond: 1,
      accelerationPerSecond2: 0.2,
      volatilityPerSqrtSecond: 0.5,
      sampleCount: 10
    },
    position: null,
    unrealizedPnlDollars: 0
  };
}

describe('evaluateSignal', () => {
  it('enters when price band and momentum gates pass', () => {
    const decision = evaluateSignal(baseContext(), config);
    expect(decision).toEqual({ action: 'ENTER', side: 'YES', reason: 'price band + positive slope/accel' });
  });

  it('forces exit before close when a position is open', () => {
    const context = baseContext();
    context.market.timeRemainingSec = 120;
    context.position = {
      marketTicker: 'KXBTCD-TEST',
      side: 'YES',
      entryPriceCents: 60,
      quantity: 10,
      enteredAtMs: 0
    };
    const decision = evaluateSignal(context, config);
    expect(decision.action).toBe('FORCE_EXIT');
  });

  it('takes stop-loss before waiting when unrealized PnL breaches the hard floor', () => {
    const context = baseContext();
    context.position = {
      marketTicker: 'KXBTCD-TEST',
      side: 'YES',
      entryPriceCents: 60,
      quantity: 100,
      enteredAtMs: 0
    };
    context.unrealizedPnlDollars = -16;

    const decision = evaluateSignal(context, config);

    expect(decision).toEqual({ action: 'STOP_LOSS', reason: 'stop-loss reached' });
  });

  it('returns caution when price band is met without momentum confirmation', () => {
    const context = baseContext();
    context.derivatives.slopePerSecond = -0.1;
    const decision = evaluateSignal(context, config);
    expect(decision.action).toBe('CAUTION');
  });
});
