import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { LibraryApiService } from '../../data/library-api.service';
import { LibraryStore } from '../../core/stores/library.store';
import { AudioPlayerService } from '../../core/services/audio-player.service';
import { ToastService } from '../../core/services/toast.service';
import { UserPreferencesService } from '../../core/services/user-preferences.service';
import { ProximitySearchService } from '../../core/services/proximity-search.service';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import {
  LIBRARY_VIEW_MODES,
  LibraryViewMode,
  USER_PREFERENCE_KEYS
} from '../../core/constants/preferences.constants';
import { Track } from '../../domain/models';
import { DurationPipe } from '../../shared/pipes/duration.pipe';
import { CoverUrlPipe } from '../../shared/pipes/cover-url.pipe';
import { MetadataDialogComponent } from '../metadata-editor/metadata-dialog.component';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { EqualizerIndicatorComponent } from '../../shared/components/equalizer-indicator/equalizer-indicator.component';
import { AddToPlaylistDialogComponent } from './components/add-to-playlist-dialog/add-to-playlist-dialog.component';
import { TrackRowComponent } from '../../shared/components/track-row/track-row.component';
import { ConfirmDialogService } from '../../core/services/confirm-dialog.service';
import { ContextMenuService } from '../../core/services/context-menu.service';

@Component({
  selector: 'app-library',
  imports: [
    FormsModule,
    DurationPipe,
    CoverUrlPipe,
    MetadataDialogComponent,
    IconComponent,
    EqualizerIndicatorComponent,
    AddToPlaylistDialogComponent,
    TrackRowComponent
  ],
  templateUrl: './library.component.html'
})
export class LibraryComponent implements OnInit {
  private readonly libraryApi = inject(LibraryApiService);
  private readonly libraryStore = inject(LibraryStore);
  readonly player = inject(AudioPlayerService);
  private readonly toast = inject(ToastService);
  private readonly preferences = inject(UserPreferencesService);
  private readonly proximitySearch = inject(ProximitySearchService);
  private readonly coverCache = inject(CoverCacheService);
  private readonly confirmDialog = inject(ConfirmDialogService);
  private readonly contextMenu = inject(ContextMenuService);

  readonly viewModes = LIBRARY_VIEW_MODES;

  readonly tracks = this.libraryStore.tracks;
  readonly isLoading = this.libraryStore.isLoading;
  readonly isInitialLoading = this.libraryStore.isInitialLoading;
  readonly connectionFailed = this.libraryStore.connectionFailed;

  readonly isSyncing = signal<boolean>(false);
  readonly searchQuery = signal<string>('');

  // Sidebar state for dynamic floating dock centering
  readonly isSidebarCollapsed = this.preferences.sidebarCollapsed;
  readonly dockLeftOffset = computed(() =>
    this.isSidebarCollapsed() ? 'calc(50% + 36px)' : 'calc(50% + 120px)'
  );

  // Selection Mode Signals
  readonly isSelectionMode = signal<boolean>(false);
  readonly selectedTrackIds = signal<Set<string>>(new Set());

  // Compatibility getter/setter for template bindings
  get filterQuery(): string {
    return this.searchQuery();
  }
  set filterQuery(value: string) {
    this.searchQuery.set(value);
  }

  readonly viewMode = this.preferences.libraryViewMode;

  // Lazy render the cards DOM subtree only when first needed
  readonly hasRenderedCards = signal<boolean>(this.viewMode() === LIBRARY_VIEW_MODES.GRID);

  readonly selectedTrackForEdit = signal<Track | null>(null);
  readonly selectedTrackForPlaylist = signal<Track | null>(null);
  readonly isAddToPlaylistOpen = signal<boolean>(false);
  readonly locationFilter = signal<'all' | 'active' | 'missing'>('all');

  readonly missingCount = computed(() => this.tracks().filter(t => t.file_exists === false).length);
  readonly activeDirCount = computed(() => this.tracks().filter(t => t.is_in_active_directory !== false && t.file_exists !== false).length);

  readonly selectedTracksList = computed<Track[]>(() => {
    const ids = this.selectedTrackIds();
    return this.tracks().filter(t => ids.has(t.id));
  });

