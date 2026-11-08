import { Injectable, signal } from '@angular/core';
import { IconName } from '../../shared/components/icon/icon.component';

export interface ContextMenuItem {
  label?: string;
  icon?: IconName;
  action?: () => void;
  danger?: boolean;
  separator?: boolean;
  disabled?: boolean;
}

export interface ContextMenuState {
  x: number;
  y: number;
  items: ContextMenuItem[];
}

@Injectable({
  providedIn: 'root',
})
export class ContextMenuService {
  readonly state = signal<ContextMenuState | null>(null);

  open(options: { x: number; y: number; items: ContextMenuItem[] }): void {
    // Avoid zero items
    if (!options.items || options.items.length === 0) return;
    this.state.set(options);
  }

  close(): void {
    this.state.set(null);
  }
}

