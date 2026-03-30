import type { AppConfig } from '../config/env.js';
import type { MarketSnapshot, PaperOrderEvent, StrategyState, SignalDecision } from '../types.js';

export class RuntimeRiskManager {
  private realizedPnlDollars = 0;

  constructor(private readonly config: AppConfig) {}

  getRealizedPnlDollars(): number {
    return this.realizedPnlDollars;
  }

  noteEvent(event: PaperOrderEvent): void {
    if (event.type === 'EXIT') {
      this.realizedPnlDollars += event.pnlDollars ?? 0;
    }
  }

  guardDecision(decision: SignalDecision, market: MarketSnapshot, state: StrategyState): SignalDecision {
    if (decision.action !== 'ENTER') {
      return decision;
    }

    if (this.config.safety.emergencyStop) {
      return { action: 'WAIT', reason: 'emergency stop enabled' };
    }

    if (this.config.safety.allowedTickers.length > 0 && !this.config.safety.allowedTickers.includes(market.marketTicker)) {
      return { action: 'WAIT', reason: 'market not in allowlist' };
    }

    const openPositionCount = state.position ? 1 : 0;
    if (openPositionCount >= this.config.safety.maxOpenPositions) {
      return { action: 'WAIT', reason: 'max open positions reached' };
    }

    const side = decision.side ?? 'YES';
    const entryPriceCents = side === 'YES' ? market.yesAskCents : market.noAskCents;
    const prospectiveNotional = (entryPriceCents / 100) * this.config.paperDefaultSize;
    if (prospectiveNotional > this.config.safety.maxOrderNotionalDollars) {
      return { action: 'WAIT', reason: 'order notional exceeds max cap' };
    }

    if (Math.max(0, -this.realizedPnlDollars) >= this.config.safety.maxDailyLossDollars) {
      return { action: 'WAIT', reason: 'daily loss limit reached' };
    }

    if (this.config.serviceMode === 'live' && !this.config.safety.liveTradingEnabled) {
      return { action: 'WAIT', reason: 'live trading not explicitly enabled' };
    }

    return decision;
  }
}
