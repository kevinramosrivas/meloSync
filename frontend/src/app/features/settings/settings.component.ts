import { Component, inject, signal, computed, OnInit } from '@angular/core';
import { SettingsApiService } from '../../data/settings-api.service';
import { ToastService } from '../../core/services/toast.service';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import { UserPreferencesService } from '../../core/services/user-preferences.service';
import { AppSettings, AudioQuality } from '../../domain/models';
import { IconComponent, IconName } from '../../shared/components/icon/icon.component';
import { environment } from '../../../environments/environment';

export type SettingsCategory = 'all' | 'general' | 'audio' | 'storage' | 'about';

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

const SECTION_KEYWORDS: Record<'general' | 'audio' | 'storage' | 'about', string[]> = {
  general: ['directorio', 'carpeta', 'descargas', 'almacenamiento', 'itunes', 'metadatos', 'etiquetas', 'caratula', 'busqueda', 'difusa', 'tolerancia', 'fuzzy', 'general'],
  audio: ['calidad', 'audio', 'bitrate', 'flac', 'opus', 'mp3', '320', '256', '128', 'normalizacion', 'volumen', 'lufs', 'sound check', 'loudnorm', 'ffmpeg', 'reproduccion'],
  storage: ['cache', 'caratulas', 'memoria', 'lru', 'almacenamiento', 'vaciar', 'ram', 'limpieza', 'purgar'],
  about: ['acerca', 'version', 'frontend', 'backend', 'fastapi', 'angular', 'tauri', 'rust', 'sidecar', 'sistema', 'servidor', 'desktop']
};

@Component({
  selector: 'app-settings',
  imports: [IconComponent],
  templateUrl: './settings.component.html'
})
export class SettingsComponent implements OnInit {
  private settingsApi = inject(SettingsApiService);
  private toast = inject(ToastService);
  private userPrefs = inject(UserPreferencesService);
  readonly coverCache = inject(CoverCacheService);

  readonly frontendVersion = environment.frontendVersion;
  readonly backendVersion = signal<string>('2.0.0');

  readonly isLoading = signal<boolean>(false);
  readonly isSaving = signal<boolean>(false);
  readonly activeCategory = signal<SettingsCategory>('all');
  readonly searchQuery = signal<string>('');

  // Form values managed via Signals
  readonly downloadDir = signal<string>('');
  readonly selectedQuality = signal<AudioQuality>('best');
  readonly normalizeLufs = signal<number>(-14.0);
  readonly autoTag = signal<boolean>(true);
  readonly fuzzyThreshold = signal<number>(0.3);

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
      this.fuzzyThreshold() !== this.originalFuzzyThreshold()
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
      this.isSectionVisible('about')
    );
  });

  ngOnInit(): void {
    this.loadSettings();
  }

  setCategory(category: SettingsCategory): void {
    this.activeCategory.set(category);
  }

  isSectionVisible(section: 'general' | 'audio' | 'storage' | 'about'): boolean {
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
        if (s.backend_version) {
          this.backendVersion.set(s.backend_version);
        }
        this.isLoading.set(false);
      },
      error: (e: Error) => {
        this.isLoading.set(false);
        this.toast.error('Error al cargar ajustes', e.message);
      }
    });
  }

  saveSettings(): void {
    this.isSaving.set(true);
    this.settingsApi.updateSettings({
      music_download_directory: this.downloadDir(),
      default_audio_quality: this.selectedQuality(),
      normalize_audio_lufs: this.normalizeLufs(),
      auto_tag_metadata: this.autoTag(),
    }).subscribe({
      next: (s) => {
        this.isSaving.set(false);
        this.originalSettings.set(s);
        this.downloadDir.set(s.music_download_directory);
        this.selectedQuality.set(s.default_audio_quality);
        this.normalizeLufs.set(s.normalize_audio_lufs);
        this.autoTag.set(s.auto_tag_metadata);
        if (s.backend_version) {
          this.backendVersion.set(s.backend_version);
        }

        // Guardar preferencia de proximidad en búsquedas difusas
        this.userPrefs.set('defaultSearchProximityThreshold', this.fuzzyThreshold());
        this.originalFuzzyThreshold.set(this.fuzzyThreshold());

        this.toast.success('Preferencias guardadas correctamente');
      },
      error: (e: Error) => {
        this.isSaving.set(false);
        this.toast.error('Error al guardar ajustes', e.message);
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
    }
    this.fuzzyThreshold.set(this.originalFuzzyThreshold());
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
}
