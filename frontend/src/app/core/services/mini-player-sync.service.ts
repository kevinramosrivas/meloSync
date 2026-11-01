import { Service, computed, effect, inject, signal, untracked } from '@angular/core';
import { Track } from '../../domain/models';
import { AudioPlayerService } from './audio-player.service';

export interface MiniPlayerState {
  track: Track | null;
  coverUrl: string | null;
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  hasNext: boolean;
  hasPrevious: boolean;
}

export type MiniPlayerAction =
  | { type: 'TOGGLE_PLAY' }
  | { type: 'NEXT' }
  | { type: 'PREVIOUS' }
  | { type: 'SEEK'; time: number }
  | { type: 'SET_VOLUME'; volume: number }
  | { type: 'CLOSE' }
  | { type: 'RESTORE_MAIN' };

export type MiniPlayerSyncMessage =
  | { type: 'REQUEST_STATE' }
  | { type: 'STATE_UPDATE'; state: MiniPlayerState }
  | { type: 'ACTION'; action: MiniPlayerAction };

async function invokeTauri<T>(cmd: string, args?: Record<string, unknown>): Promise<T | null> {
  try {
    if (typeof window !== 'undefined' && window.__TAURI__?.core?.invoke) {
      return await window.__TAURI__.core.invoke<T>(cmd, args);
    }
  } catch (err) {
    console.warn(`[Tauri] Error al invocar ${cmd}:`, err);
  }
  return null;
}

@Service()
export class MiniPlayerSyncService {
  private readonly audioPlayer = inject(AudioPlayerService);
  private channel: BroadcastChannel | null = null;

  // Window context flag
  readonly isMiniWindow = signal<boolean>(
    typeof window !== 'undefined' &&
      (window.location.pathname.includes('mini-player') || window.location.hash.includes('mini-player'))
  );

  // Status of the secondary window (for main player UI toggle/indicator)
  readonly isMiniPlayerOpen = signal<boolean>(false);

  // Synchronized Remote State Signals (used by the mini-player window)
  readonly track = signal<Track | null>(null);
  readonly coverUrl = signal<string | null>(null);
  readonly isPlaying = signal<boolean>(false);
  readonly currentTime = signal<number>(0);
  readonly duration = signal<number>(0);
  readonly volume = signal<number>(0.8);
  readonly isMuted = signal<boolean>(false);
  readonly hasNext = signal<boolean>(false);
  readonly hasPrevious = signal<boolean>(false);

  readonly progressPercent = computed(() => {
    const dur = this.duration();
    if (dur <= 0) return 0;
    return Math.min(100, (this.currentTime() / dur) * 100);
  });

  constructor() {
    this.initBroadcastChannel();

    if (this.isMiniWindow()) {
      // In mini window: request state from main player upon startup
      this.requestStateFromMain();
    } else {
      // In main window: set up reactive synchronization to broadcast changes
      this.setupMainBroadcastEffect();
      this.checkNativeMiniPlayerStatus();
    }
  }

  private initBroadcastChannel(): void {
    if (typeof BroadcastChannel !== 'undefined') {
      this.channel = new BroadcastChannel('melosync_mini_player_channel');
      this.channel.onmessage = (event: MessageEvent<MiniPlayerSyncMessage>) => {
        this.handleMessage(event.data);
      };
    }
  }

  private handleMessage(data: MiniPlayerSyncMessage): void {
    if (!data || !data.type) return;

    if (this.isMiniWindow()) {
      // Receive updates from the main window
      if (data.type === 'STATE_UPDATE') {
        const s = data.state;
        this.track.set(s.track);
        this.coverUrl.set(s.coverUrl);
        this.isPlaying.set(s.isPlaying);
        this.currentTime.set(s.currentTime);
        this.duration.set(s.duration);
        this.volume.set(s.volume);
        this.isMuted.set(s.isMuted);
        this.hasNext.set(s.hasNext);
        this.hasPrevious.set(s.hasPrevious);
      }
    } else {
      // Receive actions or requests from the mini window
      if (data.type === 'REQUEST_STATE') {
        this.broadcastCurrentState();
      } else if (data.type === 'ACTION') {
        this.executeActionFromMini(data.action);
      }
    }
  }

  private setupMainBroadcastEffect(): void {
    // Whenever player state changes in the main window, broadcast to mini player
    effect(() => {
      const state: MiniPlayerState = {
        track: this.audioPlayer.currentTrack(),
        coverUrl: this.audioPlayer.coverUrl(),
        isPlaying: this.audioPlayer.isPlaying(),
        currentTime: this.audioPlayer.currentTime(),
        duration: this.audioPlayer.duration(),
        volume: this.audioPlayer.volume(),
        isMuted: this.audioPlayer.isMuted(),
        hasNext: this.audioPlayer.hasNext(),
        hasPrevious: this.audioPlayer.hasPrevious()
      };

      untracked(() => {
        if (this.channel) {
          this.channel.postMessage({
            type: 'STATE_UPDATE',
            state
          });
        }
      });
    });
  }

