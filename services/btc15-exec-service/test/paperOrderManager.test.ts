import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config/env.js';
import { PaperOrderManager } from '../src/order/paperOrderManager.js';

const config = loadConfig({ SERVICE_MODE: 'paper', PAPER_DEFAULT_SIZE: '10' });

describe('PaperOrderManager', () => {
  it('opens then exits a paper YES position using ask-in / bid-out pricing', () => {
    const manager = new PaperOrderManager(config);
    const market = {
      marketTicker: 'KXBTCD-TEST',
      yesBidCents: 59,
      yesAskCents: 60,
      noBidCents: 39,
      noAskCents: 40,
      timeRemainingSec: 420
    };

    const enterEvent = manager.applyDecision({ action: 'ENTER', side: 'YES', reason: 'test entry' }, market, 0);
    expect(enterEvent).toMatchObject({ type: 'ENTER', side: 'YES', priceCents: 60, quantity: 10 });
    expect(manager.getPosition()).not.toBeNull();

    const markUpMarket = { ...market, yesBidCents: 72, yesAskCents: 73 };
    expect(manager.computeUnrealizedPnl(markUpMarket)).toBeCloseTo(1.2);

    const exitEvent = manager.applyDecision({ action: 'EXIT', reason: 'manual profit target reached' }, markUpMarket, 1);
    expect(exitEvent).toMatchObject({
      type: 'EXIT',
      side: 'YES',
      priceCents: 72,
      pnlDollars: 1.2,
      reason: 'manual profit target reached'
    });
    expect(manager.getPosition()).toBeNull();
  });

  it('supports NO-side entries using no ask for entry and no bid for exit', () => {
    const manager = new PaperOrderManager(loadConfig({ SERVICE_MODE: 'paper', PAPER_DEFAULT_SIZE: '100' }));
    const market = {
      marketTicker: 'KXBTCD-TEST',
      yesBidCents: 10,
      yesAskCents: 11,
      noBidCents: 89,
      noAskCents: 90,
      timeRemainingSec: 420
    };

    manager.applyDecision({ action: 'ENTER', side: 'NO', reason: 'test NO entry' }, market, 0);

    const profitMarket = { ...market, noBidCents: 96, noAskCents: 97 };
    const exitEvent = manager.applyDecision({ action: 'EXIT', reason: 'manual profit target reached' }, profitMarket, 1);

    expect(exitEvent).toMatchObject({
      type: 'EXIT',
      side: 'NO',
      priceCents: 96,
      pnlDollars: 6,
      reason: 'manual profit target reached'
    });
    expect(manager.getPosition()).toBeNull();
  });

  it('marks the market as complete after a round trip to prevent same-market re-entry', () => {
    const manager = new PaperOrderManager(config);
    const market = {
      marketTicker: 'KXBTCD-TEST',
      yesBidCents: 59,
      yesAskCents: 60,
      noBidCents: 39,
      noAskCents: 40,
      timeRemainingSec: 420
    };

    manager.applyDecision({ action: 'ENTER', side: 'YES', reason: 'test entry' }, market, 0);
    manager.applyDecision({ action: 'EXIT', reason: 'forced time exit at 3-minute cutoff' }, market, 1);

    expect(manager.getState()).toEqual({
      position: null,
      lastCompletedTicker: 'KXBTCD-TEST',
      marketRoundTripComplete: true
    });
  });
});
