import { describe, expect, it } from 'vitest';
import { loadConfig } from '../src/config/env.js';
import { PaperOrderManager } from '../src/order/paperOrderManager.js';

const config = loadConfig({ SERVICE_MODE: 'paper', PAPER_DEFAULT_SIZE: '10' });

describe('PaperOrderManager', () => {
  it('opens then exits a paper YES position', () => {
    const manager = new PaperOrderManager(config);
    const market = {
      marketTicker: 'KXBTCD-TEST',
      yesAskCents: 60,
      noAskCents: 40,
      timeRemainingSec: 420
    };

    const enterEvent = manager.applyDecision({ action: 'ENTER', side: 'YES', reason: 'test entry' }, market, 0);
    expect(enterEvent.type).toBe('ENTER');
    expect(manager.getPosition()).not.toBeNull();

    const markUpMarket = { ...market, yesAskCents: 72 };
    expect(manager.computeUnrealizedPnl(markUpMarket)).toBeCloseTo(1.2);

    const exitEvent = manager.applyDecision({ action: 'TAKE_PROFIT', reason: 'hit target' }, markUpMarket, 1);
    expect(exitEvent.type).toBe('EXIT');
    expect(exitEvent.pnlDollars).toBeCloseTo(1.2);
    expect(manager.getPosition()).toBeNull();
  });
});
