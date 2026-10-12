import { Injectable, signal, computed, effect, inject } from '@angular/core';
import { Track } from '../../domain/models';
import { API_CONFIG } from '../config/api.config';
import { ToastService } from './toast.service';

@Injectable({
  providedIn: 'root'
})
export class AudioPlayerService {
  private toast = inject(ToastService);
  private audio: HTMLAudioElement;

  // Reactive State Signals
  readonly currentTrack = signal<Track | null>(null);
  readonly isPlaying = signal<boolean>(false);
  readonly currentTime = signal<number>(0);
  readonly duration = signal<number>(0);
  readonly volume = signal<number>(0.8);
  readonly isMuted = signal<boolean>(false);
  readonly playlist = signal<Track[]>([]);

  // Computed Properties
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
  }

  private setupAudioListeners(): void {
    this.audio.ontimeupdate = () => {
      this.currentTime.set(this.audio.currentTime);
    };

    this.audio.onloadedmetadata = () => {
      this.duration.set(this.audio.duration || this.currentTrack()?.duration_seconds || 0);
    };

    this.audio.onplay = () => {
      this.isPlaying.set(true);
    };

    this.audio.onpause = () => {
      this.isPlaying.set(false);
    };

    this.audio.onended = () => {
      this.isPlaying.set(false);
      this.playNext();
    };

    this.audio.onerror = () => {
      this.isPlaying.set(false);
      const trackName = this.currentTrack()?.display_title || 'la pista';
      this.toast.error(
        'Error de reproducción',
        `No se pudo reproducir "${trackName}". Verifica el archivo o sincroniza la carpeta de música.`
      );
    };
  }

  playTrack(track: Track, playlistQueue: Track[] = []): void {
    if (playlistQueue.length > 0) {
      this.playlist.set(playlistQueue);
    }
    this.currentTrack.set(track);
    const streamUrl = `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.stream(track.id)}`;
    this.audio.src = streamUrl;
    this.audio.load();
    this.audio.play().catch((err) => {
      this.isPlaying.set(false);
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

  seek(seconds: number): void {
    if (this.audio && isFinite(seconds)) {
      this.audio.currentTime = seconds;
      this.currentTime.set(seconds);
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

  playNext(): void {
    const queue = this.playlist();
    const current = this.currentTrack();
    if (!current || queue.length === 0) return;

    const currentIndex = queue.findIndex(t => t.id === current.id);
    if (currentIndex >= 0 && currentIndex < queue.length - 1) {
      this.playTrack(queue[currentIndex + 1]);
    }
  }

  playPrevious(): void {
    const queue = this.playlist();
    const current = this.currentTrack();
    if (!current || queue.length === 0) return;

    if (this.currentTime() > 3) {
      this.seek(0);
      return;
    }

    const currentIndex = queue.findIndex(t => t.id === current.id);
    if (currentIndex > 0) {
      this.playTrack(queue[currentIndex - 1]);
    }
  }
}
