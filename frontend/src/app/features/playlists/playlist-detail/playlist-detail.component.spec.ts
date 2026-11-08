import { ComponentFixture, TestBed } from '@angular/core/testing';
import { PlaylistDetailComponent } from './playlist-detail.component';
import { PlaylistsApiService } from '../../../data/playlists-api.service';
import { PlaylistsStore } from '../../../core/stores/playlists.store';
import { LibraryApiService } from '../../../data/library-api.service';
import { AudioPlayerService } from '../../../core/services/audio-player.service';
import { ToastService } from '../../../core/services/toast.service';
import { ConfirmDialogService } from '../../../core/services/confirm-dialog.service';
import { ContextMenuService } from '../../../core/services/context-menu.service';
import { Router } from '@angular/router';
import { Playlist } from '../../../domain/models';
import { of } from 'rxjs';
import { signal } from '@angular/core';
import { describe, it, expect, beforeEach, vi } from 'vitest';

describe('PlaylistDetailComponent', () => {
  let component: PlaylistDetailComponent;
  let fixture: ComponentFixture<PlaylistDetailComponent>;

  const mockShortBio =
    'Kim Hyung-seo, más conocida como Bibi, es una cantautora surcoreana. En 2017, firmó un contrato con la discográfica Feel Ghood Music. En 2018 participó en The Fan.';

  const mockLongBio =
    'Kim Hyung-seo, más conocida como Bibi, es una cantautora surcoreana. En 2017, firmó un contrato con la discográfica Feel Ghood Music después de que la rapera Yoon Mi-rae encontró algunas de sus canciones en Soundcloud.\n\nEn 2018, participó como concursante en el programa The Fan de SBS, donde finalmente alcanzó el segundo lugar. Debutó oficialmente con el sencillo «Binu», lanzado el 15 de mayo de 2019. Su música abarca R&B, hip-hop y pop contemporáneo con letras introspectivas y conceptos visuales audaces.';

  const mockPlaylist: Playlist = {
    id: 'artist-bibi',
    name: 'Mix de BIBI',
    description: mockShortBio,
    playlist_type: 'artist',
    is_smart: true,
    filter_query: 'BIBI',
    cover_url: 'http://127.0.0.1:8000/api/v1/library/cover/1',
    created_at_iso: '2026-10-01T00:00:00Z',
    updated_at_iso: '2026-10-01T00:00:00Z',
    track_count: 3,
    duration_seconds: 610,
    tracks: [],
  };

  let playlistsApiMock: {
    getPlaylist: ReturnType<typeof vi.fn>;
    deletePlaylist: ReturnType<typeof vi.fn>;
  };

  let audioPlayerMock: {
    activePlaylistId: ReturnType<typeof signal>;
    isPlaying: ReturnType<typeof signal>;
    playPlaylist: ReturnType<typeof vi.fn>;
    togglePlay: ReturnType<typeof vi.fn>;
    isShuffle: ReturnType<typeof vi.fn>;
    toggleShuffle: ReturnType<typeof vi.fn>;
  };

  let routerMock: {
    navigate: ReturnType<typeof vi.fn>;
  };

  let toastMock: {
    success: ReturnType<typeof vi.fn>;
    error: ReturnType<typeof vi.fn>;
    info: ReturnType<typeof vi.fn>;
  };

  let confirmDialogMock: {
    confirm: ReturnType<typeof vi.fn>;
  };

  let contextMenuMock: {
    open: ReturnType<typeof vi.fn>;
    close: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    playlistsApiMock = {
      getPlaylist: vi.fn().mockReturnValue(of(mockPlaylist)),
      deletePlaylist: vi.fn().mockReturnValue(of(undefined)),
    };

    audioPlayerMock = {
      activePlaylistId: signal<string | null>(null),
      isPlaying: signal<boolean>(false),
      playPlaylist: vi.fn(),
      togglePlay: vi.fn(),
      isShuffle: vi.fn().mockReturnValue(false),
      toggleShuffle: vi.fn(),
    };

    routerMock = {
      navigate: vi.fn(),
    };

    toastMock = {
      success: vi.fn(),
      error: vi.fn(),
      info: vi.fn(),
    };

    confirmDialogMock = {
      confirm: vi.fn().mockResolvedValue(true),
    };

    contextMenuMock = {
      open: vi.fn(),
      close: vi.fn(),
    };

    await TestBed.configureTestingModule({
      imports: [PlaylistDetailComponent],
      providers: [
        { provide: PlaylistsApiService, useValue: playlistsApiMock },
        { provide: PlaylistsStore, useValue: { load: vi.fn() } },
        { provide: LibraryApiService, useValue: { addToPlaylist: vi.fn() } },
        { provide: AudioPlayerService, useValue: audioPlayerMock },
        { provide: Router, useValue: routerMock },
        { provide: ToastService, useValue: toastMock },
        { provide: ConfirmDialogService, useValue: confirmDialogMock },
        { provide: ContextMenuService, useValue: contextMenuMock },
      ],
    }).compileComponents();

    fixture = TestBed.createComponent(PlaylistDetailComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('id', 'artist-bibi');
    fixture.detectChanges();
  });

  it('should create the playlist detail component', () => {
    expect(component).toBeTruthy();
    expect(component.artistName()).toBe('BIBI');
    expect(component.artistBio()).toBe(mockShortBio);
  });

  it('should calculate isBioLong as false for short biography and not render expand button', () => {
    expect(component.isBioLong()).toBe(false);

    const compiled = fixture.nativeElement as HTMLElement;
    const button = compiled.querySelector('button[aria-expanded]');
    expect(button).toBeNull();
  });

  it('should calculate isBioLong as true for long biography and toggle expansion', () => {
    component.playlist.set({
      ...mockPlaylist,
      description: mockLongBio,
    });
    fixture.detectChanges();

    expect(component.isBioLong()).toBe(true);
    expect(component.isBioExpanded()).toBe(false);

    const compiled = fixture.nativeElement as HTMLElement;
    const button = compiled.querySelector('button[aria-expanded]') as HTMLButtonElement;
    expect(button).not.toBeNull();
    expect(button.textContent).toContain('Leer biografía completa');

    component.toggleBio();
    fixture.detectChanges();

    expect(component.isBioExpanded()).toBe(true);
    expect(button.textContent).toContain('Leer menos');
  });

  it('should not contain duplicate photo in the biography section', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    // In the entire biography card, there should be no <img> tag (only in hero artwork)
    const bioCard = compiled.querySelector('.bg-white\\/\\[0\\.02\\]');
    expect(bioCard).not.toBeNull();
    const bioImages = bioCard?.querySelectorAll('img') || [];
    expect(bioImages.length).toBe(0);
  });

  it('should confirm and delete playlist when deletePlaylist is called for custom playlist', async () => {
    component.playlist.set({ ...mockPlaylist, is_smart: false });
    await component.deletePlaylist();

    expect(confirmDialogMock.confirm).toHaveBeenCalledWith(
      expect.objectContaining({
        title: 'Eliminar lista de reproducción',
        danger: true,
      })
    );
    expect(playlistsApiMock.deletePlaylist).toHaveBeenCalledWith('artist-bibi');
    expect(routerMock.navigate).toHaveBeenCalledWith(['/playlists']);
  });

  it('should not delete playlist when confirm dialog is cancelled', async () => {
    component.playlist.set({ ...mockPlaylist, is_smart: false });
    confirmDialogMock.confirm.mockResolvedValueOnce(false);
    await component.deletePlaylist();

    expect(confirmDialogMock.confirm).toHaveBeenCalled();
    expect(playlistsApiMock.deletePlaylist).not.toHaveBeenCalled();
    expect(routerMock.navigate).not.toHaveBeenCalled();
  });

  it('should open context menu for track with right-click or options event', () => {
    const dummyTrack = {
      id: 'track-bibi',
      youtube_id: 'yt-bibi',
      url: 'https://youtube.com/watch?v=yt-bibi',
      original_title: 'BIBI - The Weekend',
      display_title: 'The Weekend',
      display_artist: 'BIBI',
      display_album: 'Lowlife Princess',
      duration_seconds: 180,
      duration_formatted: '3:00',
      channel_name: 'BIBI',
      status: 'COMPLETADA' as const,
      progress_percent: 100,
      file_exists: true,
    };
    const mouseEvent = new MouseEvent('contextmenu', { clientX: 200, clientY: 300 });
    component.openTrackContextMenu(dummyTrack, mouseEvent);

    expect(contextMenuMock.open).toHaveBeenCalledWith(
      expect.objectContaining({
        x: 200,
        y: 300,
        items: expect.any(Array),
      })
    );
  });
});
