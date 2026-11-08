import { Component, inject, signal, computed, effect, OnInit, OnDestroy } from '@angular/core';
import { DecimalPipe } from '@angular/common';
import { DownloadsApiService } from '../../data/downloads-api.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { ToastService } from '../../core/services/toast.service';
import { ConfirmDialogService } from '../../core/services/confirm-dialog.service';
import { Track } from '../../domain/models';
import { StatusBadgeComponent } from '../../shared/components/status-badge/status-badge.component';
import { ProgressBarComponent } from '../../shared/components/progress-bar/progress-bar.component';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-downloads',
  imports: [DecimalPipe, StatusBadgeComponent, ProgressBarComponent, IconComponent],
  templateUrl: './downloads.component.html'
})
export class DownloadsComponent implements OnInit, OnDestroy {
  private downloadsApi = inject(DownloadsApiService);
  private ws = inject(WebSocketService);
  private toast = inject(ToastService);
  private confirmDialog = inject(ConfirmDialogService);

  readonly tracks = signal<Track[]>([]);
  readonly hasFailedOrCancelled = computed(() =>
    this.tracks().some(t => t.status === 'ERROR' || t.status === 'CANCELADA')
  );

  private pollInterval: ReturnType<typeof setInterval> | null = null;

  constructor() {
    // React to incoming WebSocket download progress events
    effect(() => {
      const progress = this.ws.latestProgress();
      if (progress) {
        if (progress.stage_description === 'Descarga eliminada') {
          this.tracks.update(list => list.filter(t => t.id !== progress.track_id && t.youtube_id !== progress.youtube_id));
          return;
        }

        this.tracks.update(currentList => {
          const index = currentList.findIndex(t => t.youtube_id === progress.youtube_id || t.id === progress.track_id);
          if (index >= 0) {
            const updated = [...currentList];
            updated[index] = {
              ...updated[index],
              status: progress.status,
              progress_percent: progress.progress_percent,
              error_message:
                progress.status === 'ERROR'
                  ? (progress.stage_description || updated[index].error_message)
                  : progress.status === 'CANCELADA'
                  ? 'Descarga cancelada por el usuario'
                  : updated[index].error_message,
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
    // Safety polling every 2.5s to guarantee fresh state during active processing
    this.pollInterval = setInterval(() => {
      const hasActive = this.tracks().some(t => this.isActive(t));
      if (hasActive) {
        this.loadActiveDownloads();
      }
    }, 2500);
  }

  ngOnDestroy(): void {
    if (this.pollInterval) {
      clearInterval(this.pollInterval);
      this.pollInterval = null;
    }
  }

  isActive(track: Track): boolean {
    return (
      track.status === 'PENDIENTE' ||
      track.status === 'DESCARGANDO' ||
      track.status === 'PROCESANDO_AUDIO' ||
      track.status === 'OBTENIENDO_METADATOS'
    );
  }

  loadActiveDownloads(retryCount = 0): void {
    this.downloadsApi.getActiveDownloads().subscribe({
      next: (data) => {
        this.tracks.set(data);
        this.ws.syncActiveDownloads(data);
      },
      error: () => {
        if (retryCount < 2) {
          setTimeout(() => this.loadActiveDownloads(retryCount + 1), 1500);
        }
      }
    });
  }

  retry(trackId: string): void {
    this.downloadsApi.retryDownload(trackId).subscribe({
      next: () => {
        this.toast.info('Reintentando descarga...');
        this.loadActiveDownloads();
      },
      error: (e) => this.toast.error('Error al reintentar', e.message)
    });
  }

  cancel(track: Track): void {
    this.downloadsApi.cancelDownload(track.id).subscribe({
      next: () => {
        this.toast.info('Descarga cancelada');
        this.tracks.update(list =>
          list.map(t =>
            t.id === track.id
              ? { ...t, status: 'CANCELADA' as const, error_message: 'Descarga cancelada por el usuario' }
              : t
          )
        );
        this.ws.removeActiveDownload(track.id);
      },
      error: (err) => this.toast.error('Error al cancelar descarga', err.message),
    });
  }

  removeDownload(track: Track): void {
    this.downloadsApi.deleteDownload(track.id).subscribe({
      next: () => {
        this.toast.info('Descarga eliminada');
        this.tracks.update(list => list.filter(t => t.id !== track.id));
        this.ws.removeActiveDownload(track.id);
      },
      error: (err) => this.toast.error('Error al eliminar descarga', err.message),
    });
  }

  async clearFailed(): Promise<void> {
    const count = this.tracks().filter(t => t.status === 'ERROR' || t.status === 'CANCELADA').length;
    if (count === 0) return;

    const confirmed = await this.confirmDialog.confirm({
      title: 'Limpiar descargas fallidas',
      message: `¿Deseas quitar del monitor las ${count} ${count === 1 ? 'descarga fallida o cancelada' : 'descargas fallidas o canceladas'}?`,
      confirmText: 'Limpiar',
      danger: true,
      icon: 'trash',
    });

    if (!confirmed) return;

    this.downloadsApi.clearFailedDownloads().subscribe({
      next: (res) => {
        this.toast.info(res.message || 'Descargas fallidas eliminadas');
        this.tracks.update(list => list.filter(t => t.status !== 'ERROR' && t.status !== 'CANCELADA'));
        this.loadActiveDownloads();
      },
      error: (err) => this.toast.error('Error al limpiar descargas', err.message),
    });
  }
}

