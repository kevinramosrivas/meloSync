import { Service, signal, computed } from '@angular/core';
import { Track } from '../../domain/models';
import { API_CONFIG } from '../config/api.config';
import { COVER_CACHE_CONFIG } from '../constants/preferences.constants';

export interface CoverCacheStats {
  entryCount: number;
  maxEntries: number;
  estimatedMemoryDisplay: string;
}

@Service()
export class CoverCacheService {
  // LRU map preserving insertion/access order
  private readonly cache = new Map<string, string | null>();
  private readonly _version = signal<number>(0);

  /**
   * Reactive stats for settings dashboard.
   * Tracks manual purges and invalidations.
   */
  readonly stats = computed<CoverCacheStats>(() => {
    this._version();
    const count = this.cache.size;
    const bytes = count * COVER_CACHE_CONFIG.ESTIMATED_BYTES_PER_COVER;
    const mb = (bytes / (1024 * 1024)).toFixed(1);
    return {
      entryCount: count,
      maxEntries: COVER_CACHE_CONFIG.MAX_ENTRIES,
      estimatedMemoryDisplay: count === 0 ? '0 KB' : `${mb} MB`
    };
  });

  get entryCount(): number {
    return this.cache.size;
  }

  /**
   * Resolves and caches the cover URL for a track using LRU eviction.
   * Pure Map manipulation - does NOT write to signals during template render.
   */
  getCoverUrl(track: Track): string | null {
    const cacheKey = this.generateKey(track);

    if (this.cache.has(cacheKey)) {
      const cachedUrl = this.cache.get(cacheKey)!;
      // Refresh LRU order by re-inserting
      this.cache.delete(cacheKey);
      this.cache.set(cacheKey, cachedUrl);
      return cachedUrl;
    }

    const resolvedUrl = this.computeUrl(track);

    // Auto-eviction if max capacity reached
    if (this.cache.size >= COVER_CACHE_CONFIG.MAX_ENTRIES) {
      const oldestKey = this.cache.keys().next().value;
      if (oldestKey) {
        this.cache.delete(oldestKey);
      }
    }

    this.cache.set(cacheKey, resolvedUrl);
    return resolvedUrl;
  }

  /**
   * Invalidates any cached cover art for a specific track.
   * Called immediately when metadata or cover bytes are updated.
   */
  invalidate(trackId: string): void {
    let purged = false;
    for (const key of Array.from(this.cache.keys())) {
      if (key.startsWith(`${trackId}:`)) {
        this.cache.delete(key);
        purged = true;
      }
    }
    if (purged) {
      this._version.update((v) => v + 1);
    }
  }

  /**
   * Completely purges the cover art cache on demand from settings.
   */
  clear(): void {
    this.cache.clear();
    this._version.update((v) => v + 1);
  }

  private generateKey(track: Track): string {
    return `${track.id}:${track.updated_at_iso || 'initial'}:${track.metadata?.cover_url || ''}`;
  }

  private computeUrl(track: Track): string | null {
    if (track.metadata?.has_cover_bytes) {
      return `${API_CONFIG.baseUrl}${API_CONFIG.endpoints.cover(track.id)}?t=${track.updated_at_iso || ''}`;
    }
    if (track.metadata?.cover_url) {
      return track.metadata.cover_url;
    }
    return null;
  }
}
