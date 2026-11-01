import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MiniPlayerComponent } from './mini-player.component';
import { MiniPlayerSyncService } from '../../core/services/mini-player-sync.service';
import { signal } from '@angular/core';

describe('MiniPlayerComponent', () => {
  let component: MiniPlayerComponent;
  let fixture: ComponentFixture<MiniPlayerComponent>;
  let mockSyncService: {
    track: ReturnType<typeof signal>;
    coverUrl: ReturnType<typeof signal>;
    isPlaying: ReturnType<typeof signal>;
    currentTime: ReturnType<typeof signal>;
    duration: ReturnType<typeof signal>;
    progressPercent: ReturnType<typeof signal>;
    hasNext: ReturnType<typeof signal>;
    hasPrevious: ReturnType<typeof signal>;
    togglePlay: ReturnType<typeof vi.fn>;
    playNext: ReturnType<typeof vi.fn>;
    playPrevious: ReturnType<typeof vi.fn>;
    seek: ReturnType<typeof vi.fn>;
    closeMiniPlayer: ReturnType<typeof vi.fn>;
    focusMainWindow: ReturnType<typeof vi.fn>;
    startDragging: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    mockSyncService = {
      track: signal(null),
      coverUrl: signal(null),
      isPlaying: signal(false),
      currentTime: signal(0),
      duration: signal(180),
      progressPercent: signal(10),
      hasNext: signal(true),
      hasPrevious: signal(true),
      togglePlay: vi.fn(),
      playNext: vi.fn(),
      playPrevious: vi.fn(),
      seek: vi.fn(),
      closeMiniPlayer: vi.fn(),
      focusMainWindow: vi.fn(),
      startDragging: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [MiniPlayerComponent],
      providers: [
        { provide: MiniPlayerSyncService, useValue: mockSyncService }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(MiniPlayerComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create mini player component', () => {
    expect(component).toBeTruthy();
  });

  it('should detect pill mode when window height is less than 140px', () => {
    component.windowHeight.set(100);
    expect(component.isPillMode()).toBe(true);

    component.windowHeight.set(300);
    expect(component.isPillMode()).toBe(false);
  });

  it('should call closeMiniPlayer on close action', () => {
    component.closeMiniPlayer();
    expect(mockSyncService.closeMiniPlayer).toHaveBeenCalled();
  });

  it('should call focusMainWindow on restore action', () => {
    component.restoreMainWindow();
    expect(mockSyncService.focusMainWindow).toHaveBeenCalled();
  });

  it('should call startDragging on valid left click drag', () => {
    const event = {
      button: 0,
      target: document.createElement('div')
    } as unknown as MouseEvent;
    component.onStartDrag(event);
    expect(mockSyncService.startDragging).toHaveBeenCalled();
  });

  it('should enable previous button in pill mode when width >= 290px', () => {
    component.windowWidth.set(290);
    expect(component.canShowPreviousInPill()).toBe(true);

    component.windowWidth.set(280);
    expect(component.canShowPreviousInPill()).toBe(false);
  });
});

