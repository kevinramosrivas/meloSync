import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { PlaylistsApiService } from './playlists-api.service';
import { API_CONFIG } from '../core/config/api.config';
import { PlaylistsGroupedResponse, Playlist } from '../domain/models';

describe('PlaylistsApiService', () => {
  let service: PlaylistsApiService;
  let httpTesting: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [
        PlaylistsApiService,
        provideHttpClient(),
        provideHttpClientTesting(),
      ],
    });

    service = TestBed.inject(PlaylistsApiService);
    httpTesting = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpTesting.verify();
  });

  it('should fetch grouped playlists', () => {
    const mockResponse: PlaylistsGroupedResponse = {
      user_playlists: [],
      for_you_playlists: [],
      artist_playlists: [],
      genre_playlists: [],
    };

    service.getPlaylists().subscribe((data) => {
      expect(data).toEqual(mockResponse);
    });

    const req = httpTesting.expectOne(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlists}`);
    expect(req.request.method).toBe('GET');
    req.flush(mockResponse);
  });

  it('should fetch single playlist detail', () => {
    const mockPlaylist: Playlist = {
      id: 'p-1',
      name: 'Rock Classics',
      description: 'Desc',
      is_smart: false,
      playlist_type: 'custom',
      track_count: 0,
      duration_seconds: 0,
      created_at_iso: '',
      updated_at_iso: '',
      tracks: [],
    };

    service.getPlaylist('p-1').subscribe((data) => {
      expect(data.name).toBe('Rock Classics');
    });

    const req = httpTesting.expectOne(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistDetail('p-1')}`);
    expect(req.request.method).toBe('GET');
    req.flush(mockPlaylist);
  });

  it('should create playlist', () => {
    service.createPlaylist({ name: 'Party' }).subscribe((data) => {
      expect(data.name).toBe('Party');
    });

    const req = httpTesting.expectOne(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlists}`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'Party' });
    req.flush({ id: 'new-id', name: 'Party', tracks: [] });
  });

  it('should add track to playlist', () => {
    service.addTrackToPlaylist('p-1', 'track-123').subscribe((data) => {
      expect(data.id).toBe('p-1');
    });

    const req = httpTesting.expectOne(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistTracks('p-1')}`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ track_id: 'track-123' });
    req.flush({ id: 'p-1', tracks: [] });
  });

  it('should remove track from playlist', () => {
    service.removeTrackFromPlaylist('p-1', 'track-123').subscribe();

    const req = httpTesting.expectOne(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistTrackDelete('p-1', 'track-123')}`);
    expect(req.request.method).toBe('DELETE');
    req.flush({ id: 'p-1', tracks: [] });
  });

  it('should trigger smart playlists sync', () => {
    service.syncSmartPlaylists().subscribe((res) => {
      expect(res.message).toBe('ok');
    });

    const req = httpTesting.expectOne(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistsSync}`);
    expect(req.request.method).toBe('POST');
    req.flush({ message: 'ok' });
  });
});
