import { Component, OnInit, inject, signal, computed } from '@angular/core';
import { Router } from '@angular/router';
import { FormsModule } from '@angular/forms';
import { PlaylistsApiService } from '../../data/playlists-api.service';
import { PlaylistSummary } from '../../domain/models';
import { AudioPlayerService } from '../../core/services/audio-player.service';
import { ToastService } from '../../core/services/toast.service';
import { API_CONFIG } from '../../core/config/api.config';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { EqualizerIndicatorComponent } from '../../shared/components/equalizer-indicator/equalizer-indicator.component';
import { CreatePlaylistDialogComponent } from './components/create-playlist-dialog/create-playlist-dialog.component';

export type PlaylistCategoryTab = 'all' | 'user' | 'artist' | 'genre' | 'for_you';

@Component({
  selector: 'app-playlists',
  imports: [FormsModule, IconComponent, EqualizerIndicatorComponent, CreatePlaylistDialogComponent],
  templateUrl: './playlists.component.html',
})
export class PlaylistsComponent implements OnInit {
  private readonly playlistsApi = inject(PlaylistsApiService);
  readonly player = inject(AudioPlayerService);
  private readonly router = inject(Router);
  private readonly toast = inject(ToastService);

  readonly userPlaylists = signal<PlaylistSummary[]>([]);
  readonly forYouPlaylists = signal<PlaylistSummary[]>([]);
  readonly artistPlaylists = signal<PlaylistSummary[]>([]);
  readonly genrePlaylists = signal<PlaylistSummary[]>([]);
  readonly isLoading = signal(true);
  readonly isSyncing = signal(false);

  // Search & Filter State
  readonly searchQuery = signal<string>('');
  readonly activeCategory = signal<PlaylistCategoryTab>('all');

  // Filtered Computed Signals
  readonly filteredUserPlaylists = computed(() => {
    const q = this.searchQuery();
    return this.userPlaylists().filter((p) => this.matchesQuery(p, q));
  });

  readonly filteredForYouPlaylists = computed(() => {
    const q = this.searchQuery();
    return this.forYouPlaylists().filter((p) => this.matchesQuery(p, q));
  });

  readonly filteredArtistPlaylists = computed(() => {
    const q = this.searchQuery();
    return this.artistPlaylists().filter((p) => this.matchesQuery(p, q));
  });

  readonly filteredGenrePlaylists = computed(() => {
    const q = this.searchQuery();
    return this.genrePlaylists().filter((p) => this.matchesQuery(p, q));
  });

  readonly totalFilteredCount = computed(() => {
    let count = 0;
    const cat = this.activeCategory();
    if (cat === 'all' || cat === 'user') count += this.filteredUserPlaylists().length;
    if (cat === 'all' || cat === 'for_you') count += this.filteredForYouPlaylists().length;
    if (cat === 'all' || cat === 'artist') count += this.filteredArtistPlaylists().length;
    if (cat === 'all' || cat === 'genre') count += this.filteredGenrePlaylists().length;
    return count;
  });

  readonly totalAllCount = computed(() => {
    return (
      this.userPlaylists().length +
      this.forYouPlaylists().length +
      this.artistPlaylists().length +
      this.genrePlaylists().length
    );
  });

  // Dialog State
  readonly isCreateModalOpen = signal(false);
  readonly editingPlaylist = signal<PlaylistSummary | null>(null);
  readonly activeMenuId = signal<string | null>(null);

  private matchesQuery(p: PlaylistSummary, q: string): boolean {
    if (!q || !q.trim()) return true;
    const lower = q.toLowerCase().trim();
    const nameMatch = p.name.toLowerCase().includes(lower);
    const filterMatch = p.filter_query ? p.filter_query.toLowerCase().includes(lower) : false;
    const descMatch = p.description ? p.description.toLowerCase().includes(lower) : false;
    return nameMatch || filterMatch || descMatch;
  }

  clearSearch(): void {
    this.searchQuery.set('');
  }

  setCategory(cat: PlaylistCategoryTab): void {
    this.activeCategory.set(cat);
  }

  ngOnInit(): void {
    this.loadPlaylists();
  }

