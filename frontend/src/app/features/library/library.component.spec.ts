import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { of, throwError } from 'rxjs';
import { LibraryComponent } from './library.component';
import { LibraryApiService } from '../../data/library-api.service';
import { AudioPlayerService } from '../../core/services/audio-player.service';
import { WebSocketService } from '../../core/services/websocket.service';
import { ToastService } from '../../core/services/toast.service';
import { UserPreferencesService } from '../../core/services/user-preferences.service';
import { ProximitySearchService } from '../../core/services/proximity-search.service';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import { ConfirmDialogService } from '../../core/services/confirm-dialog.service';
import { ContextMenuService } from '../../core/services/context-menu.service';
import { LIBRARY_VIEW_MODES } from '../../core/constants/preferences.constants';
import { Track } from '../../domain/models';

describe('LibraryComponent', () => {
  let component: LibraryComponent;
  let fixture: ComponentFixture<LibraryComponent>;

  let mockLibraryApi: {
    getLibrary: ReturnType<typeof vi.fn>;
    syncLibrary: ReturnType<typeof vi.fn>;
    deleteTrack: ReturnType<typeof vi.fn>;
    deleteTracksBatch: ReturnType<typeof vi.fn>;
    openContainingFolder: ReturnType<typeof vi.fn>;
  };

  let mockConfirmDialog: {
    confirm: ReturnType<typeof vi.fn>;
  };

  let mockContextMenu: {
    open: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  };

  let mockWs: {
    libraryUpdated: ReturnType<typeof signal<number>>;
    isConnected: ReturnType<typeof signal<boolean>>;
    latestProgress: ReturnType<typeof signal<null>>;
    latestCompletedTrack: ReturnType<typeof signal<null>>;
  };

  let mockPlayer: {
    currentTrack: ReturnType<typeof signal<null>>;
    isPlaying: ReturnType<typeof signal<boolean>>;
    isShuffle: ReturnType<typeof signal<boolean>>;
    playTrack: ReturnType<typeof vi.fn>;
    togglePlay: ReturnType<typeof vi.fn>;
    toggleShuffle: ReturnType<typeof vi.fn>;
  };

  let mockPreferences: {
    libraryViewMode: ReturnType<typeof signal<string>>;
    sidebarCollapsed: ReturnType<typeof signal<boolean>>;
    set: ReturnType<typeof vi.fn>;
  };

  const dummyTrack: Track = {
    id: 'track-1',
    youtube_id: 'yt-1',
    url: 'https://youtube.com/watch?v=yt-1',
    original_title: 'Original Title',
    display_title: 'Test Song',
    display_artist: 'Test Artist',
    display_album: 'Test Album',
    duration_seconds: 180,
    duration_formatted: '3:00',
    channel_name: 'Test Channel',
    status: 'COMPLETADA',
    progress_percent: 100,
    file_exists: true
  };

  beforeEach(async () => {
    mockLibraryApi = {
      getLibrary: vi.fn().mockReturnValue(of([dummyTrack])),
      syncLibrary: vi.fn().mockReturnValue(of({ message: 'OK' })),
      deleteTrack: vi.fn().mockReturnValue(of({ success: true })),
      deleteTracksBatch: vi.fn().mockReturnValue(of({ deleted_count: 1, failed_ids: [] })),
      openContainingFolder: vi.fn().mockReturnValue(of({ success: true }))
    };

    mockConfirmDialog = {
      confirm: vi.fn().mockResolvedValue(true)
    };

    mockContextMenu = {
      open: vi.fn(),
      close: vi.fn()
    };

    mockWs = {
      libraryUpdated: signal(Date.now()),
      isConnected: signal(false),
      latestProgress: signal(null),
      latestCompletedTrack: signal(null)
    };

    mockPlayer = {
      currentTrack: signal(null),
      isPlaying: signal(false),
      isShuffle: signal(false),
      playTrack: vi.fn(),
      togglePlay: vi.fn(),
      toggleShuffle: vi.fn()
    };

    mockPreferences = {
      libraryViewMode: signal(LIBRARY_VIEW_MODES.LIST),
      sidebarCollapsed: signal(false),
      set: vi.fn()
    };

    const mockToast = {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn()
    };

    const mockProximitySearch = {
      searchTracks: vi.fn((tracks: Track[]) => tracks)
    };

    const mockCoverCache = {
      getCoverUrl: vi.fn().mockReturnValue(null),
      invalidate: vi.fn()
    };

    await TestBed.configureTestingModule({
      imports: [LibraryComponent],
      providers: [
        provideRouter([]),
        { provide: LibraryApiService, useValue: mockLibraryApi },
        { provide: AudioPlayerService, useValue: mockPlayer },
        { provide: WebSocketService, useValue: mockWs },
        { provide: ToastService, useValue: mockToast },
        { provide: UserPreferencesService, useValue: mockPreferences },
        { provide: ProximitySearchService, useValue: mockProximitySearch },
        { provide: CoverCacheService, useValue: mockCoverCache },
        { provide: ConfirmDialogService, useValue: mockConfirmDialog },
        { provide: ContextMenuService, useValue: mockContextMenu }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(LibraryComponent);
    component = fixture.componentInstance;
  });

  it('should create the library component', () => {
    expect(component).toBeTruthy();
  });

  it('should load tracks and hide initial skeleton on successful API response', () => {
    fixture.detectChanges(); // triggers ngOnInit -> loadLibrary(0)

    expect(mockLibraryApi.getLibrary).toHaveBeenCalledWith('COMPLETADA');
    expect(component.tracks().length).toBe(1);
    expect(component.isInitialLoading()).toBe(false);
    expect(component.connectionFailed()).toBe(false);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Test Song');
    expect(compiled.textContent).not.toContain('No hay canciones en tu biblioteca');
  });

  it('should show empty state only when API returns 0 songs successfully', () => {
    mockLibraryApi.getLibrary.mockReturnValue(of([]));
    fixture.detectChanges();

    expect(component.tracks().length).toBe(0);
    expect(component.isInitialLoading()).toBe(false);
    expect(component.connectionFailed()).toBe(false);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('No hay canciones en tu biblioteca');
  });

  it('should show connection error screen instead of false empty library if backend fails repeatedly', () => {
    mockLibraryApi.getLibrary.mockReturnValue(throwError(() => new Error('Connection refused')));
    fixture.detectChanges(); // ngOnInit runs with throwError; tracks remains empty

    component.loadLibrary(8); // Explicitly trigger retry limit
    fixture.detectChanges();

    expect(component.isInitialLoading()).toBe(false);
    expect(component.connectionFailed()).toBe(true);

    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('No se pudo conectar con el motor local');
    expect(compiled.textContent).not.toContain('No hay canciones en tu biblioteca');
    expect(compiled.textContent).toContain('Reintentar conexión');
  });

  it('should trigger reload immediately when WebSocket becomes connected during cold start', () => {
    mockLibraryApi.getLibrary.mockReturnValueOnce(throwError(() => new Error('Backend booting')));
    fixture.detectChanges();
    mockLibraryApi.getLibrary.mockClear();
    mockLibraryApi.getLibrary.mockReturnValue(of([dummyTrack]));

    mockWs.isConnected.set(true);
    TestBed.flushEffects();

    expect(mockLibraryApi.getLibrary).toHaveBeenCalled();
    expect(component.tracks().length).toBe(1);
    expect(component.isInitialLoading()).toBe(false);
  });

  it('should filter tracks according to locationFilter and compute counts', () => {
    const trackInActive: Track = { ...dummyTrack, id: 't-active', is_in_active_directory: true, file_exists: true };
    const trackForeign: Track = { ...dummyTrack, id: 't-foreign', is_in_active_directory: false, file_exists: true };
    const trackMissing: Track = { ...dummyTrack, id: 't-missing', is_in_active_directory: false, file_exists: false };

    mockLibraryApi.getLibrary.mockReturnValue(of([trackInActive, trackForeign, trackMissing]));
    component.loadLibrary(0);
    fixture.detectChanges();

    expect(component.activeDirCount()).toBe(1);
    expect(component.missingCount()).toBe(1);
    expect(component.filteredTracks().length).toBe(3);

    component.setLocationFilter('active');
    expect(component.filteredTracks().length).toBe(1);
    expect(component.filteredTracks()[0].id).toBe('t-active');

    component.setLocationFilter('missing');
    expect(component.filteredTracks().length).toBe(1);
    expect(component.filteredTracks()[0].id).toBe('t-missing');
  });

  it('should toggle selection mode and clear selection when turned off', () => {
    expect(component.isSelectionMode()).toBe(false);

    component.toggleSelectionMode();
    expect(component.isSelectionMode()).toBe(true);

    component.toggleTrackSelection(dummyTrack);
    expect(component.selectedTrackIds().has(dummyTrack.id)).toBe(true);

    component.toggleSelectionMode();
    expect(component.isSelectionMode()).toBe(false);
    expect(component.selectedTrackIds().size).toBe(0);
  });

  it('should handle select all and clear selection correctly', () => {
    component.tracks.set([
      dummyTrack,
      { ...dummyTrack, id: 'track-2', display_title: 'Track 2' },
    ]);
    component.toggleSelectionMode();

    expect(component.isAllSelected()).toBe(false);
    component.toggleSelectAll();
    expect(component.isAllSelected()).toBe(true);
    expect(component.selectedTrackIds().size).toBe(2);

    component.clearSelection();
    expect(component.selectedTrackIds().size).toBe(0);
  });

  it('should open context menu for track with right-click or options event', () => {
    const mouseEvent = new MouseEvent('contextmenu', { clientX: 250, clientY: 350 });
    component.openTrackContextMenu(dummyTrack, mouseEvent);

    expect(mockContextMenu.open).toHaveBeenCalledWith(
      expect.objectContaining({
        x: 250,
        y: 350,
        items: expect.any(Array),
      })
    );
  });

  it('should batch delete selected tracks when confirmed', async () => {
    component.tracks.set([dummyTrack]);
    component.toggleSelectionMode();
    component.toggleTrackSelection(dummyTrack);

    await component.deleteSelectedTracks();

    expect(mockConfirmDialog.confirm).toHaveBeenCalled();
    expect(mockLibraryApi.deleteTracksBatch).toHaveBeenCalledWith([dummyTrack.id], true);
    expect(component.selectedTrackIds().size).toBe(0);
    expect(component.isSelectionMode()).toBe(false);
  });

  it('should abort batch delete if confirm dialog is rejected', async () => {
    mockConfirmDialog.confirm.mockResolvedValueOnce(false);
    component.tracks.set([dummyTrack]);
    component.toggleSelectionMode();
    component.toggleTrackSelection(dummyTrack);

    await component.deleteSelectedTracks();

    expect(mockConfirmDialog.confirm).toHaveBeenCalled();
    expect(mockLibraryApi.deleteTracksBatch).not.toHaveBeenCalled();
    expect(component.selectedTrackIds().size).toBe(1);
    expect(component.isSelectionMode()).toBe(true);
  });
});
