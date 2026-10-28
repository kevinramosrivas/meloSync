import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { TrackRowComponent } from './track-row.component';
import { AudioPlayerService } from '../../../core/services/audio-player.service';
import { Track } from '../../../domain/models';

describe('TrackRowComponent', () => {
  let component: TrackRowComponent;
  let fixture: ComponentFixture<TrackRowComponent>;
  let mockPlayer: any;

  const sampleTrack: Track = {
    id: 'track-1',
    youtube_id: 'yt-1',
    url: 'https://youtube.com/watch?v=1',
    original_title: 'Test Song',
    display_title: 'Test Song',
    display_artist: 'Test Artist',
    display_album: 'Test Album',
    duration_seconds: 180,
    duration_formatted: '3:00',
    channel_name: 'Test Channel',
    status: 'COMPLETADA',
    progress_percent: 100,
    file_exists: true,
    play_count: 5,
    created_at_iso: '2026-10-23T00:00:00Z',
    updated_at_iso: '2026-10-23T00:00:00Z',
  };

  beforeEach(async () => {
    mockPlayer = {
      currentTrack: signal<Track | null>(null),
      isPlaying: signal(false),
      togglePlay: vi.fn(),
      playTrack: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [TrackRowComponent],
      providers: [
        { provide: AudioPlayerService, useValue: mockPlayer }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(TrackRowComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('track', sampleTrack);
    fixture.componentRef.setInput('index', 0);
    fixture.detectChanges();
  });

  it('should create the component', () => {
    expect(component).toBeTruthy();
  });

  it('should display track title and artist', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Test Song');
    expect(el.textContent).toContain('Test Artist');
  });

  it('should show rank badge without emojis when showRankBadge is true', () => {
    fixture.componentRef.setInput('showRankBadge', true);
    fixture.detectChanges();
    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('#1');
    expect(el.textContent).not.toContain('🔥');
  });

  it('should emit play event when clicked and not current track', () => {
    const playSpy = vi.fn();
    component.play.subscribe(playSpy);

    component.onPlayAction();
    expect(playSpy).toHaveBeenCalledWith(sampleTrack);
  });

  it('should call togglePlay on player when current track is clicked', () => {
    mockPlayer.currentTrack.set(sampleTrack);
    fixture.detectChanges();

    component.onPlayAction();
    expect(mockPlayer.togglePlay).toHaveBeenCalled();
  });
});
