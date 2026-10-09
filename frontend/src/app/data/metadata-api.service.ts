import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import { Track, TrackMetadata } from '../domain/models';

@Injectable({
  providedIn: 'root'
})
export class MetadataApiService {
  private http = inject(HttpClient);

  searchCandidates(query: string, limit: number = 15): Observable<TrackMetadata[]> {
    const params = new HttpParams()
      .set('q', query)
      .set('limit', limit.toString());
    return this.http.get<TrackMetadata[]>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.metadata}/candidates`, { params });
  }

  updateTrackMetadata(trackId: string, metadata: Partial<TrackMetadata>): Observable<Track> {
    return this.http.put<Track>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.metadata}/tracks/${trackId}`,
      metadata
    );
  }
}
