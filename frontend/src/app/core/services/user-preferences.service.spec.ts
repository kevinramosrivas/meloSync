import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { UserPreferencesService, DEFAULT_USER_PREFERENCES } from './user-preferences.service';
import { LIBRARY_VIEW_MODES, STORAGE_KEYS } from '../constants/preferences.constants';

// Mock localStorage for test environment if running under pure Node
class LocalStorageMock {
  private store: Record<string, string> = {};

  clear() {
    this.store = {};
  }

  getItem(key: string): string | null {
    return this.store[key] ?? null;
  }

  setItem(key: string, value: string) {
    this.store[key] = String(value);
  }

  removeItem(key: string) {
    delete this.store[key];
  }
}

if (typeof globalThis.localStorage === 'undefined') {
  Object.defineProperty(globalThis, 'localStorage', {
    value: new LocalStorageMock(),
    writable: true,
    configurable: true
  });
}

describe('UserPreferencesService', () => {
  let service: UserPreferencesService;

  beforeEach(() => {
    localStorage.clear();
    service = new UserPreferencesService();
  });

  afterEach(() => {
    localStorage.clear();
  });

  it('should initialize with default preferences prioritizing list view and expanded sidebar', () => {
    expect(service.get('libraryViewMode')).toBe(LIBRARY_VIEW_MODES.LIST);
    expect(service.libraryViewMode()).toBe(LIBRARY_VIEW_MODES.LIST);
    expect(service.get('sidebarCollapsed')).toBe(false);
    expect(service.sidebarCollapsed()).toBe(false);
  });

  it('should set and persist individual preference keys', () => {
    service.set('libraryViewMode', LIBRARY_VIEW_MODES.GRID);
    expect(service.get('libraryViewMode')).toBe(LIBRARY_VIEW_MODES.GRID);
    expect(service.libraryViewMode()).toBe(LIBRARY_VIEW_MODES.GRID);

    service.set('sidebarCollapsed', true);
    expect(service.get('sidebarCollapsed')).toBe(true);
    expect(service.sidebarCollapsed()).toBe(true);

    const raw = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
    expect(raw).toBeTruthy();
    const stored = JSON.parse(raw!);
    expect(stored.libraryViewMode).toBe(LIBRARY_VIEW_MODES.GRID);
    expect(stored.sidebarCollapsed).toBe(true);
  });

  it('should update multiple preferences via update()', () => {
    service.update({
      libraryViewMode: LIBRARY_VIEW_MODES.GRID,
      defaultSearchProximityThreshold: 0.4,
      sidebarCollapsed: true
    });

    expect(service.get('libraryViewMode')).toBe(LIBRARY_VIEW_MODES.GRID);
    expect(service.get('defaultSearchProximityThreshold')).toBe(0.4);
    expect(service.get('sidebarCollapsed')).toBe(true);
  });

  it('should gracefully handle corrupt localStorage data without crashing', () => {
    localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, '{invalid-json');
    const safeService = new UserPreferencesService();
    expect(safeService.get('libraryViewMode')).toBe(DEFAULT_USER_PREFERENCES.libraryViewMode);
    expect(safeService.get('sidebarCollapsed')).toBe(false);
  });
});
