import { Component, computed, inject, signal } from '@angular/core';
import { Router, RouterOutlet, NavigationEnd } from '@angular/router';
import { filter } from 'rxjs';
import { TuiRoot } from '@taiga-ui/core';
import { SidebarComponent } from './shared/components/sidebar/sidebar.component';
import { BottomPlayerComponent } from './shared/components/bottom-player/bottom-player.component';
import { ToastContainerComponent } from './shared/components/toast-container/toast-container.component';
import { ConfirmDialogComponent } from './shared/components/confirm-dialog/confirm-dialog.component';
import { ContextMenuComponent } from './shared/components/context-menu/context-menu.component';
import { TaskbarControlsService } from './core/services/taskbar-controls.service';

@Component({
  selector: 'app-root',
  imports: [
    RouterOutlet,
    TuiRoot,
    SidebarComponent,
    BottomPlayerComponent,
    ToastContainerComponent,
    ConfirmDialogComponent,
    ContextMenuComponent,
  ],
  templateUrl: './app.html'
})
export class App {
  private readonly router = inject(Router);
  private readonly taskbarControls = inject(TaskbarControlsService);

  readonly currentUrl = signal<string>(
    typeof window !== 'undefined' ? (window.location.pathname + window.location.hash) : ''
  );

  readonly isMiniPlayer = computed(() => {
    const url = this.currentUrl();
    return url.includes('mini-player');
  });

  constructor() {
    this.router.events
      .pipe(filter(event => event instanceof NavigationEnd))
      .subscribe((event: NavigationEnd) => {
        this.currentUrl.set(event.urlAfterRedirects || event.url);
      });
  }
}
