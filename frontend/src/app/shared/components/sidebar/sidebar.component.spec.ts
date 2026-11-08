import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { SidebarComponent } from './sidebar.component';
import { WebSocketService } from '../../../core/services/websocket.service';
import { SettingsApiService } from '../../../data/settings-api.service';
import { DownloadsApiService } from '../../../data/downloads-api.service';
import { ToastService } from '../../../core/services/toast.service';
import { UserPreferencesService } from '../../../core/services/user-preferences.service';
import { USER_PREFERENCE_KEYS } from '../../../core/constants/preferences.constants';

describe('SidebarComponent', () => {
  let component: SidebarComponent;
  let fixture: ComponentFixture<SidebarComponent>;
  let mockPreferences: {
    sidebarCollapsed: ReturnType<typeof signal<boolean>>;
    set: ReturnType<typeof vi.fn>;
  };
  let mockWs: {
    latestProgress: ReturnType<typeof signal<any>>;
    isConnected: ReturnType<typeof signal<boolean>>;
    hasActiveDownloads: ReturnType<typeof signal<boolean>>;
    activeDownloadsCount: ReturnType<typeof signal<number>>;
    syncActiveDownloads: ReturnType<typeof vi.fn>;
  };
  let mockDownloadsApi: {
    getActiveDownloads: ReturnType<typeof vi.fn>;
  };

  beforeEach(async () => {
    mockPreferences = {
      sidebarCollapsed: signal(false),
      set: vi.fn()
    };

    mockWs = {
      latestProgress: signal(null),
      isConnected: signal(true),
      hasActiveDownloads: signal(false),
      activeDownloadsCount: signal(0),
      syncActiveDownloads: vi.fn(),
    };

    mockDownloadsApi = {
      getActiveDownloads: vi.fn().mockReturnValue(of([])),
    };

    const mockSettingsApi = {
      openMusicFolder: vi.fn().mockReturnValue(of({ success: true }))
    };

    const mockToast = {
      info: vi.fn(),
      error: vi.fn()
    };

    await TestBed.configureTestingModule({
      imports: [SidebarComponent],
      providers: [
        provideRouter([]),
        { provide: WebSocketService, useValue: mockWs },
        { provide: SettingsApiService, useValue: mockSettingsApi },
        { provide: DownloadsApiService, useValue: mockDownloadsApi },
        { provide: ToastService, useValue: mockToast },
        { provide: UserPreferencesService, useValue: mockPreferences }
      ]
    }).compileComponents();

    fixture = TestBed.createComponent(SidebarComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create the sidebar component', () => {
    expect(component).toBeTruthy();
  });

  it('should display the official logo image', () => {
    const compiled = fixture.nativeElement as HTMLElement;
    const logoImg = compiled.querySelector('img[src="/logo.svg"]') as HTMLImageElement;
    expect(logoImg).toBeTruthy();
    expect(logoImg.getAttribute('alt')).toBe('meloSync');
  });

  it('should toggle collapse state and update preferences on wide screens', () => {
    // Mock wide window width
    vi.stubGlobal('innerWidth', 1280);

    expect(component.isCollapsed()).toBe(false);
    component.toggleCollapse();
    expect(component.isCollapsed()).toBe(true);
    expect(mockPreferences.set).toHaveBeenCalledWith(USER_PREFERENCE_KEYS.SIDEBAR_COLLAPSED, true);

    component.toggleCollapse();
    expect(component.isCollapsed()).toBe(false);
    expect(mockPreferences.set).toHaveBeenCalledWith(USER_PREFERENCE_KEYS.SIDEBAR_COLLAPSED, false);

    vi.unstubAllGlobals();
  });

  it('should automatically collapse when window width is less than 1024px', () => {
    vi.stubGlobal('innerWidth', 900);
    component.onWindowResize();
    expect(component.isCollapsed()).toBe(true);

    vi.unstubAllGlobals();
  });

  it('should remain clean and not show technical connection indicators', () => {
    mockWs.isConnected.set(true);
    fixture.detectChanges();
    let compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).not.toContain('Servidor Conectado');
    expect(compiled.textContent).not.toContain('Conectando');

    mockWs.isConnected.set(false);
    fixture.detectChanges();
    compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).not.toContain('Servidor Conectado');
    expect(compiled.textContent).not.toContain('Conectando');
  });

  it('should not display download dot or count badge when no active downloads exist', () => {
    mockWs.hasActiveDownloads.set(false);
    mockWs.activeDownloadsCount.set(0);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const downloadLink = compiled.querySelector('a[title="Descargas"]');
    expect(downloadLink).toBeTruthy();

    const dot = downloadLink?.querySelector('.bg-white.rounded-full');
    expect(dot).toBeNull();
  });

  it('should display active download count when expanded and dot indicator when collapsed', () => {
    // 1. Expanded with 2 active downloads
    component.isCollapsed.set(false);
    mockWs.hasActiveDownloads.set(true);
    mockWs.activeDownloadsCount.set(2);
    fixture.detectChanges();

    const compiled = fixture.nativeElement as HTMLElement;
    const downloadLink = compiled.querySelector('a[title="Descargas"]');
    expect(downloadLink).toBeTruthy();

    // Badge showing '2'
    const badge = downloadLink?.querySelector('span.rounded-full.bg-white.text-zinc-950');
    expect(badge).toBeTruthy();
    expect(badge?.textContent?.trim()).toBe('2');

    // 2. Collapsed
    component.isCollapsed.set(true);
    fixture.detectChanges();

    const dot = downloadLink?.querySelector('span.absolute.top-2.right-2');
    expect(dot).toBeTruthy();
  });

  it('should immediately hide badge and dot once download completes', () => {
    // Active download running
    mockWs.hasActiveDownloads.set(true);
    mockWs.activeDownloadsCount.set(1);
    fixture.detectChanges();

    let compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('a[title="Descargas"] .bg-white.rounded-full')).toBeTruthy();

    // Download finishes (COMPLETADA)
    mockWs.hasActiveDownloads.set(false);
    mockWs.activeDownloadsCount.set(0);
    fixture.detectChanges();

    compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.querySelector('a[title="Descargas"] .bg-white.rounded-full')).toBeNull();
  });
});

