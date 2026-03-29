import type { AppConfig } from '../config/env.js';
import type { MarketSnapshot, PaperOrderEvent, PositionState, SignalDecision } from '../types.js';

export class PaperOrderManager {
  private position: PositionState | null = null;

  constructor(private readonly config: AppConfig) {}

  getPosition(): PositionState | null {
    return this.position;
  }

  private getEntryPrice(side: PositionState['side'], market: MarketSnapshot): number {
    return side === 'YES' ? market.yesAskCents : market.noAskCents;
  }

  private getExitPrice(side: PositionState['side'], market: MarketSnapshot): number {
    return side === 'YES' ? market.yesBidCents : market.noBidCents;
  }

  computeUnrealizedPnl(market: MarketSnapshot): number {
    if (!this.position) {
      return 0;
    }
    const markCents = this.getExitPrice(this.position.side, market);
    return ((markCents - this.position.entryPriceCents) * this.position.quantity) / 100;
  }

  applyDecision(decision: SignalDecision, market: MarketSnapshot, nowMs = Date.now()): PaperOrderEvent {
    if (decision.action === 'ENTER' && decision.side && !this.position) {
      this.position = {
        marketTicker: market.marketTicker,
        side: decision.side,
        entryPriceCents: this.getEntryPrice(decision.side, market),
        quantity: this.config.paperDefaultSize,
        enteredAtMs: nowMs
      };
      return {
        type: 'ENTER',
        marketTicker: market.marketTicker,
        side: decision.side,
        priceCents: this.position.entryPriceCents,
        quantity: this.position.quantity,
        reason: decision.reason
      };
    }

    if (['FORCE_EXIT', 'TAKE_PROFIT', 'STOP_LOSS'].includes(decision.action) && this.position) {
      const exitPriceCents = this.getExitPrice(this.position.side, market);
      const pnlDollars = this.computeUnrealizedPnl(market);
      const event: PaperOrderEvent = {
        type: 'EXIT',
        marketTicker: market.marketTicker,
        side: this.position.side,
        priceCents: exitPriceCents,
        quantity: this.position.quantity,
        pnlDollars,
        reason: decision.reason
      };
      this.position = null;
      return event;
    }

    return {
      type: 'SKIP',
      marketTicker: market.marketTicker,
      reason: decision.reason
    };
  }
}
