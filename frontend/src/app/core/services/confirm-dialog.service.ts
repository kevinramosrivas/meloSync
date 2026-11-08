import { Injectable, signal } from '@angular/core';
import { IconName } from '../../shared/components/icon/icon.component';

export interface ConfirmDialogOptions {
  title: string;
  message: string;
  confirmText?: string;
  cancelText?: string;
  danger?: boolean;
  icon?: IconName;
}

export interface ConfirmDialogState extends ConfirmDialogOptions {
  resolve: (value: boolean) => void;
}

@Injectable({
  providedIn: 'root',
})
export class ConfirmDialogService {
  readonly state = signal<ConfirmDialogState | null>(null);

  confirm(options: ConfirmDialogOptions): Promise<boolean> {
    return new Promise<boolean>((resolve) => {
      this.state.set({
        ...options,
        confirmText: options.confirmText ?? (options.danger ? 'Eliminar' : 'Aceptar'),
        cancelText: options.cancelText ?? 'Cancelar',
        icon: options.icon ?? (options.danger ? 'trash' : 'alert-circle'),
        resolve: (result: boolean) => {
          this.state.set(null);
          resolve(result);
        },
      });
    });
  }

  close(result: boolean): void {
    const current = this.state();
    if (current) {
      current.resolve(result);
    }
  }
}

