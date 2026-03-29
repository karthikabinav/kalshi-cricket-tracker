import type { PricePoint } from '../types.js';

export interface PriceFeedAdapter {
  connect(onPrice: (point: PricePoint) => void): Promise<void>;
  disconnect(): Promise<void>;
}

export class BinanceBtcFeedAdapter implements PriceFeedAdapter {
  constructor(private readonly symbol: string) {}

  async connect(_onPrice: (point: PricePoint) => void): Promise<void> {
    console.log(JSON.stringify({ component: 'binance-feed', symbol: this.symbol, mode: 'stub', msg: 'connect not implemented yet' }));
  }

  async disconnect(): Promise<void> {
    console.log(JSON.stringify({ component: 'binance-feed', symbol: this.symbol, mode: 'stub', msg: 'disconnect noop' }));
  }
}
