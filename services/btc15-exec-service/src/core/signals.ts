import type { AppConfig } from '../config/env.js';
import type { SignalContext, SignalDecision } from '../types.js';

export function evaluateSignal(context: SignalContext, config: AppConfig): SignalDecision {
  const { market, derivatives, position, unrealizedPnlDollars } = context;

  if (position && market.timeRemainingSec <= config.forceExitRemainingSec) {
    return { action: 'FORCE_EXIT', reason: 'time stop reached' };
  }

  if (position && unrealizedPnlDollars >= config.takeProfitDollars) {
    return { action: 'TAKE_PROFIT', reason: 'take-profit reached' };
  }

  if (position && unrealizedPnlDollars <= -config.stopLossDollars) {
    return { action: 'STOP_LOSS', reason: 'stop-loss reached' };
  }

  if (position) {
    return { action: 'WAIT', reason: 'position open; monitoring' };
  }

  if (market.timeRemainingSec <= config.forceExitRemainingSec) {
    return { action: 'WAIT', reason: 'no new entries in exit window' };
  }

  const inEntryRange =
    market.yesAskCents >= config.entryPriceMinCents &&
    market.yesAskCents <= config.entryPriceMaxCents;

  if (!inEntryRange) {
    return { action: 'WAIT', reason: 'price outside entry band' };
  }

  if (derivatives.slopePerSecond > 0 && derivatives.accelerationPerSecond2 >= 0) {
    return { action: 'ENTER', side: 'YES', reason: 'price band + positive slope/accel' };
  }

  return { action: 'CAUTION', reason: 'price band met but momentum confirmation missing' };
}
