import { describe, expect, it, vi } from 'vitest';
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

class StubKalshi implements KalshiAdapter {
  constructor(private readonly market: MarketSnapshot) {}

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
      new StubKalshi({ marketTicker: 'KXBTCD-TEST', yesAskCents: 60, noAskCents: 40, timeRemainingSec: 420 })
    );

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 101 });

    expect(await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'))).toBeNull();
  });

  it('evaluates a paper cycle once enough feed data exists', async () => {
    const config = loadConfig({ SERVICE_MODE: 'paper', MIN_PRICE_SAMPLES: '3', PAPER_DEFAULT_SIZE: '10' });
    const feed = new StubFeed();
    const kalshi = new StubKalshi({ marketTicker: 'KXBTCD-TEST', yesAskCents: 60, noAskCents: 40, timeRemainingSec: 420 });
    const runtime = new Btc15Runtime(config, feed, kalshi);

    await runtime.start();
    feed.push({ tsMs: 0, price: 100 });
    feed.push({ tsMs: 1000, price: 102 });
    feed.push({ tsMs: 2000, price: 105 });

    const result = await runtime.evaluateCycle(new Date('2026-03-29T04:00:00Z'));
    expect(result).not.toBeNull();
    expect(result?.decision.action).toBe('ENTER');
    expect(result?.event.type).toBe('ENTER');
    expect(result?.derivatives.sampleCount).toBe(3);
  });
});
