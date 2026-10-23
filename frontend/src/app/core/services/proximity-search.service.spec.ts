import { describe, it, expect, beforeEach } from 'vitest';
import { ProximitySearchService } from './proximity-search.service';
import { Track } from '../../domain/models';

function createMockTrack(overrides: Partial<Track>): Track {
  return {
    id: overrides.id || 'track-1',
    youtube_id: overrides.youtube_id || 'yt-1',
    url: overrides.url || 'https://youtube.com',
    original_title: overrides.original_title || 'Original Title',
    display_title: overrides.display_title || 'Default Title',
    display_artist: overrides.display_artist || 'Default Artist',
    display_album: overrides.display_album || 'Default Album',
    duration_seconds: overrides.duration_seconds || 180,
    duration_formatted: overrides.duration_formatted || '3:00',
    channel_name: overrides.channel_name || 'Default Channel',
    status: 'COMPLETADA',
    progress_percent: 100,
    metadata: overrides.metadata ?? null,
    file_exists: true,
    ...overrides
  };
}

describe('ProximitySearchService', () => {
  let service: ProximitySearchService;
  let sampleTracks: Track[];

  beforeEach(() => {
    service = new ProximitySearchService();
    sampleTracks = [
      createMockTrack({
        id: '1',
        display_title: 'Bohemian Rhapsody',
        display_artist: 'Queen',
        display_album: 'A Night at the Opera',
        metadata: {
          title: 'Bohemian Rhapsody',
          artist: 'Queen',
          album: 'A Night at the Opera',
          genre: 'Classic Rock',
          year: 1975
        }
      }),
      createMockTrack({
        id: '2',
        display_title: 'Yellow',
        display_artist: 'Coldplay',
        display_album: 'Parachutes',
        metadata: {
          title: 'Yellow',
          artist: 'Coldplay',
          album: 'Parachutes',
          genre: 'Alternative Rock',
          year: 2000
        }
      }),
      createMockTrack({
        id: '3',
        display_title: 'Luna de Octubre',
        display_artist: 'El Último Vecino',
        display_album: 'Voces en la Noche',
        metadata: {
          title: 'Luna de Octubre',
          artist: 'El Último Vecino',
          album: 'Voces en la Noche',
          genre: 'Indie Pop',
          year: 2023
        }
      }),
      createMockTrack({
        id: '4',
        display_title: 'Blinding Lights',
        display_artist: 'The Weeknd',
        display_album: 'After Hours',
        metadata: {
          title: 'Blinding Lights',
          artist: 'The Weeknd',
          album: 'After Hours',
          genre: 'Synthpop',
          year: 2020
        }
      })
    ];
  });

  it('should return all tracks if query is empty or whitespace', () => {
    expect(service.searchTracks(sampleTracks, '')).toHaveLength(4);
    expect(service.searchTracks(sampleTracks, '   ')).toHaveLength(4);
  });

  it('should find tracks by exact title match', () => {
    const results = service.searchTracks(sampleTracks, 'Bohemian Rhapsody');
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe('1');
  });

  it('should find tracks ignoring diacritics and accents', () => {
    const results = service.searchTracks(sampleTracks, 'ultimo vecino');
    expect(results.length).toBeGreaterThan(0);
    expect(results[0].id).toBe('3');
  });

  it('should find tracks by artist name', () => {
    const results = service.searchTracks(sampleTracks, 'coldplay');
    expect(results).toHaveLength(1);
    expect(results[0].display_artist).toBe('Coldplay');
  });

  it('should find tracks by album name', () => {
    const results = service.searchTracks(sampleTracks, 'Parachutes');
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe('2');
  });

  it('should find tracks by genre metadata', () => {
    const results = service.searchTracks(sampleTracks, 'Indie Pop');
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe('3');
  });

  it('should find tracks by year metadata', () => {
    const results = service.searchTracks(sampleTracks, '1975');
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe('1');
  });

  it('should tolerate typos in search terms (Levenshtein distance)', () => {
    // "bohemain" typo for "bohemian"
    const results1 = service.searchTracks(sampleTracks, 'bohemain');
    expect(results1.length).toBeGreaterThan(0);
    expect(results1[0].id).toBe('1');

    // "coldply" typo for "coldplay"
    const results2 = service.searchTracks(sampleTracks, 'coldply');
    expect(results2.length).toBeGreaterThan(0);
    expect(results2[0].id).toBe('2');
  });

  it('should handle multi-term queries across different metadata fields', () => {
    // "queen rhapsody" -> artist + title
    const results = service.searchTracks(sampleTracks, 'queen rhapsody');
    expect(results).toHaveLength(1);
    expect(results[0].id).toBe('1');
  });
});