  loadPlaylists(): void {
    this.isLoading.set(true);
    this.playlistsApi.getPlaylists().subscribe({
      next: (resp) => {
        this.userPlaylists.set(resp.user_playlists);
        this.forYouPlaylists.set(resp.for_you_playlists);
        this.artistPlaylists.set(resp.artist_playlists);
        this.genrePlaylists.set(resp.genre_playlists);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.toast.error('Error al cargar', 'No se pudieron recuperar las listas de reproducción.');
      },
    });
  }

  syncSmartPlaylists(): void {
    this.isSyncing.set(true);
    this.playlistsApi.syncSmartPlaylists().subscribe({
      next: () => {
        this.isSyncing.set(false);
        this.toast.success('Listas actualizadas', 'Los mixes inteligentes fueron sincronizados con tu biblioteca.');
        this.loadPlaylists();
      },
      error: () => {
        this.isSyncing.set(false);
        this.toast.error('Error', 'No se pudo sincronizar en este momento.');
      },
    });
  }

  openCreateModal(): void {
    this.editingPlaylist.set(null);
    this.isCreateModalOpen.set(true);
  }

  openEditModal(p: PlaylistSummary, event: Event): void {
    event.stopPropagation();
    this.activeMenuId.set(null);
    this.editingPlaylist.set(p);
    this.isCreateModalOpen.set(true);
  }

  onSavePlaylist(payload: { id?: string; name: string; description: string }): void {
    this.isCreateModalOpen.set(false);
    if (payload.id) {
      // Update
      this.playlistsApi.updatePlaylist(payload.id, { name: payload.name, description: payload.description }).subscribe({
        next: () => {
          this.toast.success('Lista actualizada', `Se guardaron los cambios para "${payload.name}".`);
          this.loadPlaylists();
        },
        error: () => {
          this.toast.error('Error', 'No se pudo actualizar la lista.');
        },
      });
    } else {
      // Create
      this.playlistsApi.createPlaylist({ name: payload.name, description: payload.description }).subscribe({
        next: (created) => {
          this.toast.success('Lista creada', `"${created.name}" fue creada con éxito.`);
          this.loadPlaylists();
        },
        error: () => {
          this.toast.error('Error', 'No se pudo crear la lista.');
        },
      });
    }
  }

  deletePlaylist(p: PlaylistSummary, event: Event): void {
    event.stopPropagation();
    this.activeMenuId.set(null);
    if (!confirm(`¿Estás seguro de que deseas eliminar la lista "${p.name}"?`)) return;

    this.playlistsApi.deletePlaylist(p.id).subscribe({
      next: () => {
        this.toast.success('Lista eliminada', `"${p.name}" fue eliminada.`);
        this.loadPlaylists();
      },
      error: () => {
        this.toast.error('Error', 'No se pudo eliminar la lista.');
      },
    });
  }

  toggleMenu(id: string, event: Event): void {
    event.stopPropagation();
    this.activeMenuId.update((curr) => (curr === id ? null : id));
  }

  closeMenu(): void {
    this.activeMenuId.set(null);
  }

  isPlaylistActive(id: string): boolean {
    return this.player.activePlaylistId() === id;
  }

  isPlaylistPlaying(id: string): boolean {
    return this.isPlaylistActive(id) && this.player.isPlaying();
  }

  playPlaylistQuick(p: PlaylistSummary, event: Event): void {
    event.stopPropagation();
    if (p.track_count === 0) {
      this.toast.info('Lista vacía', `"${p.name}" aún no tiene canciones disponibles para reproducir.`);
      return;
    }

    if (this.isPlaylistActive(p.id)) {
      this.player.togglePlay();
      return;
    }

    this.playlistsApi.getPlaylist(p.id).subscribe({
      next: (full) => {
        if (!full.tracks || full.tracks.length === 0) {
          this.toast.info('Lista vacía', 'Esta lista aún no contiene canciones disponibles.');
          return;
        }
        this.player.playPlaylist(full.id, full.tracks, 0);
      },
      error: () => {
        this.toast.error('Error al reproducir', 'No se pudo iniciar la lista.');
      },
    });
  }

  navigateToPlaylist(id: string): void {
    this.router.navigate(['/playlists', id]);
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
}
