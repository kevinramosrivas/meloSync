import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { Router } from '@angular/router';
import { SettingsApiService } from '../../data/settings-api.service';
import { BackupApiService } from '../../data/backup-api.service';
import { ToastService } from '../../core/services/toast.service';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import { UserPreferencesService } from '../../core/services/user-preferences.service';
import { AppSettings, AudioQuality, ConsolidateReport, ImportBackupResult, MeloSyncBackupPayload, StorageStats } from '../../domain/models';
import { IconComponent, IconName } from '../../shared/components/icon/icon.component';
import { environment } from '../../../environments/environment';

export type SettingsCategory = 'all' | 'general' | 'audio' | 'storage' | 'backup' | 'about';

export interface QualityOption {
  label: string;
  value: AudioQuality;
  desc: string;
  badge: string;
}

export interface SettingsCategoryItem {
  id: SettingsCategory;
  label: string;
  icon: IconName;
}

const SECTION_KEYWORDS: Record<'general' | 'audio' | 'storage' | 'backup' | 'about', string[]> = {
  general: ['directorio', 'carpeta', 'descargas', 'almacenamiento', 'itunes', 'metadatos', 'etiquetas', 'caratula', 'busqueda', 'difusa', 'tolerancia', 'fuzzy', 'general'],
  audio: ['calidad', 'audio', 'bitrate', 'flac', 'opus', 'mp3', '320', '256', '128', 'normalizacion', 'volumen', 'lufs', 'sound check', 'loudnorm', 'ffmpeg', 'reproduccion', 'intros', 'sponsorblock', 'silencios', 'vacios', 'recorte'],
  storage: ['cache', 'caratulas', 'memoria', 'lru', 'almacenamiento', 'vaciar', 'ram', 'limpieza', 'purgar'],
  backup: ['copia', 'seguridad', 'respaldo', 'backup', 'exportar', 'importar', 'migracion', 'json', 'restaurar', 'transferir', 'sincronizacion'],
  about: ['acerca', 'version', 'frontend', 'backend', 'fastapi', 'angular', 'tauri', 'rust', 'sidecar', 'sistema', 'servidor', 'desktop']
};

@Component({
  selector: 'app-settings',
  imports: [IconComponent],
  templateUrl: './settings.component.html'
})
export class SettingsComponent implements OnInit {
  private settingsApi = inject(SettingsApiService);
  private backupApi = inject(BackupApiService);
  private toast = inject(ToastService);
  private userPrefs = inject(UserPreferencesService);
  private router = inject(Router);
  readonly coverCache = inject(CoverCacheService);

  readonly frontendVersion = environment.frontendVersion;
  readonly backendVersion = signal<string>('2.1.0');

  readonly isLoading = signal<boolean>(false);
  readonly isSaving = signal<boolean>(false);
  readonly activeCategory = signal<SettingsCategory>('all');
  readonly searchQuery = signal<string>('');

  // Backup & Migration Signals
  readonly isExporting = signal<boolean>(false);
  readonly isImporting = signal<boolean>(false);
  readonly importPreview = signal<MeloSyncBackupPayload | null>(null);
  readonly selectedFileName = signal<string>('');
  readonly downloadMissingAudio = signal<boolean>(true);
  readonly restoreSettingsOption = signal<boolean>(true);
  readonly restorePreferencesOption = signal<boolean>(true);
  readonly overwriteMetadataOption = signal<boolean>(false);
  readonly importResult = signal<ImportBackupResult | null>(null);

  // Form values managed via Signals
  readonly downloadDir = signal<string>('');
  readonly selectedQuality = signal<AudioQuality>('best');
  readonly normalizeLufs = signal<number>(-14.0);
  readonly autoTag = signal<boolean>(true);
  readonly skipNonMusic = signal<boolean>(true);
  readonly trimSilence = signal<boolean>(true);
  readonly fuzzyThreshold = signal<number>(0.3);
  readonly taskbarControls = signal<boolean>(this.userPrefs.taskbarControlsEnabled());
  readonly originalTaskbarControls = signal<boolean>(this.userPrefs.taskbarControlsEnabled());
  readonly isWindows = signal<boolean>(
    typeof navigator !== 'undefined' &&
    /Windows|Win32|Win64/i.test(navigator.userAgent || (navigator as unknown as { platform?: string }).platform || '')
  );

