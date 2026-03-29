import { config as loadDotenv } from 'dotenv';
import { z } from 'zod';
import type { ServiceMode } from '../types.js';

loadDotenv();

const envSchema = z.object({
  NODE_ENV: z.string().default('development'),
  SERVICE_MODE: z.enum(['paper', 'live']).default('paper'),
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
  KALSHI_ENV: z.string().default('demo'),
  KALSHI_MARKET_PREFIX: z.string().default('KXBTCD-'),
  PAPER_DEFAULT_SIZE: z.coerce.number().positive().default(10)
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
  kalshiEnv: string;
  kalshiMarketPrefix: string;
  paperDefaultSize: number;
};

export function loadConfig(source: NodeJS.ProcessEnv = process.env): AppConfig {
  const env = envSchema.parse(source);
  return {
    nodeEnv: env.NODE_ENV,
    serviceMode: env.SERVICE_MODE,
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
    kalshiEnv: env.KALSHI_ENV,
    kalshiMarketPrefix: env.KALSHI_MARKET_PREFIX,
    paperDefaultSize: env.PAPER_DEFAULT_SIZE
  };
}
