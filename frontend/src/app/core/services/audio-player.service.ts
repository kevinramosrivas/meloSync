import { Service, signal, computed, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Track } from '../../domain/models';
import { API_CONFIG } from '../config/api.config';
import { ToastService } from './toast.service';
import { UserPreferencesService } from './user-preferences.service';
import { REPEAT_MODES, RepeatMode, USER_PREFERENCE_KEYS } from '../constants/preferences.constants';

@Service()
export class AudioPlayerService {
  private readonly http = inject(HttpClient);
  private readonly toast = inject(ToastService);
  private readonly preferences = inject(UserPreferencesService);
  private audio: HTMLAudioElement;

  // Reactive State Signals
  readonly currentTrack = signal<Track | null>(null);
  readonly isPlaying = signal<boolean>(false);
  readonly currentTime = signal<number>(0);
  readonly duration = signal<number>(0);
  readonly volume = signal<number>(0.8);
  readonly isMuted = signal<boolean>(false);
  readonly playlist = signal<Track[]>([]);
  readonly activePlaylistId = signal<string | null>(null);
  readonly repeatMode = signal<RepeatMode>(this.preferences.repeatMode());
  readonly isShuffle = signal<boolean>(this.preferences.shuffleEnabled());

  // Shuffle queue deck state (Fisher-Yates ordered permutation)
  private shuffledPlaylist: Track[] = [];
  readonly shuffleIndex = signal<number>(-1);

  // Play history tracking flag (prevents duplicate play counting for the same listening session)
  private playRecordedForCurrentTrack = false;

  // Computed Properties
  readonly currentIndex = computed(() => {
    const current = this.currentTrack();
    const list = this.playlist();
    if (!current || list.length === 0) return -1;
    return list.findIndex(t => t.id === current.id);
  });

  readonly queueCount = computed(() => this.playlist().length);

  readonly hasNext = computed(() => {
    const queue = this.playlist();
    const count = queue.length;
    if (count <= 1) return false;
    if (this.repeatMode() === REPEAT_MODES.ALL) return true;
    if (this.isShuffle()) {
      return this.shuffleIndex() < count - 1;
    }
    const idx = this.currentIndex();
    return idx >= 0 && idx < count - 1;
  });

  readonly hasPrevious = computed(() => {
    const queue = this.playlist();
    const count = queue.length;
    if (count <= 1) return false;
    if (this.repeatMode() === REPEAT_MODES.ALL) return true;
    if (this.isShuffle()) {
      return this.shuffleIndex() > 0;
    }
    const idx = this.currentIndex();
    return idx > 0;
  });

  readonly progressPercent = computed(() => {
    const dur = this.duration();
    if (dur <= 0) return 0;
    return Math.min(100, (this.currentTime() / dur) * 100);
  });

