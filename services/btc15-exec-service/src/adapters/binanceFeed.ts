import type { PricePoint } from '../types.js';

export interface PriceFeedAdapter {
  connect(onPrice: (point: PricePoint) => void): Promise<void>;
  disconnect(): Promise<void>;
}

export interface BinanceTradeMessage {
  e: 'trade';
  E: number;
  s: string;
  p: string;
  q: string;
  T: number;
}

export interface BinanceFeedOptions {
  websocketFactory?: (url: string) => WebSocket;
  reconnectBaseMs?: number;
  reconnectMaxMs?: number;
  staleThresholdMs?: number;
  logger?: Pick<Console, 'info' | 'warn' | 'error'>;
}

const DEFAULT_RECONNECT_BASE_MS = 1_000;
const DEFAULT_RECONNECT_MAX_MS = 15_000;
const DEFAULT_STALE_THRESHOLD_MS = 20_000;

export function createBinanceTradeStreamUrl(symbol: string): string {
  return `wss://stream.binance.com:9443/ws/${symbol.toLowerCase()}@trade`;
}

export function parseBinanceTradeMessage(raw: string): PricePoint | null {
  const payload = JSON.parse(raw) as Partial<BinanceTradeMessage>;
  if (payload.e !== 'trade' || typeof payload.p !== 'string') {
    return null;
  }

  const price = Number(payload.p);
  const tsMs = typeof payload.T === 'number' ? payload.T : typeof payload.E === 'number' ? payload.E : Date.now();
  if (!Number.isFinite(price) || !Number.isFinite(tsMs)) {
    return null;
  }

  return { price, tsMs };
}

export class BinanceBtcFeedAdapter implements PriceFeedAdapter {
  private readonly websocketFactory: (url: string) => WebSocket;
  private readonly reconnectBaseMs: number;
  private readonly reconnectMaxMs: number;
  private readonly staleThresholdMs: number;
  private readonly logger: Pick<Console, 'info' | 'warn' | 'error'>;

  private onPrice: ((point: PricePoint) => void) | null = null;
  private ws: WebSocket | null = null;
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private staleTimer: ReturnType<typeof setTimeout> | null = null;
  private attempts = 0;
  private lastMessageAtMs = 0;
  private closed = false;
  private connectionPromise: Promise<void> | null = null;

  constructor(private readonly symbol: string, options: BinanceFeedOptions = {}) {
    this.websocketFactory = options.websocketFactory ?? ((url) => new WebSocket(url));
    this.reconnectBaseMs = options.reconnectBaseMs ?? DEFAULT_RECONNECT_BASE_MS;
    this.reconnectMaxMs = options.reconnectMaxMs ?? DEFAULT_RECONNECT_MAX_MS;
    this.staleThresholdMs = options.staleThresholdMs ?? DEFAULT_STALE_THRESHOLD_MS;
    this.logger = options.logger ?? console;
  }

  async connect(onPrice: (point: PricePoint) => void): Promise<void> {
    this.closed = false;
    this.onPrice = onPrice;
    if (!this.connectionPromise) {
      this.connectionPromise = this.openSocket();
    }
    await this.connectionPromise;
  }

  async disconnect(): Promise<void> {
    this.closed = true;
    this.clearReconnectTimer();
    this.clearStaleTimer();
    this.connectionPromise = null;
    const ws = this.ws;
    this.ws = null;
    if (ws && ws.readyState === WebSocket.OPEN) {
      ws.close(1000, 'client disconnect');
    } else if (ws && ws.readyState === WebSocket.CONNECTING) {
      ws.close();
    }
  }

  private async openSocket(): Promise<void> {
    const url = createBinanceTradeStreamUrl(this.symbol);
    const ws = this.websocketFactory(url);
    this.ws = ws;

    await new Promise<void>((resolve) => {
      let resolved = false;
      const settle = (): void => {
        if (!resolved) {
          resolved = true;
          resolve();
        }
      };

      ws.addEventListener('open', () => {
        this.attempts = 0;
        this.lastMessageAtMs = Date.now();
        this.logger.info(JSON.stringify({ component: 'binance-feed', symbol: this.symbol, msg: 'connected' }));
        this.armStaleTimer();
        settle();
      });

      ws.addEventListener('message', (event) => {
        this.lastMessageAtMs = Date.now();
        this.armStaleTimer();
        const data = typeof event.data === 'string' ? event.data : event.data?.toString?.();
        if (!data) {
          return;
        }
        try {
          const point = parseBinanceTradeMessage(data);
          if (point && this.onPrice) {
            this.onPrice(point);
          }
        } catch (error) {
          this.logger.warn(
            JSON.stringify({
              component: 'binance-feed',
              symbol: this.symbol,
              msg: 'failed to parse trade message',
              error: error instanceof Error ? error.message : String(error)
            })
          );
        }
      });

      ws.addEventListener('error', () => {
        this.logger.warn(JSON.stringify({ component: 'binance-feed', symbol: this.symbol, msg: 'websocket error' }));
        settle();
      });

      ws.addEventListener('close', (event) => {
        this.clearStaleTimer();
        if (this.ws === ws) {
          this.ws = null;
        }
        if (!this.closed) {
          this.logger.warn(
            JSON.stringify({
              component: 'binance-feed',
              symbol: this.symbol,
              msg: 'socket closed; scheduling reconnect',
              code: event.code,
              reason: event.reason
            })
          );
          this.scheduleReconnect();
        }
        settle();
      });
    });
  }

  private armStaleTimer(): void {
    this.clearStaleTimer();
    this.staleTimer = setTimeout(() => {
      const ws = this.ws;
      if (!ws || this.closed) {
        return;
      }
      const ageMs = Date.now() - this.lastMessageAtMs;
      if (ageMs >= this.staleThresholdMs) {
        this.logger.warn(
          JSON.stringify({ component: 'binance-feed', symbol: this.symbol, msg: 'stale stream detected; forcing reconnect', ageMs })
        );
        ws.close(4000, 'stale stream');
      }
    }, this.staleThresholdMs);
  }

  private scheduleReconnect(): void {
    if (this.closed || this.reconnectTimer) {
      return;
    }
    this.attempts += 1;
    const delayMs = Math.min(this.reconnectMaxMs, this.reconnectBaseMs * 2 ** (this.attempts - 1));
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.closed) {
        return;
      }
      this.connectionPromise = this.openSocket();
      void this.connectionPromise;
    }, delayMs);
  }

  private clearReconnectTimer(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private clearStaleTimer(): void {
    if (this.staleTimer) {
      clearTimeout(this.staleTimer);
      this.staleTimer = null;
    }
  }
}
