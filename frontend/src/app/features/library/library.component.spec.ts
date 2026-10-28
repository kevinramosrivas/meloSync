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
import { LIBRARY_VIEW_MODES } from '../../core/constants/preferences.constants';
import { Track } from '../../domain/models';

describe('LibraryComponent', () => {
  let component: LibraryComponent;
  let fixture: ComponentFixture<LibraryComponent>;

  let mockLibraryApi: {
    getLibrary: ReturnType<typeof vi.fn>;
    syncLibrary: ReturnType<typeof vi.fn>;
    deleteTrack: ReturnType<typeof vi.fn>;
    openContainingFolder: ReturnType<typeof vi.fn>;
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
      openContainingFolder: vi.fn().mockReturnValue(of({ success: true }))
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
        { provide: CoverCacheService, useValue: mockCoverCache }
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
});
