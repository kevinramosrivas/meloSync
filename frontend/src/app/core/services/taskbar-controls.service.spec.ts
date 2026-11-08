import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { signal } from '@angular/core';
import { TaskbarControlsService } from './taskbar-controls.service';
import { AudioPlayerService } from './audio-player.service';
import { UserPreferencesService } from './user-preferences.service';

describe('TaskbarControlsService', () => {
  let service: TaskbarControlsService;
  let mockAudioPlayer: {
    currentTrack: ReturnType<typeof signal>;
    isPlaying: ReturnType<typeof signal>;
    currentTime: ReturnType<typeof signal>;
    duration: ReturnType<typeof signal>;
    playlist: ReturnType<typeof signal>;
    togglePlay: ReturnType<typeof vi.fn>;
    playNext: ReturnType<typeof vi.fn>;
    playPrevious: ReturnType<typeof vi.fn>;
  };
  let mockUserPreferences: {
    taskbarControlsEnabled: ReturnType<typeof signal>;
  };

  beforeEach(() => {
    mockAudioPlayer = {
      currentTrack: signal(null),
      isPlaying: signal(false),
      currentTime: signal(0),
      duration: signal(0),
      playlist: signal([]),
      togglePlay: vi.fn(),
      playNext: vi.fn(),
      playPrevious: vi.fn(),
    };

    mockUserPreferences = {
      taskbarControlsEnabled: signal(true),
    };

    TestBed.configureTestingModule({
      providers: [
        TaskbarControlsService,
        { provide: AudioPlayerService, useValue: mockAudioPlayer },
        { provide: UserPreferencesService, useValue: mockUserPreferences },
      ],
    });

    service = TestBed.inject(TaskbarControlsService);
  });

  afterEach(() => {
    service.destroy();
    delete (window as unknown as { __TAURI__?: unknown }).__TAURI__;
  });

  it('should be created and default to not supported in non-Tauri environment', () => {
    expect(service).toBeTruthy();
    expect(service.isTauri()).toBe(false);
    expect(service.isPlatformSupported()).toBe(false);
  });

  it('should detect Tauri correctly when window.__TAURI__ is defined', () => {
    (window as unknown as { __TAURI__?: unknown }).__TAURI__ = {
      core: {
        invoke: vi.fn().mockResolvedValue('windows'),
      },
      event: {
        listen: vi.fn().mockResolvedValue(() => {}),
      },
    };

    expect(service.isTauri()).toBe(true);
  });

  it('should listen to taskbar events and dispatch audio player methods when initialized', async () => {
    const listeners: Record<string, () => void> = {};
    const mockListen = vi.fn().mockImplementation((event: string, handler: () => void) => {
      listeners[event] = handler;
      return Promise.resolve(() => {});
    });
    const mockInvoke = vi.fn().mockResolvedValue(undefined);

    (window as unknown as { __TAURI__?: unknown }).__TAURI__ = {
      core: {
        invoke: mockInvoke,
      },
      event: {
        listen: mockListen,
      },
    };

    await service.initListeners();

    expect(mockListen).toHaveBeenCalledWith('taskbar-toggle-play', expect.any(Function));
    expect(mockListen).toHaveBeenCalledWith('taskbar-previous', expect.any(Function));
    expect(mockListen).toHaveBeenCalledWith('taskbar-next', expect.any(Function));
    expect(mockInvoke).toHaveBeenCalledWith('init_taskbar_controls');

    // Trigger events
    listeners['taskbar-toggle-play']?.();
    expect(mockAudioPlayer.togglePlay).toHaveBeenCalled();

    listeners['taskbar-previous']?.();
    expect(mockAudioPlayer.playPrevious).toHaveBeenCalled();

    listeners['taskbar-next']?.();
    expect(mockAudioPlayer.playNext).toHaveBeenCalled();
  });

  it('should cleanly unlisten and destroy without throwing', () => {
    expect(() => service.destroy()).not.toThrow();
  });

  it('should synchronize track title to document.title and invoke update_taskbar_track', async () => {
    const mockInvoke = vi.fn().mockResolvedValue(undefined);
    (window as unknown as { __TAURI__?: unknown }).__TAURI__ = {
      core: {
        invoke: mockInvoke,
      },
      event: {
        listen: vi.fn().mockResolvedValue(() => {}),
      },
    };

    // Force platform supported
    (service as unknown as { _isPlatformSupported: { set: (val: boolean) => void } })._isPlatformSupported.set(true);

    mockAudioPlayer.currentTrack.set({
      id: 'track-123',
      display_title: 'No Te Vas',
      display_artist: 'Nacho',
      display_album: 'No Te Vas - Single',
    } as any);

    TestBed.flushEffects();

    expect(document.title).toBe('No Te Vas • Nacho');
    expect(mockInvoke).toHaveBeenCalledWith('update_taskbar_track', {
      title: 'No Te Vas',
      artist: 'Nacho',
    });

    // Clear track
    mockAudioPlayer.currentTrack.set(null);
    TestBed.flushEffects();

    expect(document.title).toBe('meloSync');
    expect(mockInvoke).toHaveBeenCalledWith('update_taskbar_track', {
      title: null,
      artist: null,
    });
  });
});

