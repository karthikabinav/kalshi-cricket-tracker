import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import {
  BinanceBtcFeedAdapter,
  createBinanceTradeStreamUrl,
  parseBinanceTradeMessage
} from '../src/adapters/binanceFeed.js';

class MockWebSocket extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  closeCalls: Array<{ code?: number; reason?: string }> = [];

  constructor(url: string) {
    super();
    this.url = url;
  }

  open(): void {
    this.readyState = MockWebSocket.OPEN;
    this.dispatchEvent(new Event('open'));
  }

  emitMessage(data: string): void {
    const event = new MessageEvent('message', { data });
    this.dispatchEvent(event);
  }

  fail(): void {
    this.dispatchEvent(new Event('error'));
  }

  close(code?: number, reason?: string): void {
    this.closeCalls.push({ code, reason });
    this.readyState = MockWebSocket.CLOSED;
    const event = new CloseEvent('close', { code: code ?? 1000, reason: reason ?? '' });
    this.dispatchEvent(event);
  }
}

describe('binance feed adapter', () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('builds the Binance trade stream URL', () => {
    expect(createBinanceTradeStreamUrl('BTCUSDT')).toBe('wss://stream.binance.com:9443/ws/btcusdt@trade');
  });

  it('parses trade messages into price points', () => {
    const point = parseBinanceTradeMessage(JSON.stringify({ e: 'trade', p: '84321.12', T: 1234 }));
    expect(point).toEqual({ price: 84321.12, tsMs: 1234 });
  });

  it('reconnects after a socket close and resumes streaming', async () => {
    const sockets: MockWebSocket[] = [];
    const points: number[] = [];
    const logger = { info: vi.fn(), warn: vi.fn(), error: vi.fn() };
    const adapter = new BinanceBtcFeedAdapter('btcusdt', {
      websocketFactory: (url) => {
        const socket = new MockWebSocket(url);
        sockets.push(socket);
        return socket as unknown as WebSocket;
      },
      reconnectBaseMs: 50,
      reconnectMaxMs: 100,
      staleThresholdMs: 500,
      logger
    });

    const connectPromise = adapter.connect((point) => points.push(point.price));
    expect(sockets).toHaveLength(1);
    sockets[0]!.open();
    await connectPromise;

    sockets[0]!.emitMessage(JSON.stringify({ e: 'trade', p: '84000.50', T: 1000 }));
    expect(points).toEqual([84000.5]);

    sockets[0]!.close(1006, 'network');
    await vi.advanceTimersByTimeAsync(50);
    expect(sockets).toHaveLength(2);

    sockets[1]!.open();
    sockets[1]!.emitMessage(JSON.stringify({ e: 'trade', p: '84001.25', T: 1001 }));
    expect(points).toEqual([84000.5, 84001.25]);
    expect(logger.warn).toHaveBeenCalled();
  });

  it('forces a reconnect when the stream goes stale', async () => {
    const sockets: MockWebSocket[] = [];
    const adapter = new BinanceBtcFeedAdapter('btcusdt', {
      websocketFactory: (url) => {
        const socket = new MockWebSocket(url);
        sockets.push(socket);
        return socket as unknown as WebSocket;
      },
      reconnectBaseMs: 25,
      reconnectMaxMs: 50,
      staleThresholdMs: 100,
      logger: { info: vi.fn(), warn: vi.fn(), error: vi.fn() }
    });

    const connectPromise = adapter.connect(() => undefined);
    sockets[0]!.open();
    await connectPromise;
    sockets[0]!.emitMessage(JSON.stringify({ e: 'trade', p: '84000.50', T: 1000 }));

    await vi.advanceTimersByTimeAsync(100);
    expect(sockets[0]!.closeCalls[0]).toEqual({ code: 4000, reason: 'stale stream' });
  });
});
