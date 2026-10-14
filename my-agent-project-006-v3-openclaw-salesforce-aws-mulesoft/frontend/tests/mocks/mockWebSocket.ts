/**
 * Mock WebSocket for jsdom tests.
 *
 * Extends EventTarget so it satisfies both our app code (which uses onopen/
 * onmessage handlers) AND any interceptor/observer that expects
 * addEventListener. Installed globally after MSW so it wins the constructor
 * slot.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */

export class MockWebSocket extends EventTarget {
  static readonly CONNECTING = 0;
  static readonly OPEN = 1;
  static readonly CLOSING = 2;
  static readonly CLOSED = 3;

  static instances: MockWebSocket[] = [];
  static get last(): MockWebSocket | undefined {
    return MockWebSocket.instances[MockWebSocket.instances.length - 1];
  }
  static reset(): void {
    MockWebSocket.instances = [];
  }

  readonly CONNECTING = MockWebSocket.CONNECTING;
  readonly OPEN = MockWebSocket.OPEN;
  readonly CLOSING = MockWebSocket.CLOSING;
  readonly CLOSED = MockWebSocket.CLOSED;

  readyState = MockWebSocket.CONNECTING;
  url: string;
  protocol = '';
  binaryType: 'blob' | 'arraybuffer' = 'blob';
  bufferedAmount = 0;
  extensions = '';
  onopen: ((ev: Event) => void) | null = null;
  onmessage: ((ev: MessageEvent) => void) | null = null;
  onerror: ((ev: Event) => void) | null = null;
  onclose: ((ev: CloseEvent) => void) | null = null;
  sent: string[] = [];

  constructor(url: string, _protocols?: string | string[]) {
    super();
    this.url = url;
    MockWebSocket.instances.push(this);
  }

  send(data: string): void {
    this.sent.push(data);
  }

  close(code = 1000, reason = 'client closing'): void {
    this.readyState = MockWebSocket.CLOSED;
    const ev = { code, reason, wasClean: true } as CloseEvent;
    this.onclose?.(ev);
    this.dispatchEvent(new Event('close'));
  }

  simulateOpen(): void {
    this.readyState = MockWebSocket.OPEN;
    const ev = new Event('open');
    this.onopen?.(ev);
    this.dispatchEvent(ev);
  }
  simulateMessage(payload: unknown): void {
    const data = typeof payload === 'string' ? payload : JSON.stringify(payload);
    const ev = { data } as MessageEvent;
    this.onmessage?.(ev);
    this.dispatchEvent(new MessageEvent('message', { data }));
  }
  simulateClose(code = 1006): void {
    this.readyState = MockWebSocket.CLOSED;
    const ev = { code, reason: 'test close', wasClean: code === 1000 } as CloseEvent;
    this.onclose?.(ev);
    this.dispatchEvent(new Event('close'));
  }
  simulateError(): void {
    const ev = new Event('error');
    this.onerror?.(ev);
    this.dispatchEvent(ev);
  }
}

// Global install is performed by vitest.setup.ts via Object.defineProperty.
