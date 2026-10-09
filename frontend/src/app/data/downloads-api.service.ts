import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import { DownloadRequest, Track } from '../domain/models';

@Injectable({
  providedIn: 'root'
})
export class DownloadsApiService {
  private http = inject(HttpClient);

  startDownload(request: DownloadRequest): Observable<{ message: string; youtube_id: string; status: string }> {
    return this.http.post<{ message: string; youtube_id: string; status: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.downloads}`,
      request
    );
  }

  getActiveDownloads(): Observable<Track[]> {
    return this.http.get<Track[]>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.downloads}`);
  }

  retryDownload(trackId: string): Observable<{ message: string; track_id: string }> {
    return this.http.post<{ message: string; track_id: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.downloads}/${trackId}/retry`,
      {}
    );
  }
}
