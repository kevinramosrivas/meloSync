import { Injectable, signal, computed, OnDestroy, inject } from '@angular/core';
import { filter, take } from 'rxjs';
import { API_CONFIG } from '../config/api.config';
import { BackendGateService } from './backend-gate.service';
import { WebSocketEvent, DownloadProgress, Track } from '../../domain/models';

@Injectable({
  providedIn: 'root'
})
export class WebSocketService implements OnDestroy {
  private readonly backendGate = inject(BackendGateService);
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
  readonly activeDownloads = signal<Map<string, DownloadProgress>>(new Map());
  readonly activeDownloadsCount = computed(() => this.activeDownloads().size);
  readonly hasActiveDownloads = computed(() => this.activeDownloadsCount() > 0);

  constructor() {
    this.backendGate.ready$
      .pipe(
        filter(ready => ready === true)
      )
      .subscribe(() => {
        // If socket is already open to current port, keep it; otherwise reconnect
        if (!this.socket || this.socket.url !== API_CONFIG.wsUrl) {
          if (this.socket) {
            try { this.socket.close(); } catch {}
            this.socket = null;
          }
          this.connect();
        }
      });
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
      case 'download_progress': {
        const progress = event.data as DownloadProgress;
        const isTerminal = progress.status === 'COMPLETADA' || progress.status === 'ERROR' || progress.status === 'CANCELADA';

        if (isTerminal) {
          const current = this.latestProgress();
          if (current && (current.track_id === progress.track_id || current.youtube_id === progress.youtube_id)) {
            this.latestProgress.set(null);
          }
        } else {
          this.latestProgress.set(progress);
        }

        this.activeDownloads.update(map => {
          const key = progress.youtube_id || progress.track_id;
          if (!key) return map;
          const newMap = new Map(map);
          if (isTerminal) {
            newMap.delete(key);
          } else {
            newMap.set(key, progress);
          }
          return newMap;
        });
        break;
      }
      case 'download_completed': {
        if (event.data?.track) {
          const track = event.data.track;
          this.latestCompletedTrack.set(track);
          const key = track.youtube_id || track.id;
          this.activeDownloads.update(map => {
            if (key && map.has(key)) {
              const newMap = new Map(map);
              newMap.delete(key);
              return newMap;
            }
            return map;
          });
          const current = this.latestProgress();
          if (current && (current.youtube_id === track.youtube_id || current.track_id === track.id)) {
            this.latestProgress.set(null);
          }
        }
        this.libraryUpdated.set(Date.now());
        break;
      }
      case 'library_updated':
        this.libraryUpdated.set(Date.now());
        break;
    }
  }

  syncActiveDownloads(tracks: Track[]): void {
    const activeMap = new Map<string, DownloadProgress>();
    for (const t of tracks) {
      if (t.status !== 'COMPLETADA' && t.status !== 'ERROR' && t.status !== 'CANCELADA') {
        const key = t.youtube_id || t.id;
        if (key) {
          activeMap.set(key, {
            track_id: t.id,
            youtube_id: t.youtube_id,
            status: t.status,
            progress_percent: t.progress_percent,
            stage_description: t.original_title,
          });
        }
      }
    }
    this.activeDownloads.set(activeMap);
    if (activeMap.size === 0) {
      this.latestProgress.set(null);
    }
  }

  removeActiveDownload(identifier: string): void {
    this.activeDownloads.update(map => {
      let changed = false;
      const newMap = new Map(map);
      for (const [key, val] of map.entries()) {
        if (key === identifier || val.track_id === identifier || val.youtube_id === identifier) {
          newMap.delete(key);
          changed = true;
        }
      }
      return changed ? newMap : map;
    });
    const current = this.latestProgress();
    if (current && (current.track_id === identifier || current.youtube_id === identifier)) {
      this.latestProgress.set(null);
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
