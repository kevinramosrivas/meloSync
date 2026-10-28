import { Component, inject, signal, effect, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DownloadsApiService } from '../../data/downloads-api.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { ToastService } from '../../core/services/toast.service';
import { Track } from '../../domain/models';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ProgressBarComponent } from '../../shared/components/progress-bar/progress-bar.component';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-downloads',
  imports: [CommonModule, StatusBadgeComponent, ProgressBarComponent, IconComponent],
  templateUrl: './downloads.component.html'
})
export class DownloadsComponent implements OnInit {
  private downloadsApi = inject(DownloadsApiService);
  private ws = inject(WebSocketService);
  private toast = inject(ToastService);

  readonly tracks = signal<Track[]>([]);

  constructor() {
    // React to incoming WebSocket download progress events
    effect(() => {
      const progress = this.ws.latestProgress();
      if (progress) {
        this.tracks.update(currentList => {
          const index = currentList.findIndex(t => t.youtube_id === progress.youtube_id || t.id === progress.track_id);
          if (index >= 0) {
            const updated = [...currentList];
            updated[index] = {
              ...updated[index],
              status: progress.status,
              progress_percent: progress.progress_percent,
            };
            return updated;
          } else {
            const newTrack: Track = {
              id: progress.track_id,
              youtube_id: progress.youtube_id,
              url: `https://youtube.com/watch?v=${progress.youtube_id}`,
              original_title: progress.stage_description || 'Descargando audio...',
              display_title: progress.stage_description || 'Descargando audio...',
              display_artist: 'YouTube',
              display_album: 'Sencillo',
              duration_seconds: 0,
              duration_formatted: '0:00',
              channel_name: 'YouTube',
              status: progress.status,
              progress_percent: progress.progress_percent,
            };
            return [newTrack, ...currentList];
          }
        });
      }
    });

    // React to completed tracks
    effect(() => {
      const completed = this.ws.latestCompletedTrack();
      if (completed) {
        this.tracks.update(currentList => {
          const index = currentList.findIndex(t => t.youtube_id === completed.youtube_id || t.id === completed.id);
          if (index >= 0) {
            const updated = [...currentList];
            updated[index] = completed;
            return updated;
          }
          return [completed, ...currentList];
        });
      }
    });
    // Reload active downloads when WebSocket connects (handles sidecar boot delay)
    effect(() => {
      if (this.ws.isConnected()) {
        this.loadActiveDownloads();
      }
    });
  }

  ngOnInit(): void {
    this.loadActiveDownloads();
  }

  loadActiveDownloads(retryCount = 0): void {
    this.downloadsApi.getActiveDownloads().subscribe({
      next: (data) => this.tracks.set(data),
      error: () => {
        if (retryCount < 2) {
          setTimeout(() => this.loadActiveDownloads(retryCount + 1), 1500);
        }
      }
    });
  }

  retry(trackId: string): void {
    this.downloadsApi.retryDownload(trackId).subscribe({
      next: () => this.toast.info('Reintentando descarga...'),
      error: (e) => this.toast.error('Error al reintentar', e.message)
    });
  }
}
