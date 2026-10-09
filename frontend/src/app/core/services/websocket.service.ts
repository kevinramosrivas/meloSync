import { Injectable, signal, OnDestroy } from '@angular/core';
import { API_CONFIG } from '../config/api.config';
import { WebSocketEvent, DownloadProgress, Track } from '../../domain/models';

@Injectable({
  providedIn: 'root'
})
export class WebSocketService implements OnDestroy {
  private socket: WebSocket | null = null;
  private reconnectTimeout: any = null;
  private pingInterval: any = null;
  private retryCount = 0;
  private maxRetries = 10;
  private baseDelay = 1000;

  // Reactive state signals
  readonly isConnected = signal<boolean>(false);
  readonly latestProgress = signal<DownloadProgress | null>(null);
  readonly latestCompletedTrack = signal<Track | null>(null);
  readonly libraryUpdated = signal<number>(Date.now());

  constructor() {
    this.connect();
  }

  connect(): void {
    if (this.socket && (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING)) {
      return;
    }

    try {
      this.socket = new WebSocket(API_CONFIG.wsUrl);

      this.socket.onopen = () => {
        this.isConnected.set(true);
        this.retryCount = 0;
        this.startHeartbeat();
      };

      this.socket.onmessage = (event: MessageEvent) => {
        try {
          if (event.data === 'pong') return;
          const payload: WebSocketEvent = JSON.parse(event.data);
          this.handleEvent(payload);
        } catch {
          // Non-JSON message
        }
      };

      this.socket.onclose = () => {
        this.isConnected.set(false);
        this.stopHeartbeat();
        this.scheduleReconnect();
      };

      this.socket.onerror = () => {
        this.isConnected.set(false);
      };
    } catch {
      this.scheduleReconnect();
    }
  }

  private handleEvent(event: WebSocketEvent): void {
    switch (event.event) {
      case 'download_progress':
        this.latestProgress.set(event.data as DownloadProgress);
        break;
      case 'download_completed':
        if (event.data?.track) {
          this.latestCompletedTrack.set(event.data.track);
        }
        this.libraryUpdated.set(Date.now());
        break;
      case 'library_updated':
        this.libraryUpdated.set(Date.now());
        break;
    }
  }

  private startHeartbeat(): void {
    this.stopHeartbeat();
    this.pingInterval = setInterval(() => {
      if (this.socket && this.socket.readyState === WebSocket.OPEN) {
        this.socket.send('ping');
      }
    }, 15000);
  }

  private stopHeartbeat(): void {
    if (this.pingInterval) {
      clearInterval(this.pingInterval);
      this.pingInterval = null;
    }
  }

  private scheduleReconnect(): void {
    if (this.reconnectTimeout) return;
    if (this.retryCount < this.maxRetries) {
      const delay = Math.min(this.baseDelay * Math.pow(1.5, this.retryCount), 10000);
      this.retryCount++;
      this.reconnectTimeout = setTimeout(() => {
        this.reconnectTimeout = null;
        this.connect();
      }, delay);
    }
  }

  ngOnDestroy(): void {
    this.stopHeartbeat();
    if (this.reconnectTimeout) {
      clearTimeout(this.reconnectTimeout);
    }
    if (this.socket) {
      this.socket.close();
      this.socket = null;
    }
  }
}