  private broadcastCurrentState(): void {
    if (!this.channel) return;
    const state: MiniPlayerState = {
      track: this.audioPlayer.currentTrack(),
      coverUrl: this.audioPlayer.coverUrl(),
      isPlaying: this.audioPlayer.isPlaying(),
      currentTime: this.audioPlayer.currentTime(),
      duration: this.audioPlayer.duration(),
      volume: this.audioPlayer.volume(),
      isMuted: this.audioPlayer.isMuted(),
      hasNext: this.audioPlayer.hasNext(),
      hasPrevious: this.audioPlayer.hasPrevious()
    };
    this.channel.postMessage({
      type: 'STATE_UPDATE',
      state
    });
  }

  private executeActionFromMini(action: MiniPlayerAction): void {
    switch (action.type) {
      case 'TOGGLE_PLAY':
        this.audioPlayer.togglePlay();
        break;
      case 'NEXT':
        this.audioPlayer.playNext();
        break;
      case 'PREVIOUS':
        this.audioPlayer.playPrevious();
        break;
      case 'SEEK':
        this.audioPlayer.seek(action.time);
        break;
      case 'SET_VOLUME':
        this.audioPlayer.setVolume(action.volume);
        break;
      case 'CLOSE':
        this.closeMiniPlayer();
        break;
      case 'RESTORE_MAIN':
        this.focusMainWindow();
        break;
    }
  }

  private dispatchAction(action: MiniPlayerAction): void {
    if (this.channel) {
      this.channel.postMessage({
        type: 'ACTION',
        action
      });
    }
  }

  // --- Public Action Methods (Called from Mini Player UI) ---
  togglePlay(): void {
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'TOGGLE_PLAY' });
    } else {
      this.audioPlayer.togglePlay();
    }
  }

  playNext(): void {
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'NEXT' });
    } else {
      this.audioPlayer.playNext();
    }
  }

  playPrevious(): void {
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'PREVIOUS' });
    } else {
      this.audioPlayer.playPrevious();
    }
  }

  seek(seconds: number): void {
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'SEEK', time: seconds });
    } else {
      this.audioPlayer.seek(seconds);
    }
  }

  seekPercent(percent: number): void {
    const dur = this.duration();
    if (dur > 0) {
      const targetSec = (percent / 100) * dur;
      this.seek(targetSec);
    }
  }

  setVolume(vol: number): void {
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'SET_VOLUME', volume: vol });
    } else {
      this.audioPlayer.setVolume(vol);
    }
  }

  requestStateFromMain(): void {
    if (this.channel) {
      this.channel.postMessage({ type: 'REQUEST_STATE' });
    }
  }

  // --- Window Control Methods (Tauri integration with browser fallbacks) ---
  async toggleMiniPlayer(): Promise<void> {
    const res = await invokeTauri<boolean>('toggle_mini_player');
    if (res !== null) {
      this.isMiniPlayerOpen.set(res);
      if (res) {
        this.broadcastCurrentState();
      }
    } else {
      // Fallback for browser mode during development / testing
      const opened = !this.isMiniPlayerOpen();
      this.isMiniPlayerOpen.set(opened);
      if (opened) {
        window.open('/mini-player', 'meloSyncMiniPlayer', 'width=320,height=320,resizable=yes');
        this.broadcastCurrentState();
      }
    }
  }

  async closeMiniPlayer(): Promise<void> {
    this.isMiniPlayerOpen.set(false);
    await invokeTauri('close_mini_player');
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'CLOSE' });
    }
  }

  async focusMainWindow(): Promise<void> {
    await invokeTauri('focus_main_window');
    if (this.isMiniWindow()) {
      this.dispatchAction({ type: 'RESTORE_MAIN' });
    }
  }

  async startDragging(): Promise<void> {
    try {
      const w = window as unknown as {
        __TAURI_INTERNALS__?: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };
      };
      if (w.__TAURI_INTERNALS__?.invoke) {
        await w.__TAURI_INTERNALS__.invoke('plugin:window|start_dragging');
        return;
      }
    } catch {}
    await invokeTauri('start_dragging_window');
  }

  async checkNativeMiniPlayerStatus(): Promise<void> {
    const res = await invokeTauri<boolean>('is_mini_player_open');
    if (res !== null) {
      this.isMiniPlayerOpen.set(res);
    }
  }
}

