import { describe, expect, it } from 'vitest';
import { assertLiveModeReady, loadConfig } from '../src/config/env.js';

describe('config safety gates', () => {
  it('defaults to safe paper mode', () => {
    const config = loadConfig({});
    expect(config.serviceMode).toBe('paper');
    expect(config.safety.liveTradingEnabled).toBe(false);
    expect(config.safety.emergencyStop).toBe(false);
  });

  it('supports MODE as the explicit service mode control', () => {
    const config = loadConfig({ MODE: 'live', LIVE_TRADING_ENABLED: 'true', KALSHI_API_KEY_ID: 'kid', KALSHI_PRIVATE_KEY_PATH: '/tmp/key.pem', KALSHI_MARKET_ALLOWLIST: 'KXBTCD-1,KXBTCD-2' });
    expect(config.serviceMode).toBe('live');
    expect(config.safety.allowedTickers).toEqual(['KXBTCD-1', 'KXBTCD-2']);
  });

  it('rejects live mode without the extra safety gates', () => {
    const config = loadConfig({ MODE: 'live' });
    expect(() => assertLiveModeReady(config)).toThrow('SERVICE_MODE=live requires LIVE_TRADING_ENABLED=true');
  });

  it('rejects live mode when emergency stop is set', () => {
    const config = loadConfig({
      MODE: 'live',
      LIVE_TRADING_ENABLED: 'true',
      EMERGENCY_STOP: 'true',
      KALSHI_API_KEY_ID: 'kid',
      KALSHI_PRIVATE_KEY_PATH: '/tmp/key.pem',
      KALSHI_MARKET_ALLOWLIST: 'KXBTCD-1'
    });
    expect(() => assertLiveModeReady(config)).toThrow('SERVICE_MODE=live blocked while EMERGENCY_STOP=true');
  });
});
