import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { TuiButton } from '@taiga-ui/core';
import { TuiBadge } from '@taiga-ui/kit';
import { WebSocketService } from '../../../core/services/websocket.service';
import { SettingsApiService } from '../../../data/settings-api.service';
import { ToastService } from '../../../core/services/toast.service';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterModule, TuiButton, TuiBadge, IconComponent],
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css'
})
export class SidebarComponent {
  readonly ws = inject(WebSocketService);
  private settingsApi = inject(SettingsApiService);
  private toast = inject(ToastService);

  readonly activeProgress = this.ws.latestProgress;

  openMusicFolder(): void {
    this.settingsApi.openMusicFolder().subscribe({
      next: () => this.toast.info('Carpeta de música abierta'),
      error: (e) => this.toast.error('No se pudo abrir la carpeta', e.message)
    });
  }
}