  readonly coverUrl = computed(() => {
    const track = this.currentTrack();
    if (!track) return null;
    if (track.metadata?.has_cover_bytes) {
      return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.cover(track.id)}?t=${track.updated_at_iso || ''}`;
    }
    if (track.metadata?.cover_url) {
      return track.metadata.cover_url;
    }
    return null;
  });

  constructor() {
    this.audio = new Audio();
    this.audio.volume = this.volume();
    this.setupAudioListeners();
    this.setupMediaSession();
  }

  private setupAudioListeners(): void {
    this.audio.ontimeupdate = () => {
      this.currentTime.set(this.audio.currentTime);
      this.updateMediaSessionPosition();
      this.checkAndRecordPlay();
    };

    this.audio.onloadedmetadata = () => {
      const dur = this.audio.duration || this.currentTrack()?.duration_seconds || 0;
      this.duration.set(dur);
      this.updateMediaSessionPosition();
    };

    this.audio.onplay = () => {
      this.isPlaying.set(true);
      this.updateMediaSessionPlaybackState(true);
      this.updateDocumentTitle();
    };

    this.audio.onpause = () => {
      this.isPlaying.set(false);
      this.updateMediaSessionPlaybackState(false);
      this.updateDocumentTitle();
    };

    this.audio.onended = () => {
      this.isPlaying.set(false);
      this.updateMediaSessionPlaybackState(false);
      this.recordPlayCurrentTrack();
      this.handleTrackEnded();
    };

    this.audio.onerror = () => {
      this.isPlaying.set(false);
      this.updateMediaSessionPlaybackState(false);
      const trackName = this.currentTrack()?.display_title || 'la pista';
      this.toast.error(
        'Error de reproducción',
        `No se pudo reproducir "${trackName}". Verifica el archivo o sincroniza la carpeta de música.`
      );
    };
  }

  private checkAndRecordPlay(): void {
    if (this.playRecordedForCurrentTrack) return;
    const track = this.currentTrack();
    if (!track) return;

    // Industry standard: count play after 30 seconds of continuous listening
    if (this.audio.currentTime >= 30) {
      this.recordPlayCurrentTrack();
    }
  }

  private recordPlayCurrentTrack(): void {
    if (this.playRecordedForCurrentTrack) return;
    const track = this.currentTrack();
    if (!track) return;

    this.playRecordedForCurrentTrack = true;
    const url = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.recordPlay(track.id)}`;
    this.http.post(url, {}).subscribe({
      error: (err) => console.debug('record-play silent notice', err)
    });
  }

  playPlaylist(playlistId: string, tracks: Track[], startIndex: number = 0): void {
    if (!tracks || tracks.length === 0) return;
    const safeIdx = Math.max(0, Math.min(startIndex, tracks.length - 1));
    this.activePlaylistId.set(playlistId);
    this.playTrack(tracks[safeIdx], tracks, playlistId);
  }

  playTrack(track: Track, playlistQueue: Track[] = [], playlistId?: string | null): void {
    if (playlistId !== undefined) {
      this.activePlaylistId.set(playlistId);
    } else if (playlistQueue.length > 0) {
      this.activePlaylistId.set(null);
    }

    if (playlistQueue.length > 0) {
      this.playlist.set(playlistQueue);
      if (this.isShuffle()) {
        this.buildShuffledQueue(track);
      }
    } else if (this.playlist().length === 0 || !this.playlist().some(t => t.id === track.id)) {
      this.playlist.set([track]);
      this.shuffledPlaylist = [track];
      this.shuffleIndex.set(0);
    } else if (this.isShuffle()) {
      const idx = this.shuffledPlaylist.findIndex(t => t.id === track.id);
      if (idx >= 0) {
        this.shuffleIndex.set(idx);
      } else {
        this.buildShuffledQueue(track);
      }
    }

    this.playRecordedForCurrentTrack = false;
    this.currentTrack.set(track);
    const streamUrl = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.stream(track.id)}`;
    this.audio.src = streamUrl;
    this.audio.load();

    this.updateMediaSessionMetadata(track);
    this.updateDocumentTitle();

    this.audio.play().catch((err) => {
      this.isPlaying.set(false);
      this.updateMediaSessionPlaybackState(false);
      if (err?.name !== 'AbortError') {
        this.toast.error(
          'Error al reproducir',
          'No se pudo iniciar el audio. Sincroniza la biblioteca si el archivo fue movido.'
        );
      }
    });
  }

  togglePlay(): void {
    if (!this.currentTrack()) return;
    if (this.isPlaying()) {
      this.audio.pause();
    } else {
      this.audio.play().catch(() => {});
    }
  }

  stop(): void {
    if (this.audio) {
      this.audio.pause();
      this.audio.currentTime = 0;
    }
    this.isPlaying.set(false);
    this.currentTime.set(0);
    this.updateMediaSessionPlaybackState(false);
    this.updateDocumentTitle();
  }

  seek(seconds: number): void {
    if (this.audio && isFinite(seconds)) {
      this.audio.currentTime = seconds;
      this.currentTime.set(seconds);
      this.updateMediaSessionPosition();
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
    const clamped = Math.max(0, Math.min(1, vol));
    this.volume.set(clamped);
    this.audio.volume = clamped;
    if (clamped > 0 && this.isMuted()) {
      this.isMuted.set(false);
    }
  }

  toggleMute(): void {
    if (this.isMuted()) {
      this.audio.volume = this.volume();
      this.isMuted.set(false);
    } else {
      this.audio.volume = 0;
      this.isMuted.set(true);
    }
  }

  toggleShuffle(): void {
    const next = !this.isShuffle();
    this.isShuffle.set(next);
    this.preferences.set(USER_PREFERENCE_KEYS.SHUFFLE_ENABLED, next);
    if (next) {
      this.buildShuffledQueue(this.currentTrack());
    }
  }

  cycleRepeatMode(): void {
    const current = this.repeatMode();
    let next: RepeatMode = REPEAT_MODES.OFF;
    if (current === REPEAT_MODES.OFF) {
      next = REPEAT_MODES.ALL;
    } else if (current === REPEAT_MODES.ALL) {
      next = REPEAT_MODES.ONE;
    } else {
      next = REPEAT_MODES.OFF;
    }
    this.setRepeatMode(next);
  }

  setRepeatMode(mode: RepeatMode): void {
    this.repeatMode.set(mode);
    this.preferences.set(USER_PREFERENCE_KEYS.REPEAT_MODE, mode);
  }

  setPlaylist(tracks: Track[]): void {
    this.playlist.set(tracks);
    if (this.isShuffle()) {
      this.buildShuffledQueue(this.currentTrack());
    }
  }

  clearQueue(): void {
    const current = this.currentTrack();
    this.playlist.set(current ? [current] : []);
    this.shuffledPlaylist = current ? [current] : [];
    this.shuffleIndex.set(current ? 0 : -1);
  }

  private handleTrackEnded(): void {
    if (this.repeatMode() === REPEAT_MODES.ONE) {
      this.seek(0);
      this.audio.play().catch(() => {});
      return;
    }
    this.playNext();
  }

  playNext(): void {
    const queue = this.playlist();
    const current = this.currentTrack();
    if (!current || queue.length === 0) return;

    if (this.repeatMode() === REPEAT_MODES.ONE) {
      this.seek(0);
      this.audio.play().catch(() => {});
      return;
    }

    if (this.isShuffle() && queue.length > 1) {
      if (this.shuffledPlaylist.length !== queue.length) {
        this.buildShuffledQueue(current);
      }

      const sIdx = this.shuffleIndex();
      if (sIdx >= 0 && sIdx < this.shuffledPlaylist.length - 1) {
        const nextIdx = sIdx + 1;
        this.shuffleIndex.set(nextIdx);
        this.playTrack(this.shuffledPlaylist[nextIdx]);
        return;
      } else if (this.repeatMode() === REPEAT_MODES.ALL) {
        // Full deck completed; create a fresh shuffle cycle
        this.buildShuffledQueue(null);
        this.shuffleIndex.set(0);
        this.playTrack(this.shuffledPlaylist[0]);
        return;
      } else {
        // Reached end of shuffled queue with repeat OFF
        this.audio.pause();
        this.isPlaying.set(false);
        this.seek(0);
        return;
      }
    }

    // Normal sequential playback
    const currentIndex = queue.findIndex(t => t.id === current.id);
    if (currentIndex >= 0 && currentIndex < queue.length - 1) {
      this.playTrack(queue[currentIndex + 1]);
    } else if (this.repeatMode() === REPEAT_MODES.ALL && queue.length > 0) {
      this.playTrack(queue[0]);
    } else {
      // Reached the end with repeat OFF
      this.audio.pause();
      this.isPlaying.set(false);
      this.seek(0);
    }
  }

  playPrevious(): void {
    const queue = this.playlist();
    const current = this.currentTrack();
    if (!current || queue.length === 0) return;

    // Industry standard: if played for more than 3s, rewind to start
    if (this.currentTime() > 3) {
      this.seek(0);
      return;
    }

    if (this.isShuffle() && queue.length > 1) {
      if (this.shuffledPlaylist.length !== queue.length) {
        this.buildShuffledQueue(current);
      }

      const sIdx = this.shuffleIndex();
      if (sIdx > 0) {
        const prevIdx = sIdx - 1;
        this.shuffleIndex.set(prevIdx);
        this.playTrack(this.shuffledPlaylist[prevIdx]);
        return;
      } else if (this.repeatMode() === REPEAT_MODES.ALL) {
        const lastIdx = this.shuffledPlaylist.length - 1;
        this.shuffleIndex.set(lastIdx);
        this.playTrack(this.shuffledPlaylist[lastIdx]);
        return;
      } else {
        this.seek(0);
        return;
      }
    }

    // Normal sequential previous
    const currentIndex = queue.findIndex(t => t.id === current.id);
    if (currentIndex > 0) {
      this.playTrack(queue[currentIndex - 1]);
    } else if (this.repeatMode() === REPEAT_MODES.ALL && queue.length > 0) {
      this.playTrack(queue[queue.length - 1]);
    } else {
      this.seek(0);
    }
  }

  private buildShuffledQueue(currentTrack: Track | null): void {
    const original = [...this.playlist()];
    if (original.length <= 1) {
      this.shuffledPlaylist = original;
      this.shuffleIndex.set(original.length > 0 ? 0 : -1);
      return;
    }

    let pool: Track[];
    if (currentTrack && original.some(t => t.id === currentTrack.id)) {
      pool = original.filter(t => t.id !== currentTrack.id);
      // Fisher-Yates shuffle
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
      }
      this.shuffledPlaylist = [currentTrack, ...pool];
      this.shuffleIndex.set(0);
    } else {
      pool = [...original];
      for (let i = pool.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [pool[i], pool[j]] = [pool[j], pool[i]];
      }
      this.shuffledPlaylist = pool;
      this.shuffleIndex.set(0);
    }
  }

  // --- W3C Media Session API (Windows SMTC & Media Keys) ---

  private setupMediaSession(): void {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;

    try {
      navigator.mediaSession.setActionHandler('play', () => this.togglePlay());
      navigator.mediaSession.setActionHandler('pause', () => this.togglePlay());
      navigator.mediaSession.setActionHandler('previoustrack', () => this.playPrevious());
      navigator.mediaSession.setActionHandler('nexttrack', () => this.playNext());
      navigator.mediaSession.setActionHandler('seekto', (details) => {
        if (details.seekTime !== undefined) this.seek(details.seekTime);
      });
      navigator.mediaSession.setActionHandler('seekbackward', (details) => {
        const skip = details.seekOffset || 10;
        this.seek(Math.max(this.currentTime() - skip, 0));
      });
      navigator.mediaSession.setActionHandler('seekforward', (details) => {
        const skip = details.seekOffset || 10;
        this.seek(Math.min(this.currentTime() + skip, this.duration()));
      });
      navigator.mediaSession.setActionHandler('stop', () => this.stop());
    } catch (e) {
      console.warn('No se pudieron configurar todos los handlers de MediaSession:', e);
    }
  }

  private updateMediaSessionMetadata(track: Track): void {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;

    try {
      const origin = typeof window !== 'undefined' ? window.location.origin : '';
      const fallbackIcon = `${origin}/icon.png`;
      const cover = this.coverUrl();

      const artwork: MediaImage[] = cover
        ? [
            { src: cover, sizes: '512x512', type: 'image/jpeg' },
            { src: cover, sizes: '256x256', type: 'image/jpeg' },
            { src: cover, sizes: '128x128', type: 'image/jpeg' }
          ]
        : [
            { src: fallbackIcon, sizes: '512x512', type: 'image/png' },
            { src: `${origin}/logo.svg`, sizes: '512x512', type: 'image/svg+xml' }
          ];

      const metadataPayload = {
        title: track.display_title || track.original_title || 'Pista desconocida',
        artist: track.display_artist || track.metadata?.artist || 'meloSync',
        album: track.display_album || track.metadata?.album || 'meloSync',
        artwork
      };

      navigator.mediaSession.metadata =
        typeof MediaMetadata !== 'undefined'
          ? new MediaMetadata(metadataPayload)
          : (metadataPayload as any);
    } catch (e) {
      console.warn('Error al actualizar MediaMetadata:', e);
    }
  }

  private updateMediaSessionPlaybackState(playing: boolean): void {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;
    try {
      navigator.mediaSession.playbackState = playing ? 'playing' : 'paused';
    } catch {
      // Ignore unsupported state exceptions
    }
  }

  private updateMediaSessionPosition(): void {
    if (typeof navigator === 'undefined' || !('mediaSession' in navigator)) return;
    if ('setPositionState' in navigator.mediaSession && this.duration() > 0) {
      try {
        navigator.mediaSession.setPositionState({
          duration: this.duration(),
          playbackRate: this.audio.playbackRate || 1.0,
          position: Math.min(this.currentTime(), this.duration())
        });
      } catch {
        // Silently ignore timing discrepancies during seek
      }
    }
  }

  private updateDocumentTitle(): void {
    if (typeof document === 'undefined') return;
    const track = this.currentTrack();
    if (track && this.isPlaying()) {
      document.title = `${track.display_title || 'Reproduciendo'} • ${track.display_artist || 'meloSync'} — meloSync`;
    } else {
      document.title = 'meloSync';
    }
  }
}
