import { ComponentFixture, TestBed } from '@angular/core/testing';
import { SettingsComponent } from './settings.component';
import { SettingsApiService } from '../../data/settings-api.service';
import { ToastService } from '../../core/services/toast.service';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import { UserPreferencesService } from '../../core/services/user-preferences.service';
import { AppSettings } from '../../domain/models';
import { of, throwError } from 'rxjs';

describe('SettingsComponent', () => {
  let component: SettingsComponent;
  let fixture: ComponentFixture<SettingsComponent>;

  const mockSettings: AppSettings = {
    music_download_directory: 'C:/Music/meloSync',
    default_audio_quality: 'best',
    normalize_audio_lufs: -14.0,
    auto_tag_metadata: true,
    backend_version: '2.1.0-test',
  };

  let settingsApiMock: {
    getSettings: ReturnType<typeof vi.fn>;
    updateSettings: ReturnType<typeof vi.fn>;
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
  };

  beforeEach(async () => {
    settingsApiMock = {
      getSettings: vi.fn().mockReturnValue(of(mockSettings)),
      updateSettings: vi.fn().mockReturnValue(of(mockSettings)),
      openMusicFolder: vi.fn().mockReturnValue(of({ message: 'Carpeta abierta', path: mockSettings.music_download_directory }))
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
      set: vi.fn()
    };

    await TestBed.configureTestingModule({
      imports: [SettingsComponent],
      providers: [
        { provide: SettingsApiService, useValue: settingsApiMock },
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
    expect(component.frontendVersion).toBe('1.0.1');
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
});
