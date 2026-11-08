import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SettingsComponent } from './settings.component';
import { SettingsApiService } from '../../data/settings-api.service';
import { BackupApiService } from '../../data/backup-api.service';
import { ToastService } from '../../core/services/toast.service';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import { UserPreferencesService } from '../../core/services/user-preferences.service';
import { AppSettings, MeloSyncBackupPayload, ImportBackupResult } from '../../domain/models';
import { of, throwError } from 'rxjs';

describe('SettingsComponent', () => {
  let component: SettingsComponent;
  let fixture: ComponentFixture<SettingsComponent>;

  const mockSettings: AppSettings = {
    music_download_directory: 'C:/Music/meloSync',
    default_audio_quality: 'best',
    normalize_audio_lufs: -14.0,
    auto_tag_metadata: true,
    skip_non_music_sections: true,
    trim_silence: true,
    backend_version: '2.1.0-test',
  };

  let settingsApiMock: {
    getSettings: ReturnType<typeof vi.fn>;
    updateSettings: ReturnType<typeof vi.fn>;
    getStorageStats: ReturnType<typeof vi.fn>;
    browseFolder: ReturnType<typeof vi.fn>;
    consolidateLibrary: ReturnType<typeof vi.fn>;
    openMusicFolder: ReturnType<typeof vi.fn>;
  };

  let toastMock: {
    success: ReturnType<typeof vi.fn>;
    error: ReturnType<typeof vi.fn>;
    info: ReturnType<typeof vi.fn>;
  };

  let coverCacheMock: {
    stats: ReturnType<typeof vi.fn>;
    clear: ReturnType<typeof vi.fn>;
  };

  let userPrefsMock: {
    get: ReturnType<typeof vi.fn>;
    set: ReturnType<typeof vi.fn>;
    preferences: ReturnType<typeof vi.fn>;
    update: ReturnType<typeof vi.fn>;
    taskbarControlsEnabled: ReturnType<typeof vi.fn>;
  };

  let backupApiMock: {
    exportBackup: ReturnType<typeof vi.fn>;
    importBackup: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    settingsApiMock = {
      getSettings: vi.fn().mockReturnValue(of(mockSettings)),
      updateSettings: vi.fn().mockReturnValue(of(mockSettings)),
      getStorageStats: vi.fn().mockReturnValue(of({
        active_directory: 'C:/Music/meloSync',
        active_dir_track_count: 10,
        other_locations_track_count: 2,
        missing_files_count: 0,
        total_library_tracks: 12,
        active_dir_size_bytes: 104857600,
        active_dir_size_formatted: '100.0 MB',
      })),
      browseFolder: vi.fn().mockReturnValue(of({ path: 'D:/NewFolder' })),
      consolidateLibrary: vi.fn().mockReturnValue(of({
        moved_count: 2,
        already_there_count: 10,
        missing_count: 0,
        total_tracks: 12,
        target_directory: 'D:/NewFolder',
        message: 'Consolidación exitosa',
      })),
      openMusicFolder: vi.fn().mockReturnValue(of({ message: 'Carpeta abierta', path: mockSettings.music_download_directory }))
    };

    backupApiMock = {
      exportBackup: vi.fn().mockReturnValue(of({
        format: 'melosync-backup',
        version: 1,
        exported_at_iso: '2026-11-07T12:00:00Z',
        app_version: '2.0.0',
        settings: {
          default_audio_quality: 'best',
          normalize_audio_lufs: -14.0,
          auto_tag_metadata: true,
          user_preferences: {}
        },
        tracks: [],
        playlists: []
      })),
      importBackup: vi.fn().mockReturnValue(of({
        status: 'success',
        message: 'Importación exitosa',
        total_tracks_in_backup: 1,
        tracks_imported: 1,
        tracks_already_present: 0,
        tracks_queued_for_download: 1,
        playlists_imported: 0,
        settings_restored: true,
        user_preferences: {}
      }))
    };

    toastMock = {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    };

    coverCacheMock = {
      stats: vi.fn().mockReturnValue({
        entryCount: 42,
        maxEntries: 500,
        estimatedMemoryBytes: 8 * 1024 * 1024,
        estimatedMemoryDisplay: '8.00 MB'
      }),
      clear: vi.fn()
    };

    userPrefsMock = {
      get: vi.fn().mockReturnValue(0.3),
      set: vi.fn(),
      preferences: vi.fn().mockReturnValue({}),
      update: vi.fn(),
      taskbarControlsEnabled: vi.fn().mockReturnValue(true)
    };

    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        { provide: SettingsApiService, useValue: settingsApiMock },
        { provide: BackupApiService, useValue: backupApiMock },
        { provide: ToastService, useValue: toastMock },
        { provide: CoverCacheService, useValue: coverCacheMock },
        { provide: UserPreferencesService, useValue: userPrefsMock }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(SettingsComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the component and load initial settings with frontend and backend versions', () => {
    expect(component).toBeTruthy();
    expect(settingsApiMock.getSettings).toHaveBeenCalled();
    expect(component.downloadDir()).toBe('C:/Music/meloSync');
    expect(component.selectedQuality()).toBe('best');
    expect(component.normalizeLufs()).toBe(-14.0);
    expect(component.autoTag()).toBe(true);
    expect(component.fuzzyThreshold()).toBe(0.3);
    expect(component.isDirty()).toBe(false);

    // Verify versions
    expect(component.frontendVersion).toBe('1.1.0');
    expect(component.backendVersion()).toBe('2.1.0-test');
  });

  it('should filter section visibility based on search query and category', () => {
    // When no search query and 'all' category, all sections are visible
    expect(component.isSectionVisible('general')).toBe(true);
    expect(component.isSectionVisible('audio')).toBe(true);
    expect(component.isSectionVisible('storage')).toBe(true);
    expect(component.isSectionVisible('about')).toBe(true);

    // Filter by search query "lufs"
    component.searchQuery.set('lufs');
    expect(component.isSectionVisible('audio')).toBe(true);
    expect(component.isSectionVisible('general')).toBe(false);
    expect(component.isSectionVisible('storage')).toBe(false);
    expect(component.hasAnyMatchingSection()).toBe(true);

    // Filter by query "caratula"
    component.searchQuery.set('caratula');
    expect(component.isSectionVisible('general')).toBe(true);
    expect(component.isSectionVisible('storage')).toBe(true);
    expect(component.isSectionVisible('audio')).toBe(false);

    // Clear search
    component.clearSearch();
    expect(component.searchQuery()).toBe('');
    expect(component.isSectionVisible('general')).toBe(true);
  });

  it('should switch categories with setCategory', () => {
    expect(component.activeCategory()).toBe('all');
    component.setCategory('audio');
    expect(component.activeCategory()).toBe('audio');
    expect(component.isSectionVisible('audio')).toBe(true);
    expect(component.isSectionVisible('general')).toBe(false);

    component.setCategory('storage');
    expect(component.activeCategory()).toBe('storage');
    expect(component.isSectionVisible('storage')).toBe(true);
    expect(component.isSectionVisible('audio')).toBe(false);
  });

  it('should track dirty state when values are modified and reset on resetChanges', () => {
    expect(component.isDirty()).toBe(false);

    // Modify a value
    component.downloadDir.set('D:/New/Path');
    expect(component.isDirty()).toBe(true);

    // Reset back to original
    component.resetChanges();
    expect(component.downloadDir()).toBe('C:/Music/meloSync');
    expect(component.isDirty()).toBe(false);
  });

  it('should reset LUFS to -14.0 standard via resetToStandardLufs', () => {
    component.normalizeLufs.set(-18.5);
    expect(component.normalizeLufs()).toBe(-18.5);

    component.resetToStandardLufs();
    expect(component.normalizeLufs()).toBe(-14.0);
  });

  it('should save settings, update UserPreferencesService, and display a success toast', () => {
    component.selectedQuality.set('320k');
    component.fuzzyThreshold.set(0.45);
    expect(component.isDirty()).toBe(true);

    const updatedSettings: AppSettings = {
      ...mockSettings,
      default_audio_quality: '320k',
      backend_version: '2.1.0-updated'
    };
    settingsApiMock.updateSettings.mockReturnValue(of(updatedSettings));

    component.saveSettings();

    expect(settingsApiMock.updateSettings).toHaveBeenCalledWith({
      music_download_directory: 'C:/Music/meloSync',
      default_audio_quality: '320k',
      normalize_audio_lufs: -14.0,
      auto_tag_metadata: true,
      skip_non_music_sections: true,
      trim_silence: true,
    });
    expect(userPrefsMock.set).toHaveBeenCalledWith('defaultSearchProximityThreshold', 0.45);
    expect(toastMock.success).toHaveBeenCalledWith('Preferencias guardadas correctamente');
    expect(component.backendVersion()).toBe('2.1.0-updated');
    expect(component.isDirty()).toBe(false);
  });

  it('should handle error when saving settings', () => {
    settingsApiMock.updateSettings.mockReturnValue(throwError(() => new Error('Disk full')));

    component.saveSettings();

    expect(component.isSaving()).toBe(false);
    expect(toastMock.error).toHaveBeenCalledWith('Error al guardar ajustes', 'Disk full');
  });

  it('should call clearCoverCache and display toast notification', () => {
    component.clearCoverCache();
    expect(coverCacheMock.clear).toHaveBeenCalled();
    expect(toastMock.success).toHaveBeenCalledWith('Caché Limpiada', expect.stringContaining('Se ha liberado la memoria'));
  });

  it('should call openFolder and display toast', () => {
    component.openFolder();
    expect(settingsApiMock.openMusicFolder).toHaveBeenCalled();
    expect(toastMock.info).toHaveBeenCalledWith('Carpeta abierta en explorador');
  });

  it('should compute cache percentage correctly', () => {
    // 42 out of 500 = ~8%
    expect(component.cachePercentage()).toBe(8);
  });

  it('should trigger backup export, call BackupApiService and notify user with toast', () => {
    component.exportBackup();
    expect(backupApiMock.exportBackup).toHaveBeenCalled();
    expect(toastMock.success).toHaveBeenCalledWith('Respaldo exportado', expect.stringContaining('Se exportaron'));
  });

  it('should execute import, update user preferences, reload settings and display result', () => {
    const mockPayload: MeloSyncBackupPayload = {
      format: 'melosync-backup',
      version: 1,
      exported_at_iso: '2026-11-07T12:00:00Z',
      app_version: '2.0.0',
      settings: {
        default_audio_quality: '320k',
        normalize_audio_lufs: -14.0,
        auto_tag_metadata: true,
        user_preferences: { libraryViewMode: 'grid' }
      },
      tracks: [],
      playlists: []
    };

    component.importPreview.set(mockPayload);
    component.executeImport();

    expect(backupApiMock.importBackup).toHaveBeenCalledWith(mockPayload, expect.objectContaining({
      download_missing_audio: true,
      restore_settings: true,
      restore_preferences: true,
    }));
    expect(toastMock.success).toHaveBeenCalledWith('Importación completada', expect.stringContaining('canciones añadidas'));
    expect(component.importPreview()).toBeNull();
    expect(component.importResult()).toBeTruthy();
  });

  it('should load storage stats and call browseFolder', () => {
    expect(settingsApiMock.getStorageStats).toHaveBeenCalled();
    expect(component.storageStats()?.active_dir_track_count).toBe(10);

    component.browseFolder();
    expect(settingsApiMock.browseFolder).toHaveBeenCalled();
    expect(component.downloadDir()).toBe('D:/NewFolder');
  });

  it('should show folder change modal when changing directory with existing tracks', () => {
    component.downloadDir.set('E:/AnotherFolder');
    component.saveSettings();

    expect(component.showFolderChangeModal()).toBe(true);
  });

  it('should consolidate library and close modal when confirmConsolidateAndSave is called', () => {
    component.downloadDir.set('D:/NewFolder');
    component.showFolderChangeModal.set(true);

    component.confirmConsolidateAndSave();
    expect(settingsApiMock.updateSettings).toHaveBeenCalled();
    expect(settingsApiMock.consolidateLibrary).toHaveBeenCalledWith('D:/NewFolder', true);
    expect(component.showFolderChangeModal()).toBe(false);
  });
});
