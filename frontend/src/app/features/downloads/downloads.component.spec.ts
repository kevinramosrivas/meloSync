import { ComponentFixture, TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { DownloadsComponent } from './downloads.component';
import { DownloadsApiService } from '../../data/downloads-api.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { ToastService } from '../../core/services/toast.service';
import { ConfirmDialogService } from '../../core/services/confirm-dialog.service';
import { Track, DownloadProgress } from '../../domain/models';

describe('DownloadsComponent', () => {
  let component: DownloadsComponent;
  let fixture: ComponentFixture<DownloadsComponent>;

  const mockActiveTrack: Track = {
    id: 'track-123',
    youtube_id: 'yt-123',
    url: 'https://youtube.com/watch?v=yt-123',
    original_title: 'Dany Ocean - Fuera de Mercado',
    display_title: 'Fuera de Mercado',
    display_artist: 'Danny Ocean',
    display_album: 'Single',
    duration_seconds: 180,
    duration_formatted: '3:00',
    channel_name: 'Danny Ocean',
    status: 'DESCARGANDO',
    progress_percent: 45.0,
  };

  let downloadsApiMock: {
    getActiveDownloads: ReturnType<typeof vi.fn>;
    retryDownload: ReturnType<typeof vi.fn>;
    cancelDownload: ReturnType<typeof vi.fn>;
    deleteDownload: ReturnType<typeof vi.fn>;
    clearFailedDownloads: ReturnType<typeof vi.fn>;
  };

  let wsMock: {
    isConnected: ReturnType<typeof signal>;
    latestProgress: ReturnType<typeof signal>;
    latestCompletedTrack: ReturnType<typeof signal>;
    syncActiveDownloads: ReturnType<typeof vi.fn>;
    removeActiveDownload: ReturnType<typeof vi.fn>;
  };

  let toastMock: {
    info: ReturnType<typeof vi.fn>;
    error: ReturnType<typeof vi.fn>;
  };

  let confirmDialogMock: {
    confirm: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    downloadsApiMock = {
      getActiveDownloads: vi.fn().mockReturnValue(of([mockActiveTrack])),
      retryDownload: vi.fn().mockReturnValue(of({ message: 'Retrying', track_id: 'track-123' })),
      cancelDownload: vi.fn().mockReturnValue(of({ message: 'Cancelled', track_id: 'track-123', status: 'CANCELADA' })),
      deleteDownload: vi.fn().mockReturnValue(of({ message: 'Deleted', track_id: 'track-123' })),
      clearFailedDownloads: vi.fn().mockReturnValue(of({ message: 'Cleared', deleted_count: 2 })),
    };

    wsMock = {
      isConnected: signal<boolean>(true),
      latestProgress: signal<DownloadProgress | null>(null),
      latestCompletedTrack: signal<Track | null>(null),
      syncActiveDownloads: vi.fn(),
      removeActiveDownload: vi.fn(),
    };

    toastMock = {
      info: vi.fn(),
      error: vi.fn(),
    };

    confirmDialogMock = {
      confirm: vi.fn().mockResolvedValue(true),
    };

    await TestBed.configureTestingModule({
      imports: [DownloadsComponent],
      providers: [
        { provide: DownloadsApiService, useValue: downloadsApiMock },
        { provide: WebSocketService, useValue: wsMock },
        { provide: ToastService, useValue: toastMock },
        { provide: ConfirmDialogService, useValue: confirmDialogMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(DownloadsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the component and load active downloads from API', () => {
    expect(component).toBeTruthy();
    expect(downloadsApiMock.getActiveDownloads).toHaveBeenCalled();
    expect(component.tracks().length).toBe(1);
    expect(component.tracks()[0].id).toBe('track-123');
    expect(component.tracks()[0].display_title).toBe('Fuera de Mercado');
  });

  it('should update track progress when websocket emits new progress event', () => {
    wsMock.latestProgress.set({
      track_id: 'track-123',
      youtube_id: 'yt-123',
      status: 'PROCESANDO_AUDIO',
      progress_percent: 65.0,
      stage_description: 'Normalizando volumen...',
      speed_text: '',
      eta_text: '',
    });

    fixture.detectChanges();

    expect(component.tracks().length).toBe(1);
    expect(component.tracks()[0].status).toBe('PROCESANDO_AUDIO');
    expect(component.tracks()[0].progress_percent).toBe(65.0);
  });

  it('should prepend incoming download when not present in initial list', () => {
    wsMock.latestProgress.set({
      track_id: 'track-456',
      youtube_id: 'yt-456',
      status: 'DESCARGANDO',
      progress_percent: 10.0,
      stage_description: 'Descargando audio...',
      speed_text: '2.5MB/s',
      eta_text: '00:05',
    });

    fixture.detectChanges();

    expect(component.tracks().length).toBe(2);
    expect(component.tracks()[0].youtube_id).toBe('yt-456');
    expect(component.tracks()[0].status).toBe('DESCARGANDO');
  });

  it('should update completed track state when websocket emits completed track', () => {
    const completedTrack: Track = {
      ...mockActiveTrack,
      status: 'COMPLETADA',
      progress_percent: 100.0,
    };

    wsMock.latestCompletedTrack.set(completedTrack);
    fixture.detectChanges();

    expect(component.tracks()[0].status).toBe('COMPLETADA');
    expect(component.tracks()[0].progress_percent).toBe(100.0);
  });

  it('should correctly identify active tracks', () => {
    expect(component.isActive(mockActiveTrack)).toBe(true);
    const errorTrack: Track = { ...mockActiveTrack, status: 'ERROR' };
    expect(component.isActive(errorTrack)).toBe(false);
    const cancelledTrack: Track = { ...mockActiveTrack, status: 'CANCELADA' };
    expect(component.isActive(cancelledTrack)).toBe(false);
  });

  it('should cancel active download and update status to CANCELADA', () => {
    component.cancel(mockActiveTrack);
    expect(downloadsApiMock.cancelDownload).toHaveBeenCalledWith('track-123');
    expect(toastMock.info).toHaveBeenCalledWith('Descarga cancelada');
    expect(component.tracks()[0].status).toBe('CANCELADA');
    expect(wsMock.removeActiveDownload).toHaveBeenCalledWith('track-123');
  });

  it('should remove download and filter track out of the list', () => {
    component.removeDownload(mockActiveTrack);
    expect(downloadsApiMock.deleteDownload).toHaveBeenCalledWith('track-123');
    expect(toastMock.info).toHaveBeenCalledWith('Descarga eliminada');
    expect(component.tracks().length).toBe(0);
    expect(wsMock.removeActiveDownload).toHaveBeenCalledWith('track-123');
  });

  it('should clear failed and cancelled tracks when clearFailed is called', async () => {
    component.tracks.set([
      { ...mockActiveTrack, id: 'err-1', status: 'ERROR' },
      { ...mockActiveTrack, id: 'canc-1', status: 'CANCELADA' },
    ]);
    expect(component.hasFailedOrCancelled()).toBe(true);

    await component.clearFailed();
    expect(confirmDialogMock.confirm).toHaveBeenCalled();
    expect(downloadsApiMock.clearFailedDownloads).toHaveBeenCalled();
    expect(toastMock.info).toHaveBeenCalled();
  });
});

