import type { AppConfig } from '../config/env.js';
import type { MarketSnapshot, PaperOrderEvent, PositionState, SignalDecision, StrategyState } from '../types.js';

export class PaperOrderManager {
  private state: StrategyState = {
    position: null,
    lastCompletedTicker: null,
    marketRoundTripComplete: false
  };

  constructor(private readonly config: AppConfig) {}

  getPosition(): PositionState | null {
    return this.state.position;
  }

  getState(): StrategyState {
    return {
      position: this.state.position ? { ...this.state.position } : null,
      lastCompletedTicker: this.state.lastCompletedTicker,
      marketRoundTripComplete: this.state.marketRoundTripComplete
    };
  }

  private getEntryPrice(side: PositionState['side'], market: MarketSnapshot): number {
    return side === 'YES' ? market.yesAskCents : market.noAskCents;
  }

  private getExitPrice(side: PositionState['side'], market: MarketSnapshot): number {
    return side === 'YES' ? market.yesBidCents : market.noBidCents;
  }

  computeUnrealizedPnl(market: MarketSnapshot): number {
    if (!this.state.position) {
      return 0;
    }
    const markCents = this.getExitPrice(this.state.position.side, market);
    return ((markCents - this.state.position.entryPriceCents) * this.state.position.quantity) / 100;
  }

  applyDecision(decision: SignalDecision, market: MarketSnapshot, nowMs = Date.now()): PaperOrderEvent {
    if (decision.action === 'ENTER' && decision.side && !this.state.position) {
      this.state.position = {
        marketTicker: market.marketTicker,
        side: decision.side,
        entryPriceCents: this.getEntryPrice(decision.side, market),
        quantity: this.config.paperDefaultSize,
        enteredAtMs: nowMs
      };
      if (this.state.lastCompletedTicker !== market.marketTicker) {
        this.state.marketRoundTripComplete = false;
      }
      return {
        type: 'ENTER',
        marketTicker: market.marketTicker,
        side: decision.side,
        priceCents: this.state.position.entryPriceCents,
        quantity: this.state.position.quantity,
        reason: decision.reason
      };
    }

    if (decision.action === 'EXIT' && this.state.position) {
      const exitPriceCents = this.getExitPrice(this.state.position.side, market);
      const pnlDollars = this.computeUnrealizedPnl(market);
      const event: PaperOrderEvent = {
        type: 'EXIT',
        marketTicker: market.marketTicker,
        side: this.state.position.side,
        priceCents: exitPriceCents,
        quantity: this.state.position.quantity,
        pnlDollars,
        reason: decision.reason
      };
      this.state.position = null;
      this.state.lastCompletedTicker = market.marketTicker;
      this.state.marketRoundTripComplete = true;
      return event;
    }

    return {
      type: 'SKIP',
      marketTicker: market.marketTicker,
      reason: decision.reason
    };
  }
}
