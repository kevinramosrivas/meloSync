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

  readonly viewModes = LIBRARY_VIEW_MODES;

  readonly tracks = this.libraryStore.tracks;
  readonly isLoading = this.libraryStore.isLoading;
  readonly isInitialLoading = this.libraryStore.isInitialLoading;
  readonly connectionFailed = this.libraryStore.connectionFailed;

  readonly isSyncing = signal<boolean>(false);
  readonly searchQuery = signal<string>('');

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

  openAddToPlaylist(track: Track, event: Event): void {
    event.stopPropagation();
    this.selectedTrackForPlaylist.set(track);
    this.isAddToPlaylistOpen.set(true);
  }

  readonly filteredTracks = computed(() => {
    return this.proximitySearch.searchTracks(this.tracks(), this.searchQuery());
  });

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

  deleteTrack(track: Track): void {
    if (confirm(`¿Estás seguro de eliminar "${track.display_title}"?`)) {
      this.libraryApi.deleteTrack(track.id, true).subscribe({
        next: () => {
          this.toast.success('Pista eliminada');
          this.coverCache.invalidate(track.id);
          this.libraryStore.removeTrackFromMemory(track.id);
        },
        error: (e) => this.toast.error('Error al eliminar pista', e.error?.detail || 'No se pudo eliminar la pista.')
      });
    }
  }
}