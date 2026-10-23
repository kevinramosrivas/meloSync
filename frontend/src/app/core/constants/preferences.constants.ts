export const LIBRARY_VIEW_MODES = {
  LIST: 'list',
  GRID: 'grid'
} as const;

export type LibraryViewMode = (typeof LIBRARY_VIEW_MODES)[keyof typeof LIBRARY_VIEW_MODES];

export const USER_PREFERENCE_KEYS = {
  LIBRARY_VIEW_MODE: 'libraryViewMode',
  DEFAULT_SEARCH_PROXIMITY_THRESHOLD: 'defaultSearchProximityThreshold',
  SIDEBAR_COLLAPSED: 'sidebarCollapsed'
} as const;

export type UserPreferenceKey = (typeof USER_PREFERENCE_KEYS)[keyof typeof USER_PREFERENCE_KEYS];

export const STORAGE_KEYS = {
  USER_PREFERENCES: 'melosync_user_preferences'
} as const;

export const COVER_CACHE_CONFIG = {
  MAX_ENTRIES: 150, // Prevents gigabyte memory bloat (auto-eviction threshold)
  ESTIMATED_BYTES_PER_COVER: 75_000 // Average estimated thumbnail footprint (~75KB)
} as const;
