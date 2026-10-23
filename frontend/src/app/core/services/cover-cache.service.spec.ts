import { describe, it, expect, beforeEach } from 'vitest';
import { CoverCacheService } from './cover-cache.service';
import { COVER_CACHE_CONFIG } from '../constants/preferences.constants';
import { Track } from '../../domain/models';

function createMockTrack(id: string, coverUrl?: string, hasCoverBytes = false, updatedAt?: string): Track {
  return {
    id,
    youtube_id: `yt-${id}`,
    url: 'https://youtube.com',
    original_title: `Song ${id}`,
    display_title: `Song ${id}`,
    display_artist: 'Artist',
    display_album: 'Album',
    duration_seconds: 180,
    duration_formatted: '3:00',
    channel_name: 'Channel',
    status: 'COMPLETADA',
    progress_percent: 100,
    file_exists: true,
    updated_at_iso: updatedAt,
    metadata: {
      title: `Song ${id}`,
      artist: 'Artist',
      album: 'Album',
      cover_url: coverUrl ?? null,
      has_cover_bytes: hasCoverBytes
    }
  };
}

describe('CoverCacheService', () => {
  let service: CoverCacheService;

  beforeEach(() => {
    service = new CoverCacheService();
  });

  it('should resolve and cache cover URLs', () => {
    const track = createMockTrack('1', 'https://example.com/cover.jpg');
    const url1 = service.getCoverUrl(track);
    expect(url1).toBe('https://example.com/cover.jpg');
    expect(service.entryCount).toBe(1);

    // Second call should be a cache hit
    const url2 = service.getCoverUrl(track);
    expect(url2).toBe('https://example.com/cover.jpg');
    expect(service.entryCount).toBe(1);
  });

  it('should auto-evict oldest entry when MAX_ENTRIES is exceeded (LRU behavior)', () => {
    // Fill to capacity
    for (let i = 0; i < COVER_CACHE_CONFIG.MAX_ENTRIES; i++) {
      service.getCoverUrl(createMockTrack(`track-${i}`, `https://example.com/${i}.jpg`));
    }
    expect(service.entryCount).toBe(COVER_CACHE_CONFIG.MAX_ENTRIES);

    // Adding one more should trigger auto-eviction and keep count capped at MAX_ENTRIES
    service.getCoverUrl(createMockTrack('track-overflow', 'https://example.com/overflow.jpg'));
    expect(service.entryCount).toBe(COVER_CACHE_CONFIG.MAX_ENTRIES);
  });

  it('should invalidate specific track entries when metadata or cover is updated', () => {
    const track = createMockTrack('1', 'https://example.com/old.jpg');
    service.getCoverUrl(track);
    expect(service.entryCount).toBe(1);

    service.invalidate('1');
    expect(service.entryCount).toBe(0);

    // Now resolving with new cover works cleanly
    const updatedTrack = createMockTrack('1', 'https://example.com/new.jpg', false, '2026-10-23T14:00:00Z');
    const newUrl = service.getCoverUrl(updatedTrack);
    expect(newUrl).toBe('https://example.com/new.jpg');
    expect(service.entryCount).toBe(1);
  });

  it('should completely purge cache when clear() is invoked from settings', () => {
    service.getCoverUrl(createMockTrack('1', 'https://example.com/1.jpg'));
    service.getCoverUrl(createMockTrack('2', 'https://example.com/2.jpg'));
    expect(service.entryCount).toBe(2);

    service.clear();
    expect(service.entryCount).toBe(0);
    expect(service.stats().estimatedMemoryDisplay).toBe('0 KB');
  });
});
