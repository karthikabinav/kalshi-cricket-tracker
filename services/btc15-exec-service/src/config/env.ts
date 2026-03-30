import { config as loadDotenv } from 'dotenv';
import { z } from 'zod';
import type { ServiceMode } from '../types.js';

loadDotenv();

const envSchema = z.object({
  NODE_ENV: z.string().default('development'),
  SERVICE_MODE: z.enum(['paper', 'live']).optional(),
  MODE: z.enum(['paper', 'live']).optional(),
  LOG_LEVEL: z.string().default('info'),
  HEALTH_PORT: z.coerce.number().int().positive().default(3000),
  BINANCE_SYMBOL: z.string().default('btcusdt'),
  PRICE_BUFFER_SIZE: z.coerce.number().int().min(10).default(60),
  SLOPE_LOOKBACK_SEC: z.coerce.number().positive().default(10),
  ACCEL_LOOKBACK_SEC: z.coerce.number().positive().default(5),
  VOL_LOOKBACK_SEC: z.coerce.number().positive().default(30),
  ENTRY_PRICE_MIN_CENTS: z.coerce.number().min(1).max(99).default(58),
  ENTRY_PRICE_MAX_CENTS: z.coerce.number().min(1).max(99).default(65),
  TAKE_PROFIT_DOLLARS: z.coerce.number().positive().default(10),
  STOP_LOSS_DOLLARS: z.coerce.number().positive().default(15),
  FORCE_EXIT_REMAINING_SEC: z.coerce.number().int().positive().default(180),
  MANUAL_ENTRY_CENTS: z.coerce.number().min(1).max(99).default(60),
  BAND_EXIT_CENTS: z.coerce.number().min(1).max(99).default(80),
  MANUAL_PROFIT_TARGET_DOLLARS: z.coerce.number().positive().default(10),
  STOP_LOSS_CENTS: z.coerce.number().positive().default(3),
  BTC_TREND_FILTER_ENABLED: z.coerce.boolean().default(true),
  BTC_SPOT_SLOPE_THRESHOLD: z.coerce.number().positive().default(25),
  BTC_SPOT_ACCELERATION_THRESHOLD: z.coerce.number().positive().default(10),
  LIVE_TRADING_ENABLED: z.coerce.boolean().default(false),
  EMERGENCY_STOP: z.coerce.boolean().default(false),
  KALSHI_API_KEY_ID: z.string().optional(),
  KALSHI_PRIVATE_KEY_PATH: z.string().optional(),
  KALSHI_API_BASE_URL: z.string().default('https://api.elections.kalshi.com/trade-api/v2'),
  KALSHI_MARKET_ALLOWLIST: z.string().optional(),
  KALSHI_ENV: z.string().default('demo'),
  KALSHI_MARKET_PREFIX: z.string().default('KXBTCD-'),
  PAPER_DEFAULT_SIZE: z.coerce.number().positive().default(10),
  MAX_ORDER_NOTIONAL_DOLLARS: z.coerce.number().positive().default(25),
  MAX_DAILY_LOSS_DOLLARS: z.coerce.number().positive().default(25),
  MAX_OPEN_POSITIONS: z.coerce.number().int().positive().default(1),
  EVAL_INTERVAL_MS: z.coerce.number().int().positive().default(1000),
  MIN_PRICE_SAMPLES: z.coerce.number().int().positive().default(5),
  BINANCE_RECONNECT_BASE_MS: z.coerce.number().int().positive().default(1000),
  BINANCE_RECONNECT_MAX_MS: z.coerce.number().int().positive().default(15000),
  BINANCE_STALE_THRESHOLD_MS: z.coerce.number().int().positive().default(20000)
});

export type AppConfig = {
  nodeEnv: string;
  serviceMode: ServiceMode;
  logLevel: string;
  healthPort: number;
  binanceSymbol: string;
  priceBufferSize: number;
  slopeLookbackSec: number;
  accelLookbackSec: number;
  volLookbackSec: number;
  entryPriceMinCents: number;
  entryPriceMaxCents: number;
  takeProfitDollars: number;
  stopLossDollars: number;
  forceExitRemainingSec: number;
  manualEntryCents: number;
  bandExitCents: number;
  manualProfitTargetDollars: number;
  stopLossCents: number;
  btcTrendFilterEnabled: boolean;
  btcSpotSlopeThreshold: number;
  btcSpotAccelerationThreshold: number;
  kalshiEnv: string;
  kalshiApiBaseUrl: string;
  kalshiMarketPrefix: string;
  paperDefaultSize: number;
  evalIntervalMs: number;
  minPriceSamples: number;
  binanceReconnectBaseMs: number;
  binanceReconnectMaxMs: number;
  binanceStaleThresholdMs: number;
  safety: {
    liveTradingEnabled: boolean;
    emergencyStop: boolean;
    apiKeyId?: string;
    privateKeyPath?: string;
    allowedTickers: string[];
    maxOrderNotionalDollars: number;
    maxDailyLossDollars: number;
    maxOpenPositions: number;
  };
};

