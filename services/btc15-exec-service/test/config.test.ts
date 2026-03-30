import { describe, expect, it } from 'vitest';
import { assertLiveModeReady, LIVE_CONFIRMATION_PHRASE, loadConfig } from '../src/config/env.js';

describe('config safety gates', () => {
  it('defaults to safe paper mode', () => {
    const config = loadConfig({});
    expect(config.serviceMode).toBe('paper');
    expect(config.safety.liveTradingEnabled).toBe(false);
    expect(config.safety.emergencyStop).toBe(false);
  });

  it('supports MODE as the explicit service mode control', () => {
    const config = loadConfig({
      MODE: 'live',
      LIVE_TRADING_ENABLED: 'true',
      LIVE_CONFIRMATION_PHRASE: LIVE_CONFIRMATION_PHRASE,
      KALSHI_API_KEY_ID: 'kid',
      KALSHI_PRIVATE_KEY_PATH: '/tmp/key.pem',
      KALSHI_MARKET_ALLOWLIST: 'KXBTCD-1,KXBTCD-2'
    });
    expect(config.serviceMode).toBe('live');
    expect(config.safety.allowedTickers).toEqual(['KXBTCD-1', 'KXBTCD-2']);
  });

  it('rejects live mode without the extra safety gates', () => {
    const config = loadConfig({ MODE: 'live' });
    expect(() => assertLiveModeReady(config)).toThrow('SERVICE_MODE=live requires LIVE_TRADING_ENABLED=true');
  });

  it('rejects live mode without the exact confirmation phrase', () => {
    const config = loadConfig({
      MODE: 'live',
      LIVE_TRADING_ENABLED: 'true',
      LIVE_CONFIRMATION_PHRASE: 'wrong',
      KALSHI_API_KEY_ID: 'kid',
      KALSHI_PRIVATE_KEY_PATH: '/tmp/key.pem',
      KALSHI_MARKET_ALLOWLIST: 'KXBTCD-1'
    });
    expect(() => assertLiveModeReady(config)).toThrow(
      'SERVICE_MODE=live requires LIVE_CONFIRMATION_PHRASE to match the exact risk acknowledgement string'
    );
  });

  it('rejects live mode when emergency stop is set', () => {
    const config = loadConfig({
      MODE: 'live',
      LIVE_TRADING_ENABLED: 'true',
      LIVE_CONFIRMATION_PHRASE: LIVE_CONFIRMATION_PHRASE,
      EMERGENCY_STOP: 'true',
      KALSHI_API_KEY_ID: 'kid',
      KALSHI_PRIVATE_KEY_PATH: '/tmp/key.pem',
      KALSHI_MARKET_ALLOWLIST: 'KXBTCD-1'
    });
    expect(() => assertLiveModeReady(config)).toThrow('SERVICE_MODE=live blocked while EMERGENCY_STOP=true');
  });

  it('accepts fully armed live mode only with the explicit confirmation phrase', () => {
    const config = loadConfig({
      MODE: 'live',
      LIVE_TRADING_ENABLED: 'true',
      LIVE_CONFIRMATION_PHRASE: LIVE_CONFIRMATION_PHRASE,
      KALSHI_API_KEY_ID: 'kid',
      KALSHI_PRIVATE_KEY_PATH: '/tmp/key.pem',
      KALSHI_MARKET_ALLOWLIST: 'KXBTCD-1'
    });
    expect(() => assertLiveModeReady(config)).not.toThrow();
  });
});
