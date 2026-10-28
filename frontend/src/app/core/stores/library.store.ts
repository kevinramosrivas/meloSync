import { Service, effect, inject, signal, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { LibraryApiService } from '../../data/library-api.service';
import { WebSocketService } from '../services/websocket.service';
import { Track } from '../../domain/models';

@Service()
export class LibraryStore implements OnDestroy {
  private readonly libraryApi = inject(LibraryApiService);
  private readonly ws = inject(WebSocketService);

  readonly tracks = signal<Track[]>([]);
  readonly isLoading = signal<boolean>(false);
  readonly isInitialLoading = signal<boolean>(true);
  readonly hasLoaded = signal<boolean>(false);
  readonly connectionFailed = signal<boolean>(false);

  private inFlightSub: Subscription | null = null;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private lastWsUpdate: number;

  constructor() {
    this.lastWsUpdate = this.ws.libraryUpdated();

    // Background revalidation when WebSocket signals library changes
    effect(() => {
      const updated = this.ws.libraryUpdated();
      if (updated !== this.lastWsUpdate) {
        this.lastWsUpdate = updated;
        this.load(true, 0);
      }
    });

    // Immediate hydration when WebSocket connects during cold start
    effect(() => {
      if (this.ws.isConnected() && !this.hasLoaded()) {
        this.load(true, 0);
      }
    });
  }

  /**
   * Loads tracks into memory.
   * If already loaded and force is false, returns instantaneously (0ms).
   * If a request is already in-flight and force is false, de-duplicates the call.
   */
  load(force = false, retryCount = 0): void {
    if (this.hasLoaded() && !force) {
      return;
    }

    if (this.inFlightSub && !force && retryCount === 0) {
      return;
    }

    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }

    if (this.inFlightSub) {
      this.inFlightSub.unsubscribe();
      this.inFlightSub = null;
    }

    this.isLoading.set(true);
    if (!this.hasLoaded()) {
      this.isInitialLoading.set(true);
    }
    this.connectionFailed.set(false);

    this.inFlightSub = this.libraryApi.getLibrary('COMPLETADA').subscribe({
      next: (data) => {
        this.inFlightSub = null;
        this.tracks.set(data);
        this.hasLoaded.set(true);
        this.isLoading.set(false);
        this.isInitialLoading.set(false);
        this.connectionFailed.set(false);
      },
      error: () => {
        this.inFlightSub = null;
        if (!this.hasLoaded() && retryCount < 8) {
          const delay = Math.min(1000 * Math.pow(1.25, retryCount), 3500);
          this.retryTimeout = setTimeout(() => {
            this.retryTimeout = null;
            this.load(true, retryCount + 1);
          }, delay);
        } else {
          this.isLoading.set(false);
          if (!this.hasLoaded()) {
            this.isInitialLoading.set(false);
            this.connectionFailed.set(true);
          }
        }
      }
    });
  }

  updateTrackInMemory(updatedTrack: Track): void {
    this.tracks.update((list) =>
      list.map((t) => (t.id === updatedTrack.id ? updatedTrack : t))
    );
  }

  removeTrackFromMemory(trackId: string): void {
    this.tracks.update((list) => list.filter((t) => t.id !== trackId));
  }

  ngOnDestroy(): void {
    if (this.retryTimeout) {
      clearTimeout(this.retryTimeout);
      this.retryTimeout = null;
    }
    if (this.inFlightSub) {
      this.inFlightSub.unsubscribe();
      this.inFlightSub = null;
    }
  }
}