export function loadConfig(source: NodeJS.ProcessEnv = process.env): AppConfig {
  const env = envSchema.parse(source);
  const serviceMode = (env.MODE ?? env.SERVICE_MODE ?? 'paper') as ServiceMode;
  return {
    nodeEnv: env.NODE_ENV,
    serviceMode,
    logLevel: env.LOG_LEVEL,
    healthPort: env.HEALTH_PORT,
    binanceSymbol: env.BINANCE_SYMBOL,
    priceBufferSize: env.PRICE_BUFFER_SIZE,
    slopeLookbackSec: env.SLOPE_LOOKBACK_SEC,
    accelLookbackSec: env.ACCEL_LOOKBACK_SEC,
    volLookbackSec: env.VOL_LOOKBACK_SEC,
    entryPriceMinCents: env.ENTRY_PRICE_MIN_CENTS,
    entryPriceMaxCents: env.ENTRY_PRICE_MAX_CENTS,
    takeProfitDollars: env.TAKE_PROFIT_DOLLARS,
    stopLossDollars: env.STOP_LOSS_DOLLARS,
    forceExitRemainingSec: env.FORCE_EXIT_REMAINING_SEC,
    manualEntryCents: env.MANUAL_ENTRY_CENTS,
    bandExitCents: env.BAND_EXIT_CENTS,
    manualProfitTargetDollars: env.MANUAL_PROFIT_TARGET_DOLLARS,
    stopLossCents: env.STOP_LOSS_CENTS,
    btcTrendFilterEnabled: env.BTC_TREND_FILTER_ENABLED,
    btcSpotSlopeThreshold: env.BTC_SPOT_SLOPE_THRESHOLD,
    btcSpotAccelerationThreshold: env.BTC_SPOT_ACCELERATION_THRESHOLD,
    kalshiEnv: env.KALSHI_ENV,
    kalshiApiBaseUrl: env.KALSHI_API_BASE_URL,
    kalshiMarketPrefix: env.KALSHI_MARKET_PREFIX,
    paperDefaultSize: env.PAPER_DEFAULT_SIZE,
    evalIntervalMs: env.EVAL_INTERVAL_MS,
    minPriceSamples: env.MIN_PRICE_SAMPLES,
    binanceReconnectBaseMs: env.BINANCE_RECONNECT_BASE_MS,
    binanceReconnectMaxMs: env.BINANCE_RECONNECT_MAX_MS,
    binanceStaleThresholdMs: env.BINANCE_STALE_THRESHOLD_MS,
    safety: {
      liveTradingEnabled: env.LIVE_TRADING_ENABLED,
      emergencyStop: env.EMERGENCY_STOP,
      apiKeyId: env.KALSHI_API_KEY_ID,
      privateKeyPath: env.KALSHI_PRIVATE_KEY_PATH,
      allowedTickers: (env.KALSHI_MARKET_ALLOWLIST ?? '')
        .split(',')
        .map((value) => value.trim())
        .filter(Boolean),
      maxOrderNotionalDollars: env.MAX_ORDER_NOTIONAL_DOLLARS,
      maxDailyLossDollars: env.MAX_DAILY_LOSS_DOLLARS,
      maxOpenPositions: env.MAX_OPEN_POSITIONS
    }
  };
}

export function assertLiveModeReady(config: AppConfig): void {
  if (config.serviceMode !== 'live') {
    return;
  }
  if (!config.safety.liveTradingEnabled) {
    throw new Error('SERVICE_MODE=live requires LIVE_TRADING_ENABLED=true');
  }
  if (config.safety.emergencyStop) {
    throw new Error('SERVICE_MODE=live blocked while EMERGENCY_STOP=true');
  }
  if (!config.safety.apiKeyId || !config.safety.privateKeyPath || config.safety.allowedTickers.length === 0) {
    throw new Error('SERVICE_MODE=live requires Kalshi credentials and KALSHI_MARKET_ALLOWLIST');
  }
}
