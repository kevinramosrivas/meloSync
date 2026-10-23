import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { ToastService } from '../../../core/services/toast.service';
import { IconComponent, IconName } from '../icon/icon.component';

@Component({
  selector: 'app-toast-container',
  imports: [CommonModule, IconComponent],
  templateUrl: './toast-container.component.html'
})
export class ToastContainerComponent {
  readonly toastService = inject(ToastService);

  getIconName(type: string): IconName {
    switch (type) {
      case 'success': return 'check-circle';
      case 'error': return 'alert-circle';
      case 'warning': return 'alert-triangle';
      default: return 'info';
    }
  }
}