  // Storage Stats & Migration Signals
  readonly storageStats = signal<StorageStats | null>(null);
  readonly isLoadingStats = signal<boolean>(false);
  readonly showFolderChangeModal = signal<boolean>(false);
  readonly isConsolidating = signal<boolean>(false);

  // Snapshot of loaded settings to detect changes (dirty state)
  readonly originalSettings = signal<AppSettings | null>(null);
  readonly originalFuzzyThreshold = signal<number>(0.3);

  readonly qualityOptions: QualityOption[] = [
    { label: 'Mejor Calidad', value: 'best', desc: 'Flac/Opus/V0 original', badge: 'LOSSLESS' },
    { label: '320 kbps (CBR)', value: '320k', desc: 'Máxima fidelidad MP3', badge: 'HQ' },
    { label: '256 kbps', value: '256k', desc: 'Excelente balance', badge: 'BALANCED' },
    { label: '128 kbps', value: '128k', desc: 'Ahorro de espacio', badge: 'LIGHT' },
  ];

  readonly categories: SettingsCategoryItem[] = [
    { id: 'all', label: 'Ver Todo', icon: 'grid' },
    { id: 'general', label: 'General', icon: 'folder' },
    { id: 'audio', label: 'Audio y Reproducción', icon: 'headphones' },
    { id: 'storage', label: 'Almacenamiento', icon: 'disc' },
    { id: 'backup', label: 'Copia y Migración', icon: 'download' },
    { id: 'about', label: 'Acerca de', icon: 'info' },
  ];

  readonly isDirty = computed(() => {
    const orig = this.originalSettings();
    if (!orig) return false;
    return (
      this.downloadDir() !== orig.music_download_directory ||
      this.selectedQuality() !== orig.default_audio_quality ||
      this.normalizeLufs() !== orig.normalize_audio_lufs ||
      this.autoTag() !== orig.auto_tag_metadata ||
      this.skipNonMusic() !== (orig.skip_non_music_sections ?? true) ||
      this.trimSilence() !== (orig.trim_silence ?? true) ||
      this.fuzzyThreshold() !== this.originalFuzzyThreshold() ||
      this.taskbarControls() !== this.originalTaskbarControls()
    );
  });

  readonly cachePercentage = computed(() => {
    const stats = this.coverCache.stats();
    if (stats.maxEntries === 0) return 0;
    return Math.min(100, Math.round((stats.entryCount / stats.maxEntries) * 100));
  });

  readonly hasAnyMatchingSection = computed(() => {
    return (
      this.isSectionVisible('general') ||
      this.isSectionVisible('audio') ||
      this.isSectionVisible('storage') ||
      this.isSectionVisible('backup') ||
      this.isSectionVisible('about')
    );
  });

  ngOnInit(): void {
    this.loadSettings();
  }

  setCategory(category: SettingsCategory): void {
    this.activeCategory.set(category);
  }

  isSectionVisible(section: 'general' | 'audio' | 'storage' | 'backup' | 'about'): boolean {
    const categoryMatches = this.activeCategory() === 'all' || this.activeCategory() === section;
    const query = this.searchQuery().trim().toLowerCase();

    if (!query) {
      return categoryMatches;
    }

    const keywords = SECTION_KEYWORDS[section];
    const matchesQuery = keywords.some((kw) => kw.includes(query) || query.includes(kw));
    return categoryMatches && matchesQuery;
  }

  onSearchInput(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    if (target) {
      this.searchQuery.set(target.value);
    }
  }

  clearSearch(): void {
    this.searchQuery.set('');
  }

  loadSettings(): void {
    this.isLoading.set(true);
    const initialFuzzy = this.userPrefs.get('defaultSearchProximityThreshold') ?? 0.3;
    this.fuzzyThreshold.set(initialFuzzy);
    this.originalFuzzyThreshold.set(initialFuzzy);

    this.settingsApi.getSettings().subscribe({
      next: (s) => {
        this.originalSettings.set(s);
        this.downloadDir.set(s.music_download_directory);
        this.selectedQuality.set(s.default_audio_quality);
        this.normalizeLufs.set(s.normalize_audio_lufs);
        this.autoTag.set(s.auto_tag_metadata);
        this.skipNonMusic.set(s.skip_non_music_sections ?? true);
        this.trimSilence.set(s.trim_silence ?? true);
        if (s.backend_version) {
          this.backendVersion.set(s.backend_version);
        }
        this.isLoading.set(false);
        this.loadStorageStats();
      },
      error: (e: Error) => {
        this.isLoading.set(false);
        this.toast.error('Error al cargar ajustes', e.message);
      }
    });
  }

