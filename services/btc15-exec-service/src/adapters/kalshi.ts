import type { MarketSnapshot } from '../types.js';

export interface KalshiAdapter {
  resolveActiveMarket(now: Date): Promise<string>;
  getMarketSnapshot(ticker: string): Promise<MarketSnapshot>;
  placePaperOrder(params: { ticker: string; side: 'YES' | 'NO'; priceCents: number; quantity: number }): Promise<{ accepted: boolean; mode: 'paper' }>;
}

export class PaperKalshiAdapter implements KalshiAdapter {
  constructor(private readonly marketPrefix: string) {}

  async resolveActiveMarket(now: Date): Promise<string> {
    const isoMinute = now.toISOString().slice(0, 16).replace(/[-:T]/g, '');
    return `${this.marketPrefix}${isoMinute}`;
  }

  async getMarketSnapshot(ticker: string): Promise<MarketSnapshot> {
    return {
      marketTicker: ticker,
      yesBidCents: 59,
      yesAskCents: 60,
      noBidCents: 39,
      noAskCents: 40,
      timeRemainingSec: 420
    };
  }

  async placePaperOrder(_params: { ticker: string; side: 'YES' | 'NO'; priceCents: number; quantity: number }): Promise<{ accepted: boolean; mode: 'paper' }> {
    return { accepted: true, mode: 'paper' };
  }
}
