import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import { AppSettings, ConsolidateReport, StorageStats, UpdateSettingsRequest } from '../domain/models';

@Injectable({
  providedIn: 'root'
})
export class SettingsApiService {
  private http = inject(HttpClient);

  getSettings(): Observable<AppSettings> {
    return this.http.get<AppSettings>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.settings}`);
  }

  updateSettings(settings: UpdateSettingsRequest): Observable<AppSettings> {
    return this.http.put<AppSettings>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.settings}`, settings);
  }

  getStorageStats(): Observable<StorageStats> {
    return this.http.get<StorageStats>(`${API_CONFIG.baseUrl}${API_CONFIG.endpoints.settings}/storage-stats`);
  }

  browseFolder(): Observable<{ path: string | null }> {
    return this.http.post<{ path: string | null }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.settings}/browse-folder`,
      {}
    );
  }

  consolidateLibrary(targetDirectory?: string, moveFiles: boolean = true): Observable<ConsolidateReport> {
    return this.http.post<ConsolidateReport>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.settings}/consolidate`,
      { target_directory: targetDirectory, move_files: moveFiles }
    );
  }

  openMusicFolder(): Observable<{ message: string; path: string }> {
    return this.http.post<{ message: string; path: string }>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.settings}/open-folder`,
      {}
    );
  }
}
