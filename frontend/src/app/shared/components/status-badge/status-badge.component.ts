import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TuiBadge } from '@taiga-ui/kit';
import { DownloadStatus } from '../../../domain/models';

@Component({
  selector: 'app-status-badge',
  standalone: true,
  imports: [CommonModule, TuiBadge],
  templateUrl: './status-badge.component.html',
  styleUrl: './status-badge.component.css'
})
export class StatusBadgeComponent {
  status = input.required<DownloadStatus>();

  getAppearance(): string {
    switch (this.status()) {
      case 'PENDIENTE': return 'warning';
      case 'DESCARGANDO': return 'accent';
      case 'PROCESANDO_AUDIO': return 'primary';
      case 'OBTENIENDO_METADATOS': return 'secondary';
      case 'COMPLETADA': return 'positive';
      case 'ERROR': return 'negative';
      case 'CANCELADA': return 'neutral';
      default: return 'neutral';
    }
  }

  getLabel(): string {
    switch (this.status()) {
      case 'PENDIENTE': return 'En cola';
      case 'DESCARGANDO': return 'Descargando';
      case 'PROCESANDO_AUDIO': return 'Normalizando';
      case 'OBTENIENDO_METADATOS': return 'Metadatos';
      case 'COMPLETADA': return 'Completada';
      case 'ERROR': return 'Error';
      case 'CANCELADA': return 'Cancelada';
      default: return this.status();
    }
  }
}
