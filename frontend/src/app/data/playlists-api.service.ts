import { Service, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import {
  CreatePlaylistRequest,
  Playlist,
  PlaylistsGroupedResponse,
  UpdatePlaylistRequest,
} from '../domain/models';

@Service()
export class PlaylistsApiService {
  private readonly http = inject(HttpClient);

  getPlaylists(): Observable<PlaylistsGroupedResponse> {
    return this.http.get<PlaylistsGroupedResponse>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlists}`
    );
  }

  getPlaylist(id: string): Observable<Playlist> {
    return this.http.get<Playlist>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistDetail(id)}`
    );
  }

  createPlaylist(request: CreatePlaylistRequest): Observable<Playlist> {
    return this.http.post<Playlist>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlists}`,
      request
    );
  }

  updatePlaylist(id: string, request: UpdatePlaylistRequest): Observable<Playlist> {
    return this.http.put<Playlist>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistDetail(id)}`,
      request
    );
  }

  deletePlaylist(id: string): Observable<{ message: string; playlist_id: string }> {
    return this.http.delete<{ message: string; playlist_id: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistDetail(id)}`
    );
  }

  addTrackToPlaylist(playlistId: string, trackId: string): Observable<Playlist> {
    return this.http.post<Playlist>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistTracks(playlistId)}`,
      { track_id: trackId }
    );
  }

  removeTrackFromPlaylist(playlistId: string, trackId: string): Observable<Playlist> {
    return this.http.delete<Playlist>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistTrackDelete(playlistId, trackId)}`
    );
  }

  syncSmartPlaylists(): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.playlistsSync}`,
      {}
    );
  }
}
