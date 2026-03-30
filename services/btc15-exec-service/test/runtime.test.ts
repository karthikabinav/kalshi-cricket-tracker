import { describe, expect, it } from 'vitest';
import type { PriceFeedAdapter } from '../src/adapters/binanceFeed.js';
import type { KalshiAdapter } from '../src/adapters/kalshi.js';
import { loadConfig } from '../src/config/env.js';
import { Btc15Runtime } from '../src/runtime.js';
import type { MarketSnapshot, PricePoint } from '../src/types.js';

class StubFeed implements PriceFeedAdapter {
  private onPrice: ((point: PricePoint) => void) | null = null;

  async connect(onPrice: (point: PricePoint) => void): Promise<void> {
    this.onPrice = onPrice;
  }

  async disconnect(): Promise<void> {}

  push(point: PricePoint): void {
    this.onPrice?.(point);
  }
}

class MutableStubKalshi implements KalshiAdapter {
  constructor(public market: MarketSnapshot) {}

  async resolveActiveMarket(): Promise<string> {
    return this.market.marketTicker;
  }

  async getMarketSnapshot(): Promise<MarketSnapshot> {
    return this.market;
  }

  async placePaperOrder(): Promise<{ accepted: boolean; mode: 'paper' }> {
    return { accepted: true, mode: 'paper' };
  }
}

describe('Btc15Runtime', () => {
  it('waits for enough price samples before evaluating', async () => {
    const config = loadConfig({ SERVICE_MODE: 'paper', MIN_PRICE_SAMPLES: '3' });
    const feed = new StubFeed();
    const runtime = new Btc15Runtime(
      config,
      feed,
      new MutableStubKalshi({ marketTicker: 'KXBTCD-TEST', yesBidCents: 59, yesAskCents: 60, noBidCents: 39, noAskCents: 40, timeRemainingSec: 420 })
    );

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 101 });

    expect(await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'))).toBeNull();
  });

  it('evaluates a paper cycle with a YES entry when enough feed data exists', async () => {
    const config = loadConfig({ SERVICE_MODE: 'paper', MIN_PRICE_SAMPLES: '3', PAPER_DEFAULT_SIZE: '10' });
    const feed = new StubFeed();
    const kalshi = new MutableStubKalshi({ marketTicker: 'KXBTCD-TEST', yesBidCents: 57, yesAskCents: 58, noBidCents: 82, noAskCents: 83, timeRemainingSec: 420 });
    const runtime = new Btc15Runtime(config, feed, kalshi);

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 102 });
    feed.push({ tsMs: 2000, price: 105 });

    const result = await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'));
    expect(result).not.toBeNull();
    expect(result?.decision).toMatchObject({ action: 'ENTER', side: 'YES' });
    expect(result?.event).toMatchObject({ type: 'ENTER', side: 'YES', priceCents: 58 });
    expect(result?.derivatives.sampleCount).toBe(3);
  });

  it('blocks entries when the market is outside the explicit allowlist', async () => {
    const config = loadConfig({
      SERVICE_MODE: 'paper',
      MIN_PRICE_SAMPLES: '3',
      PAPER_DEFAULT_SIZE: '10',
      KALSHI_MARKET_ALLOWLIST: 'KXBTCD-ALLOWED'
    });
    const feed = new StubFeed();
    const kalshi = new MutableStubKalshi({ marketTicker: 'KXBTCD-BLOCKED', yesBidCents: 57, yesAskCents: 58, noBidCents: 82, noAskCents: 83, timeRemainingSec: 420 });
    const runtime = new Btc15Runtime(config, feed, kalshi);

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 102 });
    feed.push({ tsMs: 2000, price: 105 });

    const result = await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'));
    expect(result?.decision).toEqual({ action: 'WAIT', reason: 'market not in allowlist' });
    expect(result?.event.type).toBe('SKIP');
  });

  it('blocks new entries after realized loss breaches the daily cap', async () => {
    const config = loadConfig({
      SERVICE_MODE: 'paper',
      MIN_PRICE_SAMPLES: '3',
      PAPER_DEFAULT_SIZE: '100',
      MAX_ORDER_NOTIONAL_DOLLARS: '100',
      MAX_DAILY_LOSS_DOLLARS: '10',
      STOP_LOSS_DOLLARS: '15'
    });
    const feed = new StubFeed();
    const kalshi = new MutableStubKalshi({ marketTicker: 'KXBTCD-TEST', yesBidCents: 57, yesAskCents: 58, noBidCents: 82, noAskCents: 83, timeRemainingSec: 420 });
    const runtime = new Btc15Runtime(config, feed, kalshi);

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 102 });
    feed.push({ tsMs: 2000, price: 105 });

    const entry = await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'));
    expect(entry?.event.type).toBe('ENTER');

    kalshi.market = { ...kalshi.market, yesBidCents: 42, yesAskCents: 43 };
    const stop = await runtime.evaluateCycle(new Date('2026-03-29T04:00:01Z'));
    expect(stop?.decision).toEqual({ action: 'EXIT', reason: 'hard stop hit' });
    expect(runtime.getRealizedPnlDollars()).toBe(-16);

    kalshi.market = { ...kalshi.market, marketTicker: 'KXBTCD-NEXT', yesBidCents: 59, yesAskCents: 60 };
    const blocked = await runtime.evaluateCycle(new Date('2026-03-29T04:00:02Z'));
    expect(blocked?.decision).toEqual({ action: 'WAIT', reason: 'daily loss limit reached' });
    expect(blocked?.event.type).toBe('SKIP');
  });

  it('blocks re-entry after a completed round trip in the same market', async () => {
    const config = loadConfig({ SERVICE_MODE: 'paper', MIN_PRICE_SAMPLES: '3', PAPER_DEFAULT_SIZE: '10' });
    const feed = new StubFeed();
    const kalshi = new MutableStubKalshi({ marketTicker: 'KXBTCD-TEST', yesBidCents: 57, yesAskCents: 58, noBidCents: 82, noAskCents: 83, timeRemainingSec: 420 });
    const runtime = new Btc15Runtime(config, feed, kalshi);

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 102 });
    feed.push({ tsMs: 2000, price: 105 });

    const entry = await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'));
    expect(entry?.event.type).toBe('ENTER');

    kalshi.market = { ...kalshi.market, timeRemainingSec: 120 };
    const exit = await runtime.evaluateCycle(new Date('2026-03-29T04:02:00Z'));
    expect(exit?.event.type).toBe('EXIT');

    kalshi.market = { ...kalshi.market, timeRemainingSec: 420 };
    const reentry = await runtime.evaluateCycle(new Date('2026-03-29T04:03:00Z'));
    expect(reentry?.decision).toEqual({ action: 'WAIT', reason: 'round trip for this market already completed' });
    expect(reentry?.event.type).toBe('SKIP');
  });
});
