import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { API_CONFIG } from '../core/config/api.config';
import {
  ImportBackupOptions,
  ImportBackupResult,
  MeloSyncBackupPayload,
} from '../domain/models';

@Injectable({
  providedIn: 'root',
})
export class BackupApiService {
  private http = inject(HttpClient);

  exportBackup(userPreferences?: Record<string, unknown>): Observable<MeloSyncBackupPayload> {
    return this.http.post<MeloSyncBackupPayload>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.backupExport}`,
      { user_preferences: userPreferences ?? {} }
    );
  }

  importBackup(
    backupData: MeloSyncBackupPayload,
    options?: Partial<ImportBackupOptions>
  ): Observable<ImportBackupResult> {
    const defaultOptions: ImportBackupOptions = {
      download_missing_audio: true,
      restore_settings: true,
      restore_preferences: true,
      overwrite_existing_metadata: false,
    };

    return this.http.post<ImportBackupResult>(
      `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.backupImport}`,
      {
        backup_data: backupData,
        options: { ...defaultOptions, ...options },
      }
    );
  }
}

