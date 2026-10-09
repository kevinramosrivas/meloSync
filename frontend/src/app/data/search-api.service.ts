import { Injectable, inject } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import { SearchResult } from '../domain/models';

@Injectable({
  providedIn: 'root'
})
export class SearchApiService {
  private http = inject(HttpClient);

  search(query: string, limit: number = 15): Observable<SearchResult[]> {
    const params = new HttpParams()
      .set('q', query)
      .set('limit', limit.toString());
    return this.http.get<SearchResult[]>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.search}`, { params });
  }

  getVideoInfo(url: string): Observable<SearchResult> {
    const params = new HttpParams().set('url', url);
    return this.http.get<SearchResult>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.search}/info`, { params });
  }
}
