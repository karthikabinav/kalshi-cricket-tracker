import type { AppConfig } from '../config/env.js';
import type { MarketSnapshot } from '../types.js';

export interface OrderPlacementParams {
  ticker: string;
  side: 'YES' | 'NO';
  priceCents: number;
  quantity: number;
}

export interface OrderPlacementResult {
  accepted: boolean;
  mode: 'paper' | 'live';
  orderId?: string;
}

export interface KalshiAdapter {
  resolveActiveMarket(now: Date): Promise<string>;
  getMarketSnapshot(ticker: string): Promise<MarketSnapshot>;
  placeOrder(params: OrderPlacementParams): Promise<OrderPlacementResult>;
}

export interface KalshiLiveClient {
  resolveActiveMarket(now: Date): Promise<string>;
  getMarketSnapshot(ticker: string): Promise<MarketSnapshot>;
  placeOrder(params: OrderPlacementParams): Promise<OrderPlacementResult>;
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

  async placeOrder(_params: OrderPlacementParams): Promise<OrderPlacementResult> {
    return { accepted: true, mode: 'paper' };
  }
}

export class UnimplementedKalshiLiveClient implements KalshiLiveClient {
  constructor(private readonly config: AppConfig) {}

  async resolveActiveMarket(_now: Date): Promise<string> {
    throw new Error(`Kalshi live market discovery not implemented for ${this.config.kalshiApiBaseUrl}`);
  }

  async getMarketSnapshot(ticker: string): Promise<MarketSnapshot> {
    throw new Error(`Kalshi live orderbook snapshot not implemented for ${ticker}`);
  }

  async placeOrder(params: OrderPlacementParams): Promise<OrderPlacementResult> {
    throw new Error(`Kalshi live order placement not implemented for ${params.ticker}`);
  }
}

export class LiveKalshiAdapter implements KalshiAdapter {
  constructor(private readonly client: KalshiLiveClient) {}

  async resolveActiveMarket(now: Date): Promise<string> {
    return this.client.resolveActiveMarket(now);
  }

  async getMarketSnapshot(ticker: string): Promise<MarketSnapshot> {
    return this.client.getMarketSnapshot(ticker);
  }

  async placeOrder(params: OrderPlacementParams): Promise<OrderPlacementResult> {
    return this.client.placeOrder(params);
  }
}
