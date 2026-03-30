export type ServiceMode = 'paper' | 'live';

export type PositionSide = 'YES' | 'NO';

export interface PricePoint {
  tsMs: number;
  price: number;
}

export interface DerivativesSnapshot {
  slopePerSecond: number;
  accelerationPerSecond2: number;
  volatilityPerSqrtSecond: number;
  sampleCount: number;
}

export interface MarketSnapshot {
  marketTicker: string;
  yesBidCents: number;
  yesAskCents: number;
  noBidCents: number;
  noAskCents: number;
  timeRemainingSec: number;
}

export interface PositionState {
  marketTicker: string;
  side: PositionSide;
  entryPriceCents: number;
  quantity: number;
  enteredAtMs: number;
}

export interface StrategyState {
  position: PositionState | null;
  lastCompletedTicker: string | null;
  marketRoundTripComplete: boolean;
}

export interface SignalContext {
  market: MarketSnapshot;
  derivatives: DerivativesSnapshot;
  state: StrategyState;
  unrealizedPnlDollars: number;
}

export type SignalAction = 'ENTER' | 'EXIT' | 'WAIT';

export interface SignalDecision {
  action: SignalAction;
  reason: string;
  side?: PositionSide;
}

export interface PaperOrderEvent {
  type: 'ENTER' | 'EXIT' | 'SKIP';
  marketTicker: string;
  side?: PositionSide;
  priceCents?: number;
  quantity?: number;
  pnlDollars?: number;
  reason: string;
}

export interface RuntimeCycleResult {
  ticker: string;
  market: MarketSnapshot;
  derivatives: DerivativesSnapshot;
  decision: SignalDecision;
  event: PaperOrderEvent;
}
