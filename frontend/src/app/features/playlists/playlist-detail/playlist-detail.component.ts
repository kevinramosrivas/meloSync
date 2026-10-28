import { Component, OnInit, computed, effect, inject, input, signal } from '@angular/core';
import { Router } from '@angular/router';
import { PlaylistsApiService } from '../../../data/playlists-api.service';
import { PlaylistsStore } from '../../../core/stores/playlists.store';
import { LibraryApiService } from '../../../data/library-api.service';
import { Playlist, Track } from '../../../domain/models';
import { AudioPlayerService } from '../../../core/services/audio-player.service';
import { ToastService } from '../../../core/services/toast.service';
import { API_CONFIG } from '../../../core/config/api.config';
import { IconComponent } from '../../../shared/components/icon/icon.component';
import { EqualizerIndicatorComponent } from '../../../shared/components/equalizer-indicator/equalizer-indicator.component';
import { CreatePlaylistDialogComponent } from '../components/create-playlist-dialog/create-playlist-dialog.component';
import { AddToPlaylistDialogComponent } from '../../library/components/add-to-playlist-dialog/add-to-playlist-dialog.component';
import { TrackRowComponent } from '../../../shared/components/track-row/track-row.component';

@Component({
  selector: 'app-playlist-detail',
  imports: [
    IconComponent,
    EqualizerIndicatorComponent,
    CreatePlaylistDialogComponent,
    AddToPlaylistDialogComponent,
    TrackRowComponent,
  ],
  templateUrl: './playlist-detail.component.html',
})
export class PlaylistDetailComponent implements OnInit {
  private readonly playlistsApi = inject(PlaylistsApiService);
  private readonly playlistsStore = inject(PlaylistsStore);
  private readonly libraryApi = inject(LibraryApiService);
  readonly player = inject(AudioPlayerService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  readonly id = input.required<string>();

  readonly playlist = signal<Playlist | null>(null);
  readonly isLoading = signal(true);
  readonly isEditModalOpen = signal(false);

  // Add to another playlist modal state
  readonly selectedTrackForPlaylist = signal<Track | null>(null);
  readonly isAddToPlaylistOpen = signal(false);

  readonly isPlaylistActive = computed(() => this.player.activePlaylistId() === this.id());
  readonly isPlaylistPlaying = computed(() => this.isPlaylistActive() && this.player.isPlaying());

  readonly isBioExpanded = signal(false);

  readonly artistBio = computed(() => {
    const p = this.playlist();
    if (!p || p.playlist_type !== 'artist' || !p.description) return null;
    if (p.description.startsWith('Todas tus canciones')) return null;
    return p.description;
  });

  readonly artistName = computed(() => {
    const p = this.playlist();
    if (!p) return '';
    return p.filter_query || p.name.replace(/^Mix de\s+/i, '').trim();
  });

  toggleBio(): void {
    this.isBioExpanded.update((v) => !v);
  }

  constructor() {
    effect(() => {
      const currentId = this.id();
      if (currentId) {
        this.loadPlaylist();
      }
    });
  }

  ngOnInit(): void {
    this.loadPlaylist();
  }

  loadPlaylist(): void {
    const playlistId = this.id();
    if (!playlistId) return;

    this.isLoading.set(true);
    this.playlistsApi.getPlaylist(playlistId).subscribe({
      next: (data) => {
        this.playlist.set(data);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.toast.error('Error al cargar', 'No se pudo cargar la información de la playlist.');
        this.router.navigate(['/playlists']);
      },
    });
  }

  goBack(): void {
    this.router.navigate(['/playlists']);
  }

  playAll(): void {
    const p = this.playlist();
    if (!p || !p.tracks || p.tracks.length === 0) {
      this.toast.info('Lista vacía', 'No hay canciones en esta lista para reproducir.');
      return;
    }
    if (this.isPlaylistActive()) {
      this.player.togglePlay();
      return;
    }
    this.player.playPlaylist(p.id, p.tracks, 0);
  }

  shufflePlay(): void {
    const p = this.playlist();
    if (!p || !p.tracks || p.tracks.length === 0) {
      this.toast.info('Lista vacía', 'No hay canciones para reproducir.');
      return;
    }
    if (!this.player.isShuffle()) {
      this.player.toggleShuffle();
    }
    // Random pick to start
    const randIdx = Math.floor(Math.random() * p.tracks.length);
    this.player.playPlaylist(p.id, p.tracks, randIdx);
  }

  playTrack(track: Track): void {
    const p = this.playlist();
    const queue = p?.tracks || [track];
    const idx = queue.findIndex((t) => t.id === track.id);
    this.player.playPlaylist(p?.id || this.id(), queue, idx >= 0 ? idx : 0);
  }

  openAddToPlaylist(data: { track: Track; event: Event }): void {
    this.selectedTrackForPlaylist.set(data.track);
    this.isAddToPlaylistOpen.set(true);
  }

  removeTrack(track: Track): void {
    const p = this.playlist();
    if (!p || p.is_smart) return;

    this.playlistsApi.removeTrackFromPlaylist(p.id, track.id).subscribe({
      next: (updated) => {
        this.playlist.set(updated);
        this.playlistsStore.load(true);
        this.toast.success('Pista eliminada', `"${track.display_title}" fue quitada de la lista.`);
      },
      error: () => {
        this.toast.error('Error', 'No se pudo quitar la pista de la lista.');
      },
    });
  }

  openFolder(trackId: string): void {
    this.libraryApi.openContainingFolder(trackId).subscribe({
      error: () => {
        this.toast.error('Error', 'No se pudo abrir la carpeta en el explorador.');
      },
    });
  }

  openEditModal(): void {
    this.isEditModalOpen.set(true);
  }

  onSavePlaylist(payload: { id?: string; name: string; description: string }): void {
    const p = this.playlist();
    if (!p) return;

    this.isEditModalOpen.set(false);
    this.playlistsApi.updatePlaylist(p.id, { name: payload.name, description: payload.description }).subscribe({
      next: (updated) => {
        this.playlist.set(updated);
        this.playlistsStore.load(true);
        this.toast.success('Lista actualizada', 'Los cambios han sido guardados.');
      },
      error: () => {
        this.toast.error('Error', 'No se pudo actualizar la lista.');
      },
    });
  }

  deletePlaylist(): void {
    const p = this.playlist();
    if (!p || p.is_smart) return;

    if (!confirm(`¿Deseas eliminar la lista "${p.name}" permanentemente?`)) return;

    this.playlistsApi.deletePlaylist(p.id).subscribe({
      next: () => {
        this.playlistsStore.load(true);
        this.toast.success('Lista eliminada', `"${p.name}" fue eliminada.`);
        this.router.navigate(['/playlists']);
      },
      error: () => {
        this.toast.error('Error', 'No se pudo eliminar la lista.');
      },
    });
  }

  getCoverUrl(trackId: string): string {
    return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.cover(trackId)}`;
  }

  formatDuration(seconds: number): string {
    if (!seconds || seconds <= 0) return '0 min';
    const mins = Math.floor(seconds / 60);
    const hrs = Math.floor(mins / 60);
    const remMins = mins % 60;
    if (hrs > 0) {
      return `${hrs} h ${remMins} min`;
    }
    return `${mins} min`;
  }

  isTrackPlaying(track: Track): boolean {
    return this.player.currentTrack()?.id === track.id && this.player.isPlaying();
  }

  getTypeBadge(type: string): { label: string; bgClass: string; textClass: string } {
    switch (type) {
      case 'top_played':
        return { label: 'TOP RANKING', bgClass: 'bg-rose-500/20 border-rose-500/30', textClass: 'text-rose-300' };
      case 'on_repeat':
        return { label: 'HÁBITO RECIENTE', bgClass: 'bg-emerald-500/20 border-emerald-500/30', textClass: 'text-emerald-300' };
      case 'artist':
        return { label: 'MIX DE ARTISTA', bgClass: 'bg-indigo-500/20 border-indigo-500/30', textClass: 'text-indigo-300' };
      case 'genre':
        return { label: 'MIX DE GÉNERO', bgClass: 'bg-purple-500/20 border-purple-500/30', textClass: 'text-purple-300' };
      default:
        return { label: 'LISTA PERSONAL', bgClass: 'bg-white/[0.08] border-white/[0.12]', textClass: 'text-zinc-200' };
    }
  }
}
