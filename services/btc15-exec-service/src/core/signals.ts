import type { AppConfig } from '../config/env.js';
import type { PositionSide, SignalContext, SignalDecision } from '../types.js';

function manualEntryBand(config: AppConfig): { low: number; high: number } {
  const configuredSpan = Math.max(0, config.bandExitCents - config.manualEntryCents);
  const halfWidth = Math.floor(configuredSpan / 2);
  return {
    low: Math.max(0, config.manualEntryCents - halfWidth),
    high: Math.min(99, config.manualEntryCents + halfWidth)
  };
}

function intendedYesPrice(side: PositionSide, askCents: number): number {
  return side === 'YES' ? askCents : 100 - askCents;
}

function btcTrendBlocksEntry(side: PositionSide, context: SignalContext, config: AppConfig): boolean {
  if (!config.btcTrendFilterEnabled) {
    return false;
  }

  const { slopePerSecond, accelerationPerSecond2 } = context.derivatives;
  const againstYes =
    side === 'YES' &&
    slopePerSecond >= config.btcSpotSlopeThreshold &&
    accelerationPerSecond2 >= config.btcSpotAccelerationThreshold;
  const againstNo =
    side === 'NO' &&
    slopePerSecond <= -config.btcSpotSlopeThreshold &&
    accelerationPerSecond2 <= -config.btcSpotAccelerationThreshold;

  return againstYes || againstNo;
}

export function evaluateSignal(context: SignalContext, config: AppConfig): SignalDecision {
  const { market, state, unrealizedPnlDollars } = context;
  const position = state.position;

  if (!position && state.marketRoundTripComplete && state.lastCompletedTicker === market.marketTicker) {
    return { action: 'WAIT', reason: 'round trip for this market already completed' };
  }

  if (position) {
    if (market.timeRemainingSec <= config.forceExitRemainingSec) {
      return { action: 'EXIT', reason: 'forced time exit at 3-minute cutoff' };
    }

    if (unrealizedPnlDollars >= config.manualProfitTargetDollars) {
      return { action: 'EXIT', reason: 'manual profit target reached' };
    }

    if (unrealizedPnlDollars <= -config.stopLossDollars) {
      return { action: 'EXIT', reason: 'hard stop hit' };
    }

    return { action: 'WAIT', reason: 'manual hold: waiting for profit target, hard stop, or 3-minute forced exit' };
  }

  if (market.timeRemainingSec <= config.forceExitRemainingSec) {
    return { action: 'WAIT', reason: 'no new entries in exit window' };
  }

  const band = manualEntryBand(config);
  const candidates: Array<{ side: PositionSide; askCents: number; intendedYes: number; distance: number }> = [];

  for (const [side, askCents] of [
    ['YES', market.yesAskCents],
    ['NO', market.noAskCents]
  ] as const) {
    const intendedYes = intendedYesPrice(side, askCents);
    if (intendedYes >= band.low && intendedYes <= band.high) {
      candidates.push({
        side,
        askCents,
        intendedYes,
        distance: Math.abs(config.manualEntryCents - intendedYes)
      });
    }
  }

  if (candidates.length === 0) {
    return {
      action: 'WAIT',
      reason: `manual state machine idle: no side offered inside the ${band.low}c-${band.high}c intended YES-price entry band`
    };
  }

  candidates.sort((a, b) => a.distance - b.distance || (a.side === 'YES' ? -1 : 1));
  const chosen = candidates[0]!;

  if (btcTrendBlocksEntry(chosen.side, context, config)) {
    return {
      action: 'WAIT',
      reason: `BTC trend filter blocked ${chosen.side}: slope ${context.derivatives.slopePerSecond.toFixed(2)} and acceleration ${context.derivatives.accelerationPerSecond2.toFixed(2)} still move against the mean-reversion entry`
    };
  }

  return {
    action: 'ENTER',
    side: chosen.side,
    reason: `manual entry: buy ${chosen.side} at ${chosen.askCents}c (intended YES price ${chosen.intendedYes}c) near ${config.manualEntryCents}c`
  };
}
