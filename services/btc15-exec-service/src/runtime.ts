import type { AppConfig } from './config/env.js';
import type { PriceFeedAdapter } from './adapters/binanceFeed.js';
import type { KalshiAdapter } from './adapters/kalshi.js';
import { PriceBuffer, computeDerivatives } from './core/derivatives.js';
import { RuntimeRiskManager } from './core/risk.js';
import { evaluateSignal } from './core/signals.js';
import { PaperOrderManager } from './order/paperOrderManager.js';
import type { RuntimeCycleResult } from './types.js';

export class Btc15Runtime {
  private readonly priceBuffer: PriceBuffer;
  private readonly orders: PaperOrderManager;
  private readonly risk: RuntimeRiskManager;

  constructor(
    private readonly config: AppConfig,
    private readonly priceFeed: PriceFeedAdapter,
    private readonly kalshi: KalshiAdapter,
    paperOrderManager?: PaperOrderManager,
    riskManager?: RuntimeRiskManager
  ) {
    this.priceBuffer = new PriceBuffer(config.priceBufferSize);
    this.orders = paperOrderManager ?? new PaperOrderManager(config);
    this.risk = riskManager ?? new RuntimeRiskManager(config);
  }

  async start(): Promise<void> {
    await this.priceFeed.connect((point) => {
      this.priceBuffer.push(point);
    });
  }

  async stop(): Promise<void> {
    await this.priceFeed.disconnect();
  }

  getSampleCount(): number {
    return this.priceBuffer.snapshot().length;
  }

  getRealizedPnlDollars(): number {
    return this.risk.getRealizedPnlDollars();
  }

  async evaluateCycle(now = new Date()): Promise<RuntimeCycleResult | null> {
    const points = this.priceBuffer.snapshot();
    if (points.length < this.config.minPriceSamples) {
      return null;
    }

    const ticker = await this.kalshi.resolveActiveMarket(now);
    const market = await this.kalshi.getMarketSnapshot(ticker);
    const derivatives = computeDerivatives(points, {
      slopeLookbackSec: this.config.slopeLookbackSec,
      accelLookbackSec: this.config.accelLookbackSec,
      volLookbackSec: this.config.volLookbackSec
    });
    const state = this.orders.getState();
    const decision = this.risk.guardDecision(
      evaluateSignal(
        {
          market,
          derivatives,
          state,
          unrealizedPnlDollars: this.orders.computeUnrealizedPnl(market)
        },
        this.config
      ),
      market,
      state
    );
    const event = this.orders.applyDecision(decision, market, now.getTime());
    this.risk.noteEvent(event);

    return { ticker, market, derivatives, decision, event };
  }
}
