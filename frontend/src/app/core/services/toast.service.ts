import { Injectable, signal } from '@angular/core';

export type ToastType = 'success' | 'error' | 'info' | 'warning';

export interface ToastMessage {
  id: string;
  type: ToastType;
  title: string;
  message: string;
  durationMs?: number;
}

@Injectable({
  providedIn: 'root'
})
export class ToastService {
  private toastsSignal = signal<ToastMessage[]>([]);
  readonly toasts = this.toastsSignal.asReadonly();

  show(title: string, message: string, type: ToastType = 'info', durationMs: number = 4000): void {
    const id = Math.random().toString(36).substring(2, 9);
    const toast: ToastMessage = { id, title, message, type, durationMs };

    this.toastsSignal.update(list => [...list, toast]);

    if (durationMs > 0) {
      setTimeout(() => {
        this.dismiss(id);
      }, durationMs);
    }
  }

  success(title: string, message: string = ''): void {
    this.show(title, message, 'success', 3500);
  }

  error(title: string, message: string = ''): void {
    this.show(title, message, 'error', 5000);
  }

  info(title: string, message: string = ''): void {
    this.show(title, message, 'info', 3500);
  }

  warning(title: string, message: string = ''): void {
    this.show(title, message, 'warning', 4000);
  }

  dismiss(id: string): void {
    this.toastsSignal.update(list => list.filter(t => t.id !== id));
  }
}
