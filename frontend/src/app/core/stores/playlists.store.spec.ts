import { TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { of, throwError, Subject } from 'rxjs';
import { PlaylistsStore } from './playlists.store';
import { PlaylistsApiService } from '../../data/playlists-api.service';
import { WebSocketService } from '../services/websocket.service';
import { PlaylistsGroupedResponse } from '../../domain/models';

describe('PlaylistsStore', () => {
  let store: PlaylistsStore;
  let mockPlaylistsApi: {
    getPlaylists: ReturnType<typeof vi.fn>;
  };
  let mockWs: {
    libraryUpdated: ReturnType<typeof signal<number>>;
    isConnected: ReturnType<typeof signal<boolean>>;
  };

  const sampleResponse: PlaylistsGroupedResponse = {
    user_playlists: [
      {
        id: 'p1',
        name: 'Favorites',
        description: 'My favs',
        is_smart: false,
        playlist_type: 'custom',
        track_count: 5,
        duration_seconds: 900,
        created_at_iso: '2026-10-27T00:00:00Z',
        updated_at_iso: '2026-10-27T00:00:00Z'
      }
    ],
    for_you_playlists: [],
    artist_playlists: [],
    genre_playlists: []
  };

  beforeEach(() => {
    mockPlaylistsApi = {
      getPlaylists: vi.fn().mockReturnValue(of(sampleResponse))
    };

    mockWs = {
      libraryUpdated: signal(1000),
      isConnected: signal(false)
    };

    TestBed.configureTestingModule({
      providers: [
        PlaylistsStore,
        { provide: PlaylistsApiService, useValue: mockPlaylistsApi },
        { provide: WebSocketService, useValue: mockWs }
      ]
    });

    store = TestBed.inject(PlaylistsStore);
  });

  it('should load playlists once and serve cached playlists instantaneously on rapid tab switches', () => {
    store.load(false);
    expect(mockPlaylistsApi.getPlaylists).toHaveBeenCalledTimes(1);
    expect(store.userPlaylists().length).toBe(1);
    expect(store.hasLoaded()).toBe(true);
    expect(store.isInitialLoading()).toBe(false);

    // Rapid tab switches
    store.load(false);
    store.load(false);

    expect(mockPlaylistsApi.getPlaylists).toHaveBeenCalledTimes(1);
    expect(store.isInitialLoading()).toBe(false);
  });

  it('should de-duplicate concurrent in-flight requests', () => {
    const pending$ = new Subject<PlaylistsGroupedResponse>();
    mockPlaylistsApi.getPlaylists.mockReturnValue(pending$.asObservable());

    store.load(false);
    store.load(false);

    expect(mockPlaylistsApi.getPlaylists).toHaveBeenCalledTimes(1);

    pending$.next(sampleResponse);
    pending$.complete();

    expect(store.userPlaylists().length).toBe(1);
  });

  it('should set connectionFailed after retry exhaustion without throwing uncaught errors', () => {
    mockPlaylistsApi.getPlaylists.mockReturnValue(throwError(() => new Error('Backend starting')));
    store.load(true, 8);

    expect(store.hasLoaded()).toBe(false);
    expect(store.isInitialLoading()).toBe(false);
    expect(store.connectionFailed()).toBe(true);
  });
});