  loadStorageStats(): void {
    this.isLoadingStats.set(true);
    this.settingsApi.getStorageStats().subscribe({
      next: (stats) => {
        this.storageStats.set(stats);
        this.isLoadingStats.set(false);
      },
      error: () => this.isLoadingStats.set(false),
    });
  }

  browseFolder(): void {
    this.settingsApi.browseFolder().subscribe({
      next: (res) => {
        if (res.path) {
          this.downloadDir.set(res.path);
        }
      },
      error: (e: Error) => this.toast.error('No se pudo abrir selector de carpetas', e.message),
    });
  }

  saveSettings(): void {
    const orig = this.originalSettings();
    const dirChanged = orig && this.downloadDir().trim() !== orig.music_download_directory.trim();
    const hasExistingTracks = (this.storageStats()?.total_library_tracks ?? 0) > 0;

    if (dirChanged && hasExistingTracks) {
      this.showFolderChangeModal.set(true);
      return;
    }

    this.executeSave();
  }

  executeSave(onComplete?: () => void): void {
    this.isSaving.set(true);
    this.settingsApi.updateSettings({
      music_download_directory: this.downloadDir(),
      default_audio_quality: this.selectedQuality(),
      normalize_audio_lufs: this.normalizeLufs(),
      auto_tag_metadata: this.autoTag(),
      skip_non_music_sections: this.skipNonMusic(),
      trim_silence: this.trimSilence(),
    }).subscribe({
      next: (s) => {
        this.isSaving.set(false);
        this.originalSettings.set(s);
        this.downloadDir.set(s.music_download_directory);
        this.selectedQuality.set(s.default_audio_quality);
        this.normalizeLufs.set(s.normalize_audio_lufs);
        this.autoTag.set(s.auto_tag_metadata);
        this.skipNonMusic.set(s.skip_non_music_sections ?? true);
        this.trimSilence.set(s.trim_silence ?? true);
        if (s.backend_version) {
          this.backendVersion.set(s.backend_version);
        }

        // Guardar preferencia de proximidad en búsquedas difusas
        this.userPrefs.set('defaultSearchProximityThreshold', this.fuzzyThreshold());
        this.originalFuzzyThreshold.set(this.fuzzyThreshold());

        // Guardar preferencia de controles en barra de tareas de Windows
        this.userPrefs.set('taskbarControlsEnabled', this.taskbarControls());
        this.originalTaskbarControls.set(this.taskbarControls());

        this.loadStorageStats();
        this.toast.success('Preferencias guardadas correctamente');
        if (onComplete) onComplete();
      },
      error: (e: Error) => {
        this.isSaving.set(false);
        this.toast.error('Error al guardar ajustes', e.message);
      }
    });
  }

  confirmConsolidateAndSave(): void {
    this.showFolderChangeModal.set(false);
    this.isConsolidating.set(true);
    const targetDir = this.downloadDir();

    this.executeSave(() => {
      this.settingsApi.consolidateLibrary(targetDir, true).subscribe({
        next: (report) => {
          this.isConsolidating.set(false);
          this.toast.success('Biblioteca Consolidada', report.message);
          this.loadStorageStats();
        },
        error: (err) => {
          this.isConsolidating.set(false);
          this.toast.error('Error al consolidar archivos', err.message);
        }
      });
    });
  }

  saveWithoutConsolidating(): void {
    this.showFolderChangeModal.set(false);
    this.executeSave(() => {
      this.toast.info('Nueva carpeta configurada solo para futuras descargas');
    });
  }

  cancelFolderChange(): void {
    this.showFolderChangeModal.set(false);
  }

  consolidateNow(): void {
    this.isConsolidating.set(true);
    this.settingsApi.consolidateLibrary(this.downloadDir(), true).subscribe({
      next: (report) => {
        this.isConsolidating.set(false);
        this.toast.success('Archivos consolidados', report.message);
        this.loadStorageStats();
      },
      error: (err) => {
        this.isConsolidating.set(false);
        this.toast.error('Error al consolidar', err.message);
      }
    });
  }

