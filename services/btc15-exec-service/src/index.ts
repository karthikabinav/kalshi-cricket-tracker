import { loadConfig } from './config/env.js';
import { BinanceBtcFeedAdapter } from './adapters/binanceFeed.js';
import { PaperKalshiAdapter } from './adapters/kalshi.js';
import { PriceBuffer, computeDerivatives } from './core/derivatives.js';
import { evaluateSignal } from './core/signals.js';
import { PaperOrderManager } from './order/paperOrderManager.js';

export async function bootstrap(): Promise<void> {
  const config = loadConfig();
  const priceBuffer = new PriceBuffer(config.priceBufferSize);
  const priceFeed = new BinanceBtcFeedAdapter(config.binanceSymbol);
  const kalshi = new PaperKalshiAdapter(config.kalshiMarketPrefix);
  const orders = new PaperOrderManager(config);

  await priceFeed.connect((point) => priceBuffer.push(point));

  const ticker = await kalshi.resolveActiveMarket(new Date());
  const market = await kalshi.getMarketSnapshot(ticker);
  const derivatives = computeDerivatives(priceBuffer.snapshot(), {
    slopeLookbackSec: config.slopeLookbackSec,
    accelLookbackSec: config.accelLookbackSec,
    volLookbackSec: config.volLookbackSec
  });

  const decision = evaluateSignal(
    {
      market,
      derivatives,
      position: orders.getPosition(),
      unrealizedPnlDollars: orders.computeUnrealizedPnl(market)
    },
    config
  );

  const event = orders.applyDecision(decision, market);
  console.log(JSON.stringify({ component: 'bootstrap', serviceMode: config.serviceMode, ticker, decision, event }));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  bootstrap().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
