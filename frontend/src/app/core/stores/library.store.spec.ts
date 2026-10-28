import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { of, throwError, Subject } from 'rxjs';
import { LibraryStore } from './library.store';
import { LibraryApiService } from '../../data/library-api.service';
import { WebSocketService } from '../services/websocket.service';
import { Track } from '../../domain/models';

describe('LibraryStore', () => {
  let store: LibraryStore;
  let mockLibraryApi: {
    getLibrary: ReturnType<typeof vi.fn>;
  };
  let mockWs: {
    libraryUpdated: ReturnType<typeof signal<number>>;
    isConnected: ReturnType<typeof signal<boolean>>;
  };

  const sampleTrack: Track = {
    id: 't1',
    youtube_id: 'yt1',
    url: 'https://youtube.com/watch?v=yt1',
    original_title: 'Song 1',
    display_title: 'Song 1',
    display_artist: 'Artist 1',
    display_album: 'Album 1',
    duration_seconds: 200,
    duration_formatted: '3:20',
    channel_name: 'Channel 1',
    status: 'COMPLETADA',
    progress_percent: 100,
    file_exists: true
  };

  beforeEach(() => {
    mockLibraryApi = {
      getLibrary: vi.fn().mockReturnValue(of([sampleTrack]))
    };

    mockWs = {
      libraryUpdated: signal(1000),
      isConnected: signal(false)
    };

    TestBed.configureTestingModule({
      providers: [
        LibraryStore,
        { provide: LibraryApiService, useValue: mockLibraryApi },
        { provide: WebSocketService, useValue: mockWs }
      ]
    });

    store = TestBed.inject(LibraryStore);
  });

  it('should load tracks and cache them in memory so subsequent non-forced calls make 0 HTTP requests', () => {
    store.load(false);
    expect(mockLibraryApi.getLibrary).toHaveBeenCalledTimes(1);
    expect(store.tracks().length).toBe(1);
    expect(store.hasLoaded()).toBe(true);
    expect(store.isInitialLoading()).toBe(false);

    // Simulating rapid tab switches (Library -> Playlists -> Library)
    store.load(false);
    store.load(false);
    store.load(false);

    // Still only 1 HTTP request made!
    expect(mockLibraryApi.getLibrary).toHaveBeenCalledTimes(1);
    expect(store.isInitialLoading()).toBe(false);
  });

  it('should de-duplicate concurrent non-forced load calls while a request is in-flight', () => {
    const pending$ = new Subject<Track[]>();
    mockLibraryApi.getLibrary.mockReturnValue(pending$.asObservable());

    store.load(false);
    store.load(false);
    store.load(false);

    expect(mockLibraryApi.getLibrary).toHaveBeenCalledTimes(1);

    pending$.next([sampleTrack]);
    pending$.complete();

    expect(store.tracks().length).toBe(1);
    expect(store.hasLoaded()).toBe(true);
  });

  it('should set connectionFailed only after exhausting retries when not yet loaded', () => {
    mockLibraryApi.getLibrary.mockReturnValue(throwError(() => new Error('Offline')));
    store.load(true, 8);

    expect(store.hasLoaded()).toBe(false);
    expect(store.isInitialLoading()).toBe(false);
    expect(store.connectionFailed()).toBe(true);
  });

  it('should update and remove tracks in memory cleanly', () => {
    store.load(false);
    store.updateTrackInMemory({ ...sampleTrack, display_title: 'Updated Title' });
    expect(store.tracks()[0].display_title).toBe('Updated Title');

    store.removeTrackFromMemory('t1');
    expect(store.tracks().length).toBe(0);
  });
});

