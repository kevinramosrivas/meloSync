import { Service, signal, computed } from '@angular/core';
import {
  LIBRARY_VIEW_MODES,
  LibraryViewMode,
  REPEAT_MODES,
  RepeatMode,
  STORAGE_KEYS,
  UserPreferenceKey
} from '../constants/preferences.constants';

export interface UserPreferences {
  libraryViewMode: LibraryViewMode;
  defaultSearchProximityThreshold: number;
  sidebarCollapsed: boolean;
  repeatMode: RepeatMode;
  shuffleEnabled: boolean;
}

export const DEFAULT_USER_PREFERENCES: UserPreferences = {
  libraryViewMode: LIBRARY_VIEW_MODES.LIST,
  defaultSearchProximityThreshold: 0.3,
  sidebarCollapsed: false,
  repeatMode: REPEAT_MODES.ALL,
  shuffleEnabled: false
};

@Service()
export class UserPreferencesService {
  private readonly _preferences = signal<UserPreferences>(this.loadPreferences());

  readonly preferences = this._preferences.asReadonly();
  readonly libraryViewMode = computed(() => this._preferences().libraryViewMode);
  readonly sidebarCollapsed = computed(() => this._preferences().sidebarCollapsed);
  readonly repeatMode = computed(() => this._preferences().repeatMode);
  readonly shuffleEnabled = computed(() => this._preferences().shuffleEnabled);

  constructor() {
    if (typeof window !== 'undefined') {
      window.addEventListener('storage', (event: StorageEvent) => {
        if (event.key === STORAGE_KEYS.USER_PREFERENCES && event.newValue) {
          try {
            const parsed = JSON.parse(event.newValue) as Partial<UserPreferences>;
            this._preferences.set({ ...DEFAULT_USER_PREFERENCES, ...parsed });
          } catch {
            // Ignore parse errors from concurrent storage events
          }
        }
      });
    }
  }

  get<K extends keyof UserPreferences>(key: K): UserPreferences[K] {
    return this._preferences()[key];
  }

  set<K extends keyof UserPreferences>(key: K, value: UserPreferences[K]): void {
    this._preferences.update((current) => {
      const updated = { ...current, [key]: value };
      this.persist(updated);
      return updated;
    });
  }

  update(partial: Partial<UserPreferences>): void {
    this._preferences.update((current) => {
      const updated = { ...current, ...partial };
      this.persist(updated);
      return updated;
    });
  }

  private loadPreferences(): UserPreferences {
    if (typeof localStorage === 'undefined') {
      return { ...DEFAULT_USER_PREFERENCES };
    }
    try {
      const raw = localStorage.getItem(STORAGE_KEYS.USER_PREFERENCES);
      if (!raw) return { ...DEFAULT_USER_PREFERENCES };
      const parsed = JSON.parse(raw) as Partial<UserPreferences>;
      return { ...DEFAULT_USER_PREFERENCES, ...parsed };
    } catch {
      return { ...DEFAULT_USER_PREFERENCES };
    }
  }

  private persist(prefs: UserPreferences): void {
    if (typeof localStorage === 'undefined') return;
    try {
      localStorage.setItem(STORAGE_KEYS.USER_PREFERENCES, JSON.stringify(prefs));
    } catch (err) {
      console.warn('No se pudo guardar preferencias en localStorage:', err);
    }
  }
}
