import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config/env.js';
import { PaperOrderManager } from '../src/order/paperOrderManager.js';

const config = loadConfig({ SERVICE_MODE: 'paper', PAPER_DEFAULT_SIZE: '10' });

describe('PaperOrderManager', () => {
  it('opens then exits a paper YES position using bid-side marks', () => {
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
    expect(enterEvent.type).toBe('ENTER');
    expect(manager.getPosition()).not.toBeNull();

    const markUpMarket = { ...market, yesBidCents: 72, yesAskCents: 73 };
    expect(manager.computeUnrealizedPnl(markUpMarket)).toBeCloseTo(1.2);

    const exitEvent = manager.applyDecision({ action: 'TAKE_PROFIT', reason: 'hit target' }, markUpMarket, 1);
    expect(exitEvent.type).toBe('EXIT');
    expect(exitEvent.priceCents).toBe(72);
    expect(exitEvent.pnlDollars).toBeCloseTo(1.2);
    expect(manager.getPosition()).toBeNull();
  });

  it('exits on stop-loss using the same bid-side pricing path as the manual paper flow', () => {
    const manager = new PaperOrderManager(loadConfig({ SERVICE_MODE: 'paper', PAPER_DEFAULT_SIZE: '100' }));
    const market = {
      marketTicker: 'KXBTCD-TEST',
      yesBidCents: 59,
      yesAskCents: 60,
      noBidCents: 39,
      noAskCents: 40,
      timeRemainingSec: 420
    };

    manager.applyDecision({ action: 'ENTER', side: 'YES', reason: 'test entry' }, market, 0);

    const stopMarket = { ...market, yesBidCents: 44, yesAskCents: 45 };
    const exitEvent = manager.applyDecision({ action: 'STOP_LOSS', reason: 'stop-loss reached' }, stopMarket, 1);

    expect(exitEvent).toMatchObject({
      type: 'EXIT',
      side: 'YES',
      priceCents: 44,
      pnlDollars: -16,
      reason: 'stop-loss reached'
    });
    expect(manager.getPosition()).toBeNull();
  });
});
