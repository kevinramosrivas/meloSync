import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { AudioPlayerService } from '../../../core/services/audio-player.service';
import { DurationPipe } from '../../pipes/duration.pipe';
import { LibraryApiService } from '../../../data/library-api.service';
import { ToastService } from '../../../core/services/toast.service';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-bottom-player',
  standalone: true,
  imports: [CommonModule, DurationPipe, IconComponent],
  templateUrl: './bottom-player.component.html',
  styleUrl: './bottom-player.component.css'
})
export class BottomPlayerComponent {
  readonly player = inject(AudioPlayerService);
  private libraryApi = inject(LibraryApiService);
  private toast = inject(ToastService);

  onSeekClick(event: MouseEvent): void {
    const track = event.currentTarget as HTMLElement;
    const rect = track.getBoundingClientRect();
    const clickX = event.clientX - rect.left;
    const percent = (clickX / rect.width) * 100;
    this.player.seekPercent(percent);
  }

  onVolumeChange(event: Event): void {
    const input = event.target as HTMLInputElement;
    this.player.setVolume(parseFloat(input.value));
  }

  openInSystemPlayer(trackId: string): void {
    this.libraryApi.openInSystemPlayer(trackId).subscribe({
      next: () => this.toast.info('Abierto en reproductor local'),
      error: (e) => this.toast.error('Error al abrir archivo', e.message)
    });
  }

  openFolder(trackId: string): void {
    this.libraryApi.openContainingFolder(trackId).subscribe({
      next: () => this.toast.info('Carpeta abierta en explorador'),
      error: (e) => this.toast.error('Error al abrir carpeta', e.message)
    });
  }
}
