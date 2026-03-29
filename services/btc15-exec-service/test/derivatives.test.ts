import { describe, expect, it } from 'vitest';
import { computeDerivatives } from '../src/core/derivatives.js';
import type { PricePoint } from '../src/types.js';

describe('computeDerivatives', () => {
  it('computes positive slope and non-zero volatility on rising prices', () => {
    const points: PricePoint[] = [
      { tsMs: 0, price: 100 },
      { tsMs: 1000, price: 101 },
      { tsMs: 2000, price: 103 },
      { tsMs: 3000, price: 106 }
    ];

    const snapshot = computeDerivatives(points, {
      slopeLookbackSec: 10,
      accelLookbackSec: 3,
      volLookbackSec: 10
    });

    expect(snapshot.slopePerSecond).toBeCloseTo(2);
    expect(snapshot.accelerationPerSecond2).toBeGreaterThanOrEqual(0);
    expect(snapshot.volatilityPerSqrtSecond).toBeGreaterThan(0);
  });
});
