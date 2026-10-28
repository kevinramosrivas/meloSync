import { describe, it, expect, beforeEach, vi, afterEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { provideHttpClient } from '@angular/common/http';
import { provideHttpClientTesting } from '@angular/common/http/testing';
import { AudioPlayerService } from './audio-player.service';
import { UserPreferencesService } from './user-preferences.service';
import { ToastService } from './toast.service';
import { Track } from '../../domain/models';
import { REPEAT_MODES } from '../constants/preferences.constants';

describe('AudioPlayerService', () => {
  let service: AudioPlayerService;
  let preferences: UserPreferencesService;

  const mockTrack1: Track = {
    id: 'track-1',
    youtube_id: 'yt-1',
    url: 'https://youtube.com/watch?v=1',
    original_title: 'Song One',
    display_title: 'Song One',
    display_artist: 'Artist One',
    display_album: 'Album One',
    duration_seconds: 180,
    duration_formatted: '3:00',
    channel_name: 'Channel One',
    status: 'COMPLETADA',
    progress_percent: 100,
    metadata: {
      title: 'Song One',
      artist: 'Artist One',
      album: 'Album One',
      has_cover_bytes: true
    }
  };

  const mockTrack2: Track = {
    id: 'track-2',
    youtube_id: 'yt-2',
    url: 'https://youtube.com/watch?v=2',
    original_title: 'Song Two',
    display_title: 'Song Two',
    display_artist: 'Artist Two',
    display_album: 'Album Two',
    duration_seconds: 240,
    duration_formatted: '4:00',
    channel_name: 'Channel Two',
    status: 'COMPLETADA',
    progress_percent: 100
  };

  const mockTrack3: Track = {
    id: 'track-3',
    youtube_id: 'yt-3',
    url: 'https://youtube.com/watch?v=3',
    original_title: 'Song Three',
    display_title: 'Song Three',
    display_artist: 'Artist Three',
    display_album: 'Album Three',
    duration_seconds: 200,
    duration_formatted: '3:20',
    channel_name: 'Channel Three',
    status: 'COMPLETADA',
    progress_percent: 100
  };

  // Setup MediaMetadata and mediaSession mock if not in browser
  if (typeof globalThis.MediaMetadata === 'undefined') {
    class MediaMetadataMock {
      title: string;
      artist: string;
      album: string;
      artwork: any[];
      constructor(init?: any) {
        this.title = init?.title || '';
        this.artist = init?.artist || '';
        this.album = init?.album || '';
        this.artwork = init?.artwork || [];
      }
    }
    Object.defineProperty(globalThis, 'MediaMetadata', {
      value: MediaMetadataMock,
      writable: true,
      configurable: true
    });
  }

  const mediaSessionMock = {
    metadata: null as any,
    playbackState: 'none',
    actionHandlers: new Map<string, Function>(),
    setActionHandler(action: string, handler: Function | null) {
      if (handler) {
        this.actionHandlers.set(action, handler);
      } else {
        this.actionHandlers.delete(action);
      }
    },
    setPositionState: vi.fn()
  };

  beforeEach(() => {
    // Mock HTMLAudioElement methods
    vi.spyOn(HTMLAudioElement.prototype, 'play').mockImplementation(() => Promise.resolve());
    vi.spyOn(HTMLAudioElement.prototype, 'pause').mockImplementation(() => {});
    vi.spyOn(HTMLAudioElement.prototype, 'load').mockImplementation(() => {});

    // Attach mock mediaSession to navigator
    if (typeof navigator !== 'undefined') {
      Object.defineProperty(navigator, 'mediaSession', {
        value: mediaSessionMock,
        writable: true,
        configurable: true
      });
    }

    TestBed.configureTestingModule({
      providers: [
        AudioPlayerService,
        UserPreferencesService,
        provideHttpClient(),
        provideHttpClientTesting(),
        {
          provide: ToastService,
          useValue: { error: vi.fn(), success: vi.fn(), info: vi.fn() }
        }
      ]
    });

    service = TestBed.inject(AudioPlayerService);
    preferences = TestBed.inject(UserPreferencesService);
  });

  afterEach(() => {
    vi.restoreAllMocks();
    mediaSessionMock.actionHandlers.clear();
    mediaSessionMock.metadata = null;
  });

  it('should initialize with default repeat mode ALL and shuffle disabled', () => {
    expect(service.repeatMode()).toBe(REPEAT_MODES.ALL);
    expect(service.isShuffle()).toBe(false);
    expect(service.playlist()).toEqual([]);
    expect(service.currentTrack()).toBeNull();
  });

  it('should play a track and configure the playlist queue', () => {
    service.playTrack(mockTrack1, [mockTrack1, mockTrack2, mockTrack3]);

    expect(service.currentTrack()).toEqual(mockTrack1);
    expect(service.playlist().length).toBe(3);
    expect(service.currentIndex()).toBe(0);
    expect(service.hasNext()).toBe(true);
    expect(service.hasPrevious()).toBe(true); // repeatMode is ALL
  });

  it('should update navigator.mediaSession metadata and handlers when track plays', () => {
    service.playTrack(mockTrack1, [mockTrack1, mockTrack2]);

    expect(mediaSessionMock.metadata).toBeTruthy();
    expect(mediaSessionMock.metadata.title).toBe('Song One');
    expect(mediaSessionMock.metadata.artist).toBe('Artist One');
    expect(mediaSessionMock.metadata.album).toBe('Album One');
    expect(mediaSessionMock.actionHandlers.has('nexttrack')).toBe(true);
    expect(mediaSessionMock.actionHandlers.has('previoustrack')).toBe(true);
    expect(mediaSessionMock.actionHandlers.has('play')).toBe(true);
    expect(mediaSessionMock.actionHandlers.has('pause')).toBe(true);
  });

  it('should advance to the next track on playNext()', () => {
    service.playTrack(mockTrack1, [mockTrack1, mockTrack2, mockTrack3]);
    expect(service.currentIndex()).toBe(0);

    service.playNext();
    expect(service.currentTrack()?.id).toBe('track-2');
    expect(service.currentIndex()).toBe(1);

    service.playNext();
    expect(service.currentTrack()?.id).toBe('track-3');
    expect(service.currentIndex()).toBe(2);
  });

  it('should loop to track 0 on playNext() from the end when repeatMode is ALL', () => {
    service.setRepeatMode(REPEAT_MODES.ALL);
    service.playTrack(mockTrack3, [mockTrack1, mockTrack2, mockTrack3]);
    expect(service.currentIndex()).toBe(2);

    service.playNext();
    expect(service.currentTrack()?.id).toBe('track-1');
    expect(service.currentIndex()).toBe(0);
  });

  it('should stop playback at the end when repeatMode is OFF', () => {
    service.setRepeatMode(REPEAT_MODES.OFF);
    service.playTrack(mockTrack3, [mockTrack1, mockTrack2, mockTrack3]);

    service.playNext();
    expect(service.isPlaying()).toBe(false);
  });

  it('should rewind to 0 on playPrevious() if currentTime > 3', () => {
    service.playTrack(mockTrack2, [mockTrack1, mockTrack2]);
    service.seek(15);
    expect(service.currentTime()).toBe(15);

    service.playPrevious();
    expect(service.currentTime()).toBe(0);
    expect(service.currentTrack()?.id).toBe('track-2'); // Stays on track 2
  });

  it('should go to previous track on playPrevious() if currentTime <= 3', () => {
    service.playTrack(mockTrack2, [mockTrack1, mockTrack2]);
    service.seek(1);

    service.playPrevious();
    expect(service.currentTrack()?.id).toBe('track-1');
  });

  it('should loop to last track on playPrevious() from track 0 when repeatMode is ALL', () => {
    service.setRepeatMode(REPEAT_MODES.ALL);
    service.playTrack(mockTrack1, [mockTrack1, mockTrack2, mockTrack3]);
    service.seek(0);

    service.playPrevious();
    expect(service.currentTrack()?.id).toBe('track-3');
  });

  it('should cycle repeat mode OFF -> ALL -> ONE -> OFF', () => {
    service.setRepeatMode(REPEAT_MODES.OFF);

    service.cycleRepeatMode();
    expect(service.repeatMode()).toBe(REPEAT_MODES.ALL);

    service.cycleRepeatMode();
    expect(service.repeatMode()).toBe(REPEAT_MODES.ONE);

    service.cycleRepeatMode();
    expect(service.repeatMode()).toBe(REPEAT_MODES.OFF);
  });

  it('should toggle shuffle and traverse the entire deck without repeating tracks', () => {
    service.playTrack(mockTrack1, [mockTrack1, mockTrack2, mockTrack3]);
    service.setRepeatMode(REPEAT_MODES.OFF);
    service.toggleShuffle();
    expect(service.isShuffle()).toBe(true);

    const visitedTracks: string[] = [service.currentTrack()!.id];

    // Next track 1
    service.playNext();
    visitedTracks.push(service.currentTrack()!.id);

    // Next track 2
    service.playNext();
    visitedTracks.push(service.currentTrack()!.id);

    // All 3 tracks must have been visited exactly once without duplicates
    expect(visitedTracks).toHaveLength(3);
    expect(new Set(visitedTracks).size).toBe(3);
    expect(visitedTracks).toContain('track-1');
    expect(visitedTracks).toContain('track-2');
    expect(visitedTracks).toContain('track-3');

    // Previous track should return to the 2nd visited track
    service.seek(1);
    service.playPrevious();
    expect(service.currentTrack()?.id).toBe(visitedTracks[1]);
  });
});
