import { describe, it, expect, beforeEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { MiniPlayerSyncService } from './mini-player-sync.service';
import { AudioPlayerService } from './audio-player.service';

describe('MiniPlayerSyncService', () => {
  let service: MiniPlayerSyncService;
  let mockAudioPlayer: {
    currentTrack: ReturnType<typeof vi.fn>;
    coverUrl: ReturnType<typeof vi.fn>;
    isPlaying: ReturnType<typeof vi.fn>;
    currentTime: ReturnType<typeof vi.fn>;
    duration: ReturnType<typeof vi.fn>;
    volume: ReturnType<typeof vi.fn>;
    isMuted: ReturnType<typeof vi.fn>;
    hasNext: ReturnType<typeof vi.fn>;
    hasPrevious: ReturnType<typeof vi.fn>;
    togglePlay: ReturnType<typeof vi.fn>;
    playNext: ReturnType<typeof vi.fn>;
    playPrevious: ReturnType<typeof vi.fn>;
    seek: ReturnType<typeof vi.fn>;
    setVolume: ReturnType<typeof vi.fn>;
  };

  beforeEach(() => {
    mockAudioPlayer = {
      currentTrack: vi.fn().mockReturnValue(null),
      coverUrl: vi.fn().mockReturnValue(null),
      isPlaying: vi.fn().mockReturnValue(false),
      currentTime: vi.fn().mockReturnValue(0),
      duration: vi.fn().mockReturnValue(0),
      volume: vi.fn().mockReturnValue(0.8),
      isMuted: vi.fn().mockReturnValue(false),
      hasNext: vi.fn().mockReturnValue(false),
      hasPrevious: vi.fn().mockReturnValue(false),
      togglePlay: vi.fn(),
      playNext: vi.fn(),
      playPrevious: vi.fn(),
      seek: vi.fn(),
      setVolume: vi.fn(),
    };

    TestBed.configureTestingModule({
      providers: [
        MiniPlayerSyncService,
        { provide: AudioPlayerService, useValue: mockAudioPlayer }
      ]
    });

    service = TestBed.inject(MiniPlayerSyncService);
  });

  it('should initialize with default states', () => {
    expect(service.track()).toBeNull();
    expect(service.isPlaying()).toBe(false);
    expect(service.currentTime()).toBe(0);
    expect(service.duration()).toBe(0);
    expect(service.progressPercent()).toBe(0);
  });

  it('should compute progressPercent accurately', () => {
    service.duration.set(200);
    service.currentTime.set(50);
    expect(service.progressPercent()).toBe(25);

    service.currentTime.set(200);
    expect(service.progressPercent()).toBe(100);

    service.duration.set(0);
    expect(service.progressPercent()).toBe(0);
  });

  it('should delegate actions to AudioPlayerService in main window mode', () => {
    service.isMiniWindow.set(false);

    service.togglePlay();
    expect(mockAudioPlayer.togglePlay).toHaveBeenCalled();

    service.playNext();
    expect(mockAudioPlayer.playNext).toHaveBeenCalled();

    service.playPrevious();
    expect(mockAudioPlayer.playPrevious).toHaveBeenCalled();

    service.seek(45);
    expect(mockAudioPlayer.seek).toHaveBeenCalledWith(45);

    service.setVolume(0.5);
    expect(mockAudioPlayer.setVolume).toHaveBeenCalledWith(0.5);
  });

  it('should calculate seekPercent and delegate correctly', () => {
    service.isMiniWindow.set(false);
    service.duration.set(200);

    service.seekPercent(50);
    expect(mockAudioPlayer.seek).toHaveBeenCalledWith(100);
  });
});

