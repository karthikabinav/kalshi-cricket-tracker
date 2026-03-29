import type { DerivativesSnapshot, PricePoint } from '../types.js';

export class PriceBuffer {
  private readonly points: PricePoint[] = [];

  constructor(private readonly maxSize: number) {}

  push(point: PricePoint): void {
    this.points.push(point);
    if (this.points.length > this.maxSize) {
      this.points.shift();
    }
  }

  snapshot(): PricePoint[] {
    return [...this.points];
  }
}

function toWindow(points: PricePoint[], lookbackSec: number): PricePoint[] {
  if (points.length === 0) {
    return [];
  }
  const endTs = points[points.length - 1]!.tsMs;
  const floorTs = endTs - lookbackSec * 1000;
  return points.filter((point) => point.tsMs >= floorTs);
}

function slope(points: PricePoint[]): number {
  if (points.length < 2) {
    return 0;
  }
  const first = points[0]!;
  const last = points[points.length - 1]!;
  const dtSec = (last.tsMs - first.tsMs) / 1000;
  if (dtSec <= 0) {
    return 0;
  }
  return (last.price - first.price) / dtSec;
}

function volatility(points: PricePoint[]): number {
  if (points.length < 2) {
    return 0;
  }

  const returns: number[] = [];
  for (let i = 1; i < points.length; i += 1) {
    const prev = points[i - 1]!;
    const cur = points[i]!;
    const dtSec = (cur.tsMs - prev.tsMs) / 1000;
    if (dtSec <= 0) continue;
    returns.push((cur.price - prev.price) / Math.sqrt(dtSec));
  }

  if (returns.length === 0) {
    return 0;
  }

  const mean = returns.reduce((sum, value) => sum + value, 0) / returns.length;
  const variance = returns.reduce((sum, value) => sum + (value - mean) ** 2, 0) / returns.length;
  return Math.sqrt(variance);
}

export function computeDerivatives(
  points: PricePoint[],
  params: { slopeLookbackSec: number; accelLookbackSec: number; volLookbackSec: number }
): DerivativesSnapshot {
  const slopeWindow = toWindow(points, params.slopeLookbackSec);
  const accelWindow = toWindow(points, params.accelLookbackSec);
  const volWindow = toWindow(points, params.volLookbackSec);

  const currentSlope = slope(slopeWindow);
  const previousSlope = slope(accelWindow.slice(0, -1));
  const acceleration = accelWindow.length >= 2 ? currentSlope - previousSlope : 0;

  return {
    slopePerSecond: currentSlope,
    accelerationPerSecond2: acceleration,
    volatilityPerSqrtSecond: volatility(volWindow),
    sampleCount: points.length
  };
}
