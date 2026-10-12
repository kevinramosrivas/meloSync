import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import { DownloadStatus, SyncReport, Track } from '../domain/models';

@Injectable({
  providedIn: 'root'
})
export class LibraryApiService {
  private http = inject(HttpClient);

  getLibrary(status?: DownloadStatus): Observable<Track[]> {
    let params = new HttpParams();
    if (status) {
      params = params.set('status', status);
    }
    return this.http.get<Track[]>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.library}`, { params });
  }

  getTrack(trackId: string): Observable<Track> {
    return this.http.get<Track>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.library}/${trackId}`);
  }

  deleteTrack(trackId: string, deleteFile: boolean = true): Observable<{ message: string; track_id: string }> {
    const params = new HttpParams().set('delete_file', deleteFile.toString());
    return this.http.delete<{ message: string; track_id: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.library}/${trackId}`,
      { params }
    );
  }

  openInSystemPlayer(trackId: string): Observable<{ message: string; file_path: string }> {
    return this.http.post<{ message: string; file_path: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.openFile(trackId)}`,
      {}
    );
  }

  openContainingFolder(trackId: string): Observable<{ message: string }> {
    return this.http.post<{ message: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.openFolder(trackId)}`,
      {}
    );
  }

  syncLibrary(): Observable<SyncReport> {
    return this.http.post<SyncReport>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.library}/sync`,
      {}
    );
  }
}
