import { Component, inject, signal, effect, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TuiButton } from '@taiga-ui/core';
import { LibraryApiService } from '../../data/library-api.service';
import { AudioPlayerService } from '../../core/services/audio-player.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { ToastService } from '../../core/services/toast.service';
import { Track } from '../../domain/models';
import { DurationPipe } from '../../shared/pipes/duration.pipe';
import { MetadataDialogComponent } from '../metadata-editor/metadata-dialog.component';
import { API_CONFIG } from '../../core/config/api.config';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-library',
  standalone: true,
  imports: [CommonModule, FormsModule, DurationPipe, MetadataDialogComponent, TuiButton, IconComponent],
  templateUrl: './library.component.html',
  styleUrl: './library.component.css'
})
export class LibraryComponent implements OnInit {
  private libraryApi = inject(LibraryApiService);
  readonly player = inject(AudioPlayerService);
  private ws = inject(WebSocketService);
  private toast = inject(ToastService);

  readonly tracks = signal<Track[]>([]);
  readonly isLoading = signal<boolean>(false);
  filterQuery = '';

  readonly selectedTrackForEdit = signal<Track | null>(null);

  constructor() {
    // Automatically reload library whenever WebSocket signals an update
    effect(() => {
      this.ws.libraryUpdated();
      this.loadLibrary();
    });
  }

  ngOnInit(): void {
    this.loadLibrary();
  }

  loadLibrary(): void {
    this.isLoading.set(true);
    this.libraryApi.getLibrary('COMPLETADA').subscribe({
      next: (data) => {
        this.tracks.set(data);
        this.isLoading.set(false);
      },
      error: () => this.isLoading.set(false)
    });
  }

  filteredTracks(): Track[] {
    const q = this.filterQuery.toLowerCase().trim();
    if (!q) return this.tracks();
    return this.tracks().filter(t =>
      t.display_title.toLowerCase().includes(q) ||
      t.display_artist.toLowerCase().includes(q) ||
      t.display_album.toLowerCase().includes(q)
    );
  }

  getCoverUrl(track: Track): string | null {
    if (track.metadata?.has_cover_bytes) {
      return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.cover(track.id)}?t=${track.updated_at_iso || ''}`;
    }
    if (track.metadata?.cover_url) {
      return track.metadata.cover_url;
    }
    return null;
  }

  play(track: Track): void {
    this.player.playTrack(track, this.filteredTracks());
  }

  openFolder(trackId: string): void {
    this.libraryApi.openContainingFolder(trackId).subscribe({
      next: () => this.toast.info('Carpeta abierta en explorador'),
      error: (e) => this.toast.error('Error al abrir carpeta', e.message)
    });
  }

  openMetadataDialog(track: Track): void {
    this.selectedTrackForEdit.set(track);
  }

  onTrackMetadataUpdated(updatedTrack: Track): void {
    this.tracks.update(list => list.map(t => t.id === updatedTrack.id ? updatedTrack : t));
  }

  deleteTrack(track: Track): void {
    if (confirm(`¿Estás seguro de eliminar "${track.display_title}"?`)) {
      this.libraryApi.deleteTrack(track.id, true).subscribe({
        next: () => {
          this.toast.success('Pista eliminada');
          this.tracks.update(list => list.filter(t => t.id !== track.id));
        },
        error: (e) => this.toast.error('Error al eliminar pista', e.message)
      });
    }
  }
}