  readonly isAllSelected = computed<boolean>(() => {
    const displayed = this.filteredTracks();
    if (displayed.length === 0) return false;
    return displayed.every(t => this.selectedTrackIds().has(t.id));
  });

  openAddToPlaylist(track: Track, event: Event): void {
    event.stopPropagation();
    this.selectedTrackForPlaylist.set(track);
    this.isAddToPlaylistOpen.set(true);
  }

  readonly filteredTracks = computed(() => {
    let list = this.tracks();
    const loc = this.locationFilter();
    if (loc === 'active') {
      list = list.filter(t => t.is_in_active_directory !== false && t.file_exists !== false);
    } else if (loc === 'missing') {
      list = list.filter(t => t.file_exists === false);
    }
    return this.proximitySearch.searchTracks(list, this.searchQuery());
  });

  setLocationFilter(filter: 'all' | 'active' | 'missing'): void {
    this.locationFilter.set(filter);
  }

  ngOnInit(): void {
    this.libraryStore.load(false);
  }

  setViewMode(mode: LibraryViewMode): void {
    if (mode === LIBRARY_VIEW_MODES.GRID) {
      this.hasRenderedCards.set(true);
    }
    this.preferences.set(USER_PREFERENCE_KEYS.LIBRARY_VIEW_MODE, mode);
  }

  loadLibrary(retryCount = 0): void {
    this.libraryStore.load(true, retryCount);
  }

  syncLibrary(): void {
    this.isSyncing.set(true);
    this.libraryApi.syncLibrary().subscribe({
      next: (res) => {
        this.isSyncing.set(false);
        this.toast.success('Biblioteca Sincronizada', res.message);
        this.libraryStore.load(true);
      },
      error: (e) => {
        this.isSyncing.set(false);
        this.toast.error('Error al sincronizar', e.error?.detail || 'No se pudo sincronizar la biblioteca.');
      }
    });
  }

  getCoverUrl(track: Track): string | null {
    return this.coverCache.getCoverUrl(track);
  }

  play(track: Track): void {
    this.player.playTrack(track, this.filteredTracks());
  }

  togglePlayTrack(track: Track): void {
    if (this.player.currentTrack()?.id === track.id) {
      this.player.togglePlay();
    } else {
      this.play(track);
    }
  }

  playAll(shuffle: boolean = false): void {
    const list = this.filteredTracks();
    if (list.length === 0) return;

    if (shuffle) {
      if (!this.player.isShuffle()) {
        this.player.toggleShuffle();
      }
      const randomIndex = Math.floor(Math.random() * list.length);
      this.player.playTrack(list[randomIndex], list);
    } else {
      this.player.playTrack(list[0], list);
    }
  }

  openFolder(trackId: string): void {
    this.libraryApi.openContainingFolder(trackId).subscribe({
      next: () => this.toast.info('Carpeta abierta en explorador'),
      error: (e) => this.toast.error('Error al abrir carpeta', e.error?.detail || 'El archivo físico no se encuentra en el disco.')
    });
  }

  openMetadataDialog(track: Track): void {
    this.selectedTrackForEdit.set(track);
  }

  onTrackMetadataUpdated(updatedTrack: Track): void {
    this.coverCache.invalidate(updatedTrack.id);
    this.libraryStore.updateTrackInMemory(updatedTrack);
  }

  toggleSelectionMode(): void {
    const next = !this.isSelectionMode();
    this.isSelectionMode.set(next);
    if (!next) {
      this.selectedTrackIds.set(new Set());
    }
  }

  toggleTrackSelection(track: Track): void {
    if (!this.isSelectionMode()) {
      this.isSelectionMode.set(true);
    }
    this.selectedTrackIds.update(set => {
      const updated = new Set(set);
      if (updated.has(track.id)) {
        updated.delete(track.id);
      } else {
        updated.add(track.id);
      }
      return updated;
    });
  }

  toggleSelectAll(): void {
    const displayed = this.filteredTracks();
    if (this.isAllSelected()) {
      this.selectedTrackIds.update(set => {
        const updated = new Set(set);
        displayed.forEach(t => updated.delete(t.id));
        return updated;
      });
    } else {
      this.selectedTrackIds.update(set => {
        const updated = new Set(set);
        displayed.forEach(t => updated.add(t.id));
        return updated;
      });
    }
  }

  clearSelection(): void {
    this.selectedTrackIds.set(new Set());
    this.isSelectionMode.set(false);
  }

  openBatchAddToPlaylist(): void {
    const selected = this.selectedTracksList();
    if (selected.length === 0) return;
    this.selectedTrackForPlaylist.set(null);
    this.isAddToPlaylistOpen.set(true);
  }

  openTrackContextMenu(track: Track, event: MouseEvent): void {
    const isSelected = this.selectedTrackIds().has(track.id);
    this.contextMenu.open({
      x: event.clientX,
      y: event.clientY,
      items: [
        {
          label: 'Reproducir ahora',
          icon: 'play',
          action: () => this.togglePlayTrack(track),
        },
        {
          label: 'Añadir a playlist...',
          icon: 'list-music',
          action: () => {
            this.selectedTrackForPlaylist.set(track);
            this.isAddToPlaylistOpen.set(true);
          },
        },
        {
          label: 'Editar metadatos y carátula...',
          icon: 'pencil',
          action: () => this.openMetadataDialog(track),
        },
        {
          label: 'Revelar en el explorador',
          icon: 'folder',
          action: () => this.openFolder(track.id),
        },
        { separator: true },
        {
          label: isSelected ? 'Deseleccionar canción' : 'Seleccionar canción',
          icon: isSelected ? 'check-square' : 'square',
          action: () => this.toggleTrackSelection(track),
        },
        { separator: true },
        {
          label: 'Eliminar de la biblioteca',
          icon: 'trash',
          danger: true,
          action: () => this.deleteTrack(track),
        },
      ],
    });
  }

  async deleteTrack(track: Track): Promise<void> {
    const confirmed = await this.confirmDialog.confirm({
      title: 'Eliminar canción',
      message: `¿Estás seguro de que deseas eliminar permanentemente "${track.display_title}"? El archivo físico se borrará de tu equipo.`,
      confirmText: 'Eliminar',
      danger: true,
      icon: 'trash',
    });

    if (!confirmed) return;

    this.libraryApi.deleteTrack(track.id, true).subscribe({
      next: () => {
        this.toast.success('Pista eliminada');
        this.coverCache.invalidate(track.id);
        this.libraryStore.removeTrackFromMemory(track.id);
        this.selectedTrackIds.update(set => {
          const updated = new Set(set);
          updated.delete(track.id);
          return updated;
        });
      },
      error: (e) => this.toast.error('Error al eliminar pista', e.error?.detail || 'No se pudo eliminar la pista.')
    });
  }

  async deleteSelectedTracks(): Promise<void> {
    const tracksToDelete = this.selectedTracksList();
    const count = tracksToDelete.length;
    if (count === 0) return;

    const confirmed = await this.confirmDialog.confirm({
      title: `Eliminar ${count} ${count === 1 ? 'canción' : 'canciones'}`,
      message: `¿Deseas eliminar permanentemente ${count} ${count === 1 ? 'canción seleccionada' : 'canciones seleccionadas'} de tu biblioteca y disco duro? Esta acción no se puede deshacer.`,
      confirmText: `Eliminar ${count}`,
      danger: true,
      icon: 'trash',
    });

    if (!confirmed) return;

    const ids = tracksToDelete.map(t => t.id);
    this.libraryApi.deleteTracksBatch(ids, true).subscribe({
      next: (res) => {
        this.toast.success('Canciones eliminadas', `${res.deleted_count} canciones fueron eliminadas.`);
        tracksToDelete.forEach(t => {
          this.coverCache.invalidate(t.id);
          this.libraryStore.removeTrackFromMemory(t.id);
        });
        this.clearSelection();
      },
      error: (err) => this.toast.error('Error al eliminar en lote', err.message || 'No se pudieron eliminar las pistas.')
    });
  }
}