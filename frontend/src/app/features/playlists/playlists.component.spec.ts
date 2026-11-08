import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { Router } from '@angular/router';
import { PlaylistsComponent } from './playlists.component';
import { PlaylistsApiService } from '../../data/playlists-api.service';
import { PlaylistsStore } from '../../core/stores/playlists.store';
import { AudioPlayerService } from '../../core/services/audio-player.service';
import { ToastService } from '../../core/services/toast.service';
import { ConfirmDialogService } from '../../core/services/confirm-dialog.service';
import { PlaylistSummary } from '../../domain/models';

describe('PlaylistsComponent', () => {
  let component: PlaylistsComponent;
  let fixture: ComponentFixture<PlaylistsComponent>;

  const dummySummary: PlaylistSummary = {
    id: 'pl-1',
    name: 'Favoritas',
    description: 'Mis canciones favoritas',
    playlist_type: 'custom',
    is_smart: false,
    track_count: 5,
    duration_seconds: 900,
    created_at_iso: '2026-01-01T00:00:00Z',
    updated_at_iso: '2026-01-01T00:00:00Z',
    sample_cover_track_ids: [],
  };

  let mockPlaylistsApi: {
    getPlaylists: ReturnType<typeof vi.fn>;
    getPlaylist: ReturnType<typeof vi.fn>;
    createPlaylist: ReturnType<typeof vi.fn>;
    updatePlaylist: ReturnType<typeof vi.fn>;
    deletePlaylist: ReturnType<typeof vi.fn>;
    triggerSmartSync: ReturnType<typeof vi.fn>;
  };

  let mockPlaylistsStore: {
    userPlaylists: ReturnType<typeof signal<PlaylistSummary[]>>;
    forYouPlaylists: ReturnType<typeof signal<PlaylistSummary[]>>;
    artistPlaylists: ReturnType<typeof signal<PlaylistSummary[]>>;
    genrePlaylists: ReturnType<typeof signal<PlaylistSummary[]>>;
    isLoading: ReturnType<typeof signal<boolean>>;
    isInitialLoading: ReturnType<typeof signal<boolean>>;
    connectionFailed: ReturnType<typeof signal<boolean>>;
    load: ReturnType<typeof vi.fn>;
  };

  let mockPlayer: {
    activePlaylistId: ReturnType<typeof signal<string | null>>;
    isPlaying: ReturnType<typeof signal<boolean>>;
    playPlaylist: ReturnType<typeof vi.fn>;
    togglePlay: ReturnType<typeof vi.fn>;
  };

  let mockRouter: {
    navigate: ReturnType<typeof vi.fn>;
  };

  let mockToast: {
    success: ReturnType<typeof vi.fn>;
    error: ReturnType<typeof vi.fn>;
    info: ReturnType<typeof vi.fn>;
  };

  let mockConfirmDialog: {
    confirm: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    mockPlaylistsApi = {
      getPlaylists: vi.fn().mockReturnValue(of({ user: [dummySummary], for_you: [], artists: [], genres: [] })),
      getPlaylist: vi.fn().mockReturnValue(of({ id: 'pl-1', name: 'Favoritas', tracks: [] })),
      createPlaylist: vi.fn().mockReturnValue(of(dummySummary)),
      updatePlaylist: vi.fn().mockReturnValue(of(dummySummary)),
      deletePlaylist: vi.fn().mockReturnValue(of({ success: true })),
      triggerSmartSync: vi.fn().mockReturnValue(of({ message: 'OK' })),
    };

    mockPlaylistsStore = {
      userPlaylists: signal([dummySummary]),
      forYouPlaylists: signal([]),
      artistPlaylists: signal([]),
      genrePlaylists: signal([]),
      isLoading: signal(false),
      isInitialLoading: signal(false),
      connectionFailed: signal(false),
      load: vi.fn(),
    };

    mockPlayer = {
      activePlaylistId: signal(null),
      isPlaying: signal(false),
      playPlaylist: vi.fn(),
      togglePlay: vi.fn(),
    };

    mockRouter = {
      navigate: vi.fn(),
    };

    mockToast = {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    };

    mockConfirmDialog = {
      confirm: vi.fn().mockResolvedValue(true),
    };

    await TestBed.configureTestingModule({
      imports: [PlaylistsComponent],
      providers: [
        { provide: PlaylistsApiService, useValue: mockPlaylistsApi },
        { provide: PlaylistsStore, useValue: mockPlaylistsStore },
        { provide: AudioPlayerService, useValue: mockPlayer },
        { provide: Router, useValue: mockRouter },
        { provide: ToastService, useValue: mockToast },
        { provide: ConfirmDialogService, useValue: mockConfirmDialog },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PlaylistsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the playlists component', () => {
    expect(component).toBeTruthy();
    expect(component.filteredUserPlaylists().length).toBe(1);
  });

  it('should navigate to playlist detail on card click', () => {
    component.navigateToPlaylist('pl-1');
    expect(mockRouter.navigate).toHaveBeenCalledWith(['/playlists', 'pl-1']);
  });

  it('should filter playlists by search query', () => {
    component.searchQuery.set('NonExistent');
    expect(component.filteredUserPlaylists().length).toBe(0);

    component.searchQuery.set('Favoritas');
    expect(component.filteredUserPlaylists().length).toBe(1);
  });

  it('should confirm and delete playlist when deletePlaylist is called', async () => {
    const fakeEvent = new MouseEvent('click');
    const stopSpy = vi.spyOn(fakeEvent, 'stopPropagation');

    await component.deletePlaylist(dummySummary, fakeEvent);

    expect(stopSpy).toHaveBeenCalled();
    expect(mockConfirmDialog.confirm).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Eliminar lista de reproducción',
        danger: true,
      })
    );
    expect(mockPlaylistsApi.deletePlaylist).toHaveBeenCalledWith('pl-1');
    expect(mockToast.success).toHaveBeenCalled();
  });

  it('should not delete playlist when confirm dialog is rejected', async () => {
    mockConfirmDialog.confirm.mockResolvedValueOnce(false);
    const fakeEvent = new MouseEvent('click');

    await component.deletePlaylist(dummySummary, fakeEvent);

    expect(mockConfirmDialog.confirm).toHaveBeenCalled();
    expect(mockPlaylistsApi.deletePlaylist).not.toHaveBeenCalled();
  });
});
