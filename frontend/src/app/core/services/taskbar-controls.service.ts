import { Service, effect, inject, signal } from '@angular/core';
import { AudioPlayerService } from './audio-player.service';
import { UserPreferencesService } from './user-preferences.service';

@Service()
export class TaskbarControlsService {
  private readonly audioPlayer = inject(AudioPlayerService);
  private readonly preferences = inject(UserPreferencesService);

  private readonly _isPlatformSupported = signal<boolean>(false);
  readonly isPlatformSupported = this._isPlatformSupported.asReadonly();

  private unlistenTogglePlay: (() => void) | null = null;
  private unlistenPrevious: (() => void) | null = null;
  private unlistenNext: (() => void) | null = null;

  private lastProgressSec = -1;
  private lastPlayingState: boolean | null = null;
  private lastTrackId: string | null = null;
  private lastTrackTitle: string | null = null;
  private lastTrackArtist: string | null = null;
  private initialized = false;

  constructor() {
    this.detectPlatform();
    this.setupSyncEffect();
  }

  isTauri(): boolean {
    return typeof window !== 'undefined' && !!window.__TAURI__?.core?.invoke;
  }

  isWindows(): boolean {
    if (typeof navigator === 'undefined') return false;
    const ua = navigator.userAgent || '';
    const platform = (navigator as unknown as { platform?: string }).platform || '';
    return /Windows|Win32|Win64/i.test(ua) || /Win/i.test(platform);
  }

  private async detectPlatform(): Promise<void> {
    if (!this.isTauri()) {
      this._isPlatformSupported.set(false);
      return;
    }

    try {
      if (window.__TAURI__?.core?.invoke) {
        const platform = await window.__TAURI__.core.invoke<string>('get_desktop_platform');
        this._isPlatformSupported.set(platform === 'windows');
      } else {
        this._isPlatformSupported.set(this.isWindows());
      }
    } catch {
      this._isPlatformSupported.set(this.isWindows());
    }

    if (this._isPlatformSupported()) {
      await this.initListeners();
    }
  }

  async initListeners(): Promise<void> {
    if (this.initialized || typeof window === 'undefined' || !window.__TAURI__?.event?.listen) {
      return;
    }
    this.initialized = true;

    try {
      this.unlistenTogglePlay = await window.__TAURI__.event.listen('taskbar-toggle-play', () => {
        this.audioPlayer.togglePlay();
      });

      this.unlistenPrevious = await window.__TAURI__.event.listen('taskbar-previous', () => {
        this.audioPlayer.playPrevious();
      });

      this.unlistenNext = await window.__TAURI__.event.listen('taskbar-next', () => {
        this.audioPlayer.playNext();
      });

      if (window.__TAURI__?.core?.invoke) {
        await window.__TAURI__.core.invoke('init_taskbar_controls');
      }
    } catch (e) {
      console.warn('Could not initialize Windows taskbar thumbnail listeners:', e);
    }
  }

  private setupSyncEffect(): void {
    effect(() => {
      const isSupported = this._isPlatformSupported();
      const isEnabled = this.preferences.taskbarControlsEnabled();
      const currentTrack = this.audioPlayer.currentTrack();
      const isPlaying = this.audioPlayer.isPlaying();
      const queue = this.audioPlayer.playlist();
      const currentTime = Math.floor(this.audioPlayer.currentTime());
      const duration = Math.floor(this.audioPlayer.duration());

      if (!isSupported || !isEnabled || typeof window === 'undefined' || !window.__TAURI__?.core?.invoke) {
        return;
      }

      // 1. Window Title & Live Taskbar Thumbnail Tooltip Synchronization (Spotify Style)
      const trackId = currentTrack?.id ?? null;
      const trackTitle = currentTrack?.display_title ?? null;
      const trackArtist = currentTrack?.display_artist ?? null;

      if (
        this.lastTrackId !== trackId ||
        this.lastTrackTitle !== trackTitle ||
        this.lastTrackArtist !== trackArtist
      ) {
        this.lastTrackId = trackId;
        this.lastTrackTitle = trackTitle;
        this.lastTrackArtist = trackArtist;

        const formattedDocTitle = trackTitle
          ? (trackArtist ? `${trackTitle} • ${trackArtist}` : trackTitle)
          : 'meloSync';

        if (typeof document !== 'undefined') {
          document.title = formattedDocTitle;
        }

        window.__TAURI__.core.invoke('update_taskbar_track', {
          title: trackTitle,
          artist: trackArtist,
        }).catch(() => {});
      }

      // 2. Playback State Synchronization (Buttons & Icons)
      const currentIndex = queue.findIndex((t) => t.id === currentTrack?.id);
      const canPrevious = currentIndex > 0;
      const canNext = currentIndex >= 0 && currentIndex < queue.length - 1;

      if (this.lastPlayingState !== isPlaying) {
        this.lastPlayingState = isPlaying;
        window.__TAURI__.core.invoke('update_taskbar_playback', {
          isPlaying,
          canPrevious,
          canNext
        }).catch(() => {});
      }

      // 3. Taskbar Progress Bar Synchronization (Green bar on taskbar icon)
      if (currentTrack && duration > 0) {
        if (currentTime !== this.lastProgressSec) {
          this.lastProgressSec = currentTime;
          window.__TAURI__.core.invoke('update_taskbar_progress', {
            positionSecs: currentTime,
            durationSecs: duration,
            isPlaying
          }).catch(() => {});
        }
      } else if (this.lastProgressSec !== -1) {
        this.lastProgressSec = -1;
        window.__TAURI__.core.invoke('clear_taskbar_progress').catch(() => {});
      }
    });
  }

  destroy(): void {
    if (typeof document !== 'undefined') {
      document.title = 'meloSync';
    }
    if (typeof window !== 'undefined' && window.__TAURI__?.core?.invoke) {
      window.__TAURI__.core.invoke('update_taskbar_track', {
        title: null,
        artist: null,
      }).catch(() => {});
    }

    if (this.unlistenTogglePlay) {
      this.unlistenTogglePlay();
      this.unlistenTogglePlay = null;
    }
    if (this.unlistenPrevious) {
      this.unlistenPrevious();
      this.unlistenPrevious = null;
    }
    if (this.unlistenNext) {
      this.unlistenNext();
      this.unlistenNext = null;
    }
    this.initialized = false;
  }
}

