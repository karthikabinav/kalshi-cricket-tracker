import { BinanceBtcFeedAdapter } from './adapters/binanceFeed.js';
import { LiveKalshiAdapter, PaperKalshiAdapter, UnimplementedKalshiLiveClient } from './adapters/kalshi.js';
import { assertLiveModeReady, loadConfig } from './config/env.js';
import { Btc15Runtime } from './runtime.js';

export async function bootstrap(): Promise<void> {
  const config = loadConfig();
  assertLiveModeReady(config);

  const kalshiAdapter =
    config.serviceMode === 'live'
      ? new LiveKalshiAdapter(new UnimplementedKalshiLiveClient(config))
      : new PaperKalshiAdapter(config.kalshiMarketPrefix);

  const runtime = new Btc15Runtime(
    config,
    new BinanceBtcFeedAdapter(config.binanceSymbol, {
      reconnectBaseMs: config.binanceReconnectBaseMs,
      reconnectMaxMs: config.binanceReconnectMaxMs,
      staleThresholdMs: config.binanceStaleThresholdMs
    }),
    kalshiAdapter
  );

  await runtime.start();
  console.log(
    JSON.stringify({
      component: 'bootstrap',
      serviceMode: config.serviceMode,
      safety: config.safety,
      msg: 'runtime started'
    })
  );

  const interval = setInterval(async () => {
    try {
      const result = await runtime.evaluateCycle(new Date());
      if (!result) {
        console.log(
          JSON.stringify({
            component: 'runtime',
            msg: 'waiting for sufficient price samples',
            sampleCount: runtime.getSampleCount(),
            requiredSamples: config.minPriceSamples
          })
        );
        return;
      }
      console.log(
        JSON.stringify({
          component: 'runtime',
          serviceMode: config.serviceMode,
          realizedPnlDollars: runtime.getRealizedPnlDollars(),
          ...result
        })
      );
    } catch (error) {
      console.error(
        JSON.stringify({
          component: 'runtime',
          msg: 'evaluation cycle failed',
          error: error instanceof Error ? error.message : String(error)
        })
      );
    }
  }, config.evalIntervalMs);

  const shutdown = async (signal: string): Promise<void> => {
    clearInterval(interval);
    console.log(JSON.stringify({ component: 'bootstrap', msg: 'shutdown requested', signal }));
    await runtime.stop();
    process.exit(0);
  };

  process.once('SIGINT', () => void shutdown('SIGINT'));
  process.once('SIGTERM', () => void shutdown('SIGTERM'));
}

if (import.meta.url === `file://${process.argv[1]}`) {
  bootstrap().catch((error) => {
    console.error(error);
    process.exitCode = 1;
  });
}
