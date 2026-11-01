import { Service, signal } from '@angular/core';
import { BehaviorSubject } from 'rxjs';
import { API_CONFIG } from '../config/api.config';

async function invokeTauri<T>(cmd: string, args?: Record<string, unknown>): Promise<T | null> {
  try {
    if (typeof window !== 'undefined') {
      if (window.__TAURI__?.core?.invoke) {
        return await window.__TAURI__.core.invoke<T>(cmd, args);
      }
      if (window.__TAURI_INTERNALS__?.invoke) {
        return (await window.__TAURI_INTERNALS__.invoke(cmd, args)) as T;
      }
    }
  } catch (err) {
    console.debug(`[Tauri] ${cmd} notice:`, err);
  }
  return null;
}

@Service()
export class BackendGateService {
  readonly isReady = signal<boolean>(false);
  readonly port = signal<number>(8000);
  readonly ready$ = new BehaviorSubject<boolean>(false);

  private unlistenEvent: (() => void) | null = null;
  private probeActive = false;

  constructor() {
    // In unit test runner environment, immediately consider backend ready
    if (typeof window !== 'undefined' && window.__VITEST__) {
      this.isReady.set(true);
      this.ready$.next(true);
      return;
    }

    this.initGate();
  }

  private async initGate(): Promise<void> {
    // 1. Inquire dynamic port from Tauri or web discovery file
    const dynamicPort = await this.resolveInitialPort();
    if (dynamicPort && dynamicPort > 0) {
      this.port.set(dynamicPort);
      API_CONFIG.setPort(dynamicPort);
    }

    // 2. Listen to Tauri 'backend-ready' background event
    if (typeof window !== 'undefined' && window.__TAURI__?.event?.listen) {
      try {
        this.unlistenEvent = await window.__TAURI__.event.listen<number>('backend-ready', (e) => {
          const readyPort = e.payload || this.port() || 8000;
          this.markReady(readyPort);
        });
      } catch {
        // Fallback to active probe below
      }
    }

    // 3. Start lightweight active polling probe (100ms interval) with strict timeout
    this.startActiveHealthProbe();
  }

  private async resolveInitialPort(): Promise<number | null> {
    const tauriPort = await invokeTauri<number>('get_backend_port');
    if (tauriPort && tauriPort > 0) {
      return tauriPort;
    }
    return await this.readWebDiscoveryPort();
  }

  private async readWebDiscoveryPort(): Promise<number | null> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 250);
    try {
      const res = await fetch('/active_port.json', {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
      });
      if (res.ok) {
        const data = (await res.json()) as { port?: number };
        if (data?.port && data.port > 0 && data.port <= 65535) {
          return data.port;
        }
      }
    } catch {
      // Discovery file may not exist in production static build
    } finally {
      clearTimeout(timer);
    }
    return null;
  }

  /**
   * Probes `http://127.0.0.1:<port>/health` with a strict 400ms timeout
   * and verifies that the responder is genuinely `meloSync API`.
   */
  async probeHealth(port: number): Promise<boolean> {
    const controller = new AbortController();
    const timer = setTimeout(() => controller.abort(), 400);
    try {
      const healthUrl = `http://127.0.0.1:${port}/health`;
      const res = await fetch(healthUrl, {
        method: 'GET',
        cache: 'no-store',
        signal: controller.signal,
      });
      if (!res.ok) {
        return false;
      }
      const data = (await res.json()) as { status?: string; service?: string };
      return data?.service === 'meloSync API';
    } catch {
      return false;
    } finally {
      clearTimeout(timer);
    }
  }

  private async startActiveHealthProbe(): Promise<void> {
    if (this.probeActive || this.isReady()) return;
    this.probeActive = true;

    const maxAttempts = 150; // ~15 seconds max
    let attempts = 0;

    while (attempts < maxAttempts && !this.isReady()) {
      // Refresh port from Tauri in case background discovery updated it
      const latestTauriPort = await invokeTauri<number>('get_backend_port');
      if (latestTauriPort && latestTauriPort > 0 && latestTauriPort !== this.port()) {
        this.port.set(latestTauriPort);
        API_CONFIG.setPort(latestTauriPort);
      }

      const currentPort = this.port();
      if (await this.probeHealth(currentPort)) {
        this.markReady(currentPort);
        break;
      }

      // Check web discovery file if available and pointing to a different port
      if (!this.isReady()) {
        const discPort = await this.readWebDiscoveryPort();
        if (discPort && discPort !== currentPort && (await this.probeHealth(discPort))) {
          this.markReady(discPort);
          break;
        }
      }

      attempts++;
      await new Promise((resolve) => setTimeout(resolve, 100));
    }

    this.probeActive = false;

    // Safety fallback: if maxAttempts elapsed, open gate to prevent permanently hanging UI
    if (!this.isReady()) {
      this.markReady(this.port());
    }
  }

  markReady(port: number): void {
    this.port.set(port);
    API_CONFIG.setPort(port);
    if (!this.isReady()) {
      this.isReady.set(true);
      this.ready$.next(true);
    }

    if (this.unlistenEvent) {
      try {
        this.unlistenEvent();
        this.unlistenEvent = null;
      } catch {}
    }
  }

  isBackendRequest(url: string): boolean {
    if (!url) return false;
    return (
      url.includes('/api/v1') ||
      url.startsWith('http://127.0.0.1:') ||
      url.startsWith('http://localhost:') ||
      url.startsWith('/api/')
    );
  }

  rewriteUrlIfNeeded(url: string): string {
    const currentBase = API_CONFIG.baseUrl;
    // Replace hardcoded 8000 or outdated port with current resolved dynamic base URL
    return url.replace(/http:\/\/(?:127\.0\.0\.1|localhost):(?:\d+)/, currentBase);
  }
}
