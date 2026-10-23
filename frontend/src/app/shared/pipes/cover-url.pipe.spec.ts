import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { CoverUrlPipe } from './cover-url.pipe';
import { CoverCacheService } from '../../core/services/cover-cache.service';
import { Track } from '../../domain/models';

function createMockTrack(id: string, coverUrl?: string): Track {
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
    metadata: {
      title: `Song ${id}`,
      artist: 'Artist',
      album: 'Album',
      cover_url: coverUrl ?? null
    }
  };
}

describe('CoverUrlPipe', () => {
  let pipe: CoverUrlPipe;
  let coverCache: CoverCacheService;

  beforeEach(() => {
    TestBed.configureTestingModule({
      providers: [CoverUrlPipe, CoverCacheService]
    });
    pipe = TestBed.inject(CoverUrlPipe);
    coverCache = TestBed.inject(CoverCacheService);
  });

  it('should return null when track is null or undefined', () => {
    expect(pipe.transform(null)).toBeNull();
    expect(pipe.transform(undefined)).toBeNull();
  });

  it('should resolve cover URL through CoverCacheService', () => {
    const track = createMockTrack('1', 'https://example.com/cover.jpg');
    const result = pipe.transform(track);
    expect(result).toBe('https://example.com/cover.jpg');
    expect(coverCache.entryCount).toBe(1);
  });
});
