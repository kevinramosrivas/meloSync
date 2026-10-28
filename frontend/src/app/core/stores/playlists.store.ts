import { Service, effect, inject, signal, OnDestroy } from '@angular/core';
import { Subscription } from 'rxjs';
import { PlaylistsApiService } from '../../data/playlists-api.service';
import { WebSocketService } from '../services/websocket.service';
import { PlaylistSummary } from '../../domain/models';

@Service()
export class PlaylistsStore implements OnDestroy {
  private readonly playlistsApi = inject(PlaylistsApiService);
  private readonly ws = inject(WebSocketService);

  readonly userPlaylists = signal<PlaylistSummary[]>([]);
  readonly forYouPlaylists = signal<PlaylistSummary[]>([]);
  readonly artistPlaylists = signal<PlaylistSummary[]>([]);
  readonly genrePlaylists = signal<PlaylistSummary[]>([]);

  readonly isLoading = signal<boolean>(false);
  readonly isInitialLoading = signal<boolean>(true);
  readonly hasLoaded = signal<boolean>(false);
  readonly connectionFailed = signal<boolean>(false);

  private inFlightSub: Subscription | null = null;
  private retryTimeout: ReturnType<typeof setTimeout> | null = null;
  private lastWsUpdate: number;

  constructor() {
    this.lastWsUpdate = this.ws.libraryUpdated();

    // Background revalidation when library changes (updates smart playlists & counts)
    effect(() => {
      const updated = this.ws.libraryUpdated();
      if (updated !== this.lastWsUpdate) {
        this.lastWsUpdate = updated;
        if (this.hasLoaded()) {
          this.load(true, 0);
        }
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
   * Loads playlists into memory.
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

    this.inFlightSub = this.playlistsApi.getPlaylists().subscribe({
      next: (resp) => {
        this.inFlightSub = null;
        this.userPlaylists.set(resp.user_playlists);
        this.forYouPlaylists.set(resp.for_you_playlists);
        this.artistPlaylists.set(resp.artist_playlists);
        this.genrePlaylists.set(resp.genre_playlists);
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