  resetChanges(): void {
    const orig = this.originalSettings();
    if (orig) {
      this.downloadDir.set(orig.music_download_directory);
      this.selectedQuality.set(orig.default_audio_quality);
      this.normalizeLufs.set(orig.normalize_audio_lufs);
      this.autoTag.set(orig.auto_tag_metadata);
      this.skipNonMusic.set(orig.skip_non_music_sections ?? true);
      this.trimSilence.set(orig.trim_silence ?? true);
    }
    this.fuzzyThreshold.set(this.originalFuzzyThreshold());
    this.taskbarControls.set(this.originalTaskbarControls());
  }

  resetToStandardLufs(): void {
    this.normalizeLufs.set(-14.0);
  }

  onDownloadDirChange(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    if (target) {
      this.downloadDir.set(target.value);
    }
  }

  onLufsChange(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    if (target) {
      this.normalizeLufs.set(parseFloat(target.value));
    }
  }

  onFuzzyChange(event: Event): void {
    const target = event.target as HTMLInputElement | null;
    if (target) {
      this.fuzzyThreshold.set(parseFloat(target.value));
    }
  }

  openFolder(): void {
    this.settingsApi.openMusicFolder().subscribe({
      next: () => this.toast.info('Carpeta abierta en explorador'),
      error: (e: Error) => this.toast.error('No se pudo abrir carpeta', e.message)
    });
  }

  clearCoverCache(): void {
    this.coverCache.clear();
    this.toast.success('Caché Limpiada', 'Se ha liberado la memoria de carátulas en caché.');
  }

  // ==========================================
  // COPIA DE SEGURIDAD Y MIGRACIÓN
  // ==========================================

  exportBackup(): void {
    this.isExporting.set(true);
    const prefs = this.userPrefs.preferences() as unknown as Record<string, unknown>;

    this.backupApi.exportBackup(prefs).subscribe({
      next: (payload) => {
        this.isExporting.set(false);
        const jsonString = JSON.stringify(payload, null, 2);
        const blob = new Blob([jsonString], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const now = new Date().toISOString().replace(/[:.]/g, '-').slice(0, 19);
        const a = document.createElement('a');
        a.href = url;
        a.download = `melosync_backup_${now}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);

        this.toast.success(
          'Respaldo exportado',
          `Se exportaron ${payload.tracks.length} canciones y ${payload.playlists.length} listas en formato JSON.`
        );
      },
      error: (err: Error) => {
        this.isExporting.set(false);
        this.toast.error('Error al exportar', err.message);
      }
    });
  }

  async onFileSelected(event: Event): Promise<void> {
    const input = event.target as HTMLInputElement;
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    this.selectedFileName.set(file.name);
    this.importResult.set(null);

    try {
      const text = await file.text();
      const data = JSON.parse(text) as MeloSyncBackupPayload;

      if (!data || data.format !== 'melosync-backup') {
        this.toast.error('Archivo no válido', 'El archivo no tiene el formato de respaldo de meloSync.');
        input.value = '';
        return;
      }

      this.importPreview.set(data);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Error desconocido';
      this.toast.error('Error al leer archivo', `No se pudo interpretar el archivo JSON: ${message}`);
      input.value = '';
    }
  }

  cancelImportPreview(): void {
    this.importPreview.set(null);
    this.selectedFileName.set('');
  }

  executeImport(): void {
    const payload = this.importPreview();
    if (!payload) return;

    this.isImporting.set(true);
    this.backupApi.importBackup(payload, {
      download_missing_audio: this.downloadMissingAudio(),
      restore_settings: this.restoreSettingsOption(),
      restore_preferences: this.restorePreferencesOption(),
      overwrite_existing_metadata: this.overwriteMetadataOption(),
    }).subscribe({
      next: (result) => {
        this.isImporting.set(false);
        this.importPreview.set(null);
        this.importResult.set(result);

        // Update frontend user preferences if restored
        if (result.user_preferences && Object.keys(result.user_preferences).length > 0) {
          this.userPrefs.update(result.user_preferences as any);
        }

        // Reload backend settings in view
        this.loadSettings();

        this.toast.success(
          'Importación completada',
          `${result.tracks_imported} canciones añadidas, ${result.tracks_queued_for_download} encoladas para descarga.`
        );
      },
      error: (err: Error) => {
        this.isImporting.set(false);
        this.toast.error('Error al importar', err.message);
      }
    });
  }

  goToDownloads(): void {
    this.router.navigate(['/downloads']);
  }
}
