import { Component, inject, OnInit, signal } from '@angular/core';
import { RouterModule } from '@angular/router';
import { WebSocketService } from '../../../core/services/websocket.service';
import { SettingsApiService } from '../../../data/settings-api.service';
import { ToastService } from '../../../core/services/toast.service';
import { UserPreferencesService } from '../../../core/services/user-preferences.service';
import { USER_PREFERENCE_KEYS } from '../../../core/constants/preferences.constants';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-sidebar',
  imports: [RouterModule, IconComponent],
  templateUrl: './sidebar.component.html',
  host: {
    'class': 'h-full shrink-0 border-r border-white/[0.08] bg-[#0c0c11]/95 backdrop-blur-2xl transition-[width] duration-200 ease-[cubic-bezier(0.32,0.72,0,1)] will-change-[width] overflow-hidden block select-none',
    '[class.w-[240px]]': '!isCollapsed()',
    '[class.w-[72px]]': 'isCollapsed()',
    '(window:resize)': 'onWindowResize()',
    '(window:keydown)': 'onKeyDown($event)'
  }
})
export class SidebarComponent implements OnInit {
  readonly ws = inject(WebSocketService);
  private readonly settingsApi = inject(SettingsApiService);
  private readonly toast = inject(ToastService);
  private readonly preferences = inject(UserPreferencesService);

  readonly activeProgress = this.ws.latestProgress;
  readonly isCollapsed = signal<boolean>(false);

  ngOnInit(): void {
    this.syncResponsiveState();
  }

  onWindowResize(): void {
    this.syncResponsiveState();
  }

  onKeyDown(event: KeyboardEvent): void {
    if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
      event.preventDefault();
      this.toggleCollapse();
    }
  }

  toggleCollapse(): void {
    const next = !this.isCollapsed();
    this.isCollapsed.set(next);
    if (typeof window !== 'undefined' && window.innerWidth >= 1024) {
      this.preferences.set(USER_PREFERENCE_KEYS.SIDEBAR_COLLAPSED, next);
    }
  }

  private syncResponsiveState(): void {
    if (typeof window === 'undefined') return;
    if (window.innerWidth < 1024) {
      this.isCollapsed.set(true);
    } else {
      this.isCollapsed.set(this.preferences.sidebarCollapsed());
    }
  }

  openMusicFolder(): void {
    this.settingsApi.openMusicFolder().subscribe({
      next: () => this.toast.info('Carpeta de música abierta'),
      error: (e) => this.toast.error('No se pudo abrir la carpeta', e.message)
    });
  }
}
