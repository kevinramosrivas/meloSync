import { ComponentFixture, TestBed } from '@angular/core/testing';
import { provideRouter } from '@angular/router';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { signal } from '@angular/core';
import { of } from 'rxjs';
import { SidebarComponent } from './sidebar.component';
import { WebSocketService } from '../../../core/services/websocket.service';
import { SettingsApiService } from '../../../data/settings-api.service';
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
    latestProgress: ReturnType<typeof signal<null>>;
    isConnected: ReturnType<typeof signal<boolean>>;
  };

  beforeEach(async () => {
    mockPreferences = {
      sidebarCollapsed: signal(false),
      set: vi.fn()
    };

    mockWs = {
      latestProgress: signal(null),
      isConnected: signal(true)
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

  it('should remain clean and not show connection indicator when connected', () => {
    mockWs.isConnected.set(true);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).not.toContain('Servidor Conectado');
    expect(compiled.textContent).not.toContain('Conectando...');
  });

  it('should display a subtle connecting indicator when disconnected', () => {
    mockWs.isConnected.set(false);
    fixture.detectChanges();
    const compiled = fixture.nativeElement as HTMLElement;
    expect(compiled.textContent).toContain('Conectando...');
    expect(compiled.textContent).not.toContain('Servidor Conectado');
  });
});

