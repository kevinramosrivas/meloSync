import { Component, EventEmitter, Input, Output, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { TuiButton } from '@taiga-ui/core';
import { MetadataApiService } from '../../data/metadata-api.service';
import { ToastService } from '../../core/services/toast.service';
import { Track, TrackMetadata } from '../../domain/models';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-metadata-dialog',
  standalone: true,
  imports: [CommonModule, FormsModule, TuiButton, IconComponent],
  templateUrl: './metadata-dialog.component.html',
  styleUrl: './metadata-dialog.component.css'
})
export class MetadataDialogComponent implements OnInit {
  @Input({ required: true }) track!: Track;
  @Output() close = new EventEmitter<void>();
  @Output() updated = new EventEmitter<Track>();

  private metadataApi = inject(MetadataApiService);
  private toast = inject(ToastService);

  searchCandidateQuery = '';
  readonly candidates = signal<TrackMetadata[]>([]);
  readonly isSearchingCandidates = signal<boolean>(false);
  readonly isSaving = signal<boolean>(false);

  formTitle = '';
  formArtist = '';
  formAlbum = '';
  formYear: number | null = null;
  formGenre = '';
  formTrackNumber: number | null = null;
  formCoverUrl = '';

  ngOnInit(): void {
    if (this.track) {
      this.formTitle = this.track.metadata?.title || this.track.original_title;
      this.formArtist = this.track.metadata?.artist || this.track.channel_name;
      this.formAlbum = this.track.metadata?.album || 'Sencillo';
      this.formYear = this.track.metadata?.year || null;
      this.formGenre = this.track.metadata?.genre || '';
      this.formTrackNumber = this.track.metadata?.track_number || null;
      this.formCoverUrl = this.track.metadata?.cover_url || '';
      this.searchCandidateQuery = `${this.formArtist} ${this.formTitle}`.trim();
    }
  }

  onBackdropClick(event: MouseEvent): void {
    if ((event.target as HTMLElement).classList.contains('modal-backdrop')) {
      this.close.emit();
    }
  }

  searchCandidates(): void {
    const q = this.searchCandidateQuery.trim();
    if (!q) return;

    this.isSearchingCandidates.set(true);
    this.metadataApi.searchCandidates(q, 8).subscribe({
      next: (list) => {
        this.candidates.set(list);
        this.isSearchingCandidates.set(false);
      },
      error: () => this.isSearchingCandidates.set(false)
    });
  }

  applyCandidate(c: TrackMetadata): void {
    this.formTitle = c.title;
    this.formArtist = c.artist;
    this.formAlbum = c.album;
    this.formYear = c.year || null;
    this.formGenre = c.genre || '';
    this.formTrackNumber = c.track_number || null;
    this.formCoverUrl = c.cover_url || '';
    this.toast.info('Sugerencia aplicada al formulario');
  }

  save(): void {
    this.isSaving.set(true);

    const payload: Partial<TrackMetadata> = {
      title: this.formTitle,
      artist: this.formArtist,
      album: this.formAlbum,
      year: this.formYear,
      genre: this.formGenre,
      track_number: this.formTrackNumber,
      cover_url: this.formCoverUrl,
    };

    this.metadataApi.updateTrackMetadata(this.track.id, payload).subscribe({
      next: (updatedTrack) => {
        this.isSaving.set(false);
        this.toast.success('Metadatos actualizados y guardados en el archivo');
        this.updated.emit(updatedTrack);
        this.close.emit();
      },
      error: (e) => {
        this.isSaving.set(false);
        this.toast.error('Error al guardar metadatos', e.message);
      }
    });
  }
}
