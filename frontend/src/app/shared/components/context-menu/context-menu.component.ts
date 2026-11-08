import { Component, computed, inject } from '@angular/core';
import { ContextMenuItem, ContextMenuService } from '../../../core/services/context-menu.service';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-context-menu',
  imports: [IconComponent],
  host: {
    '(keydown.escape)': 'contextMenu.close()',
    '(window:resize)': 'contextMenu.close()',
    '(window:scroll)': 'contextMenu.close()',
  },
  template: `
    @if (contextMenu.state(); as menu) {
      <!-- Transparent click-outside backdrop (no blur or screen dimming) -->
      <div
        class="fixed inset-0 z-50 bg-transparent"
        (click)="contextMenu.close()"
        (contextmenu)="onBackdropContextMenu($event)"
      >
        <!-- Floating Menu Card -->
        <div
          class="fixed z-50 min-w-[210px] max-w-xs rounded-2xl bg-[#15151c]/95 border border-white/10 p-1.5 shadow-[0_12px_40px_rgba(0,0,0,0.65)] backdrop-blur-2xl flex flex-col gap-0.5 select-none animate-fade-in"
          [style.left.px]="adjustedPosition().x"
          [style.top.px]="adjustedPosition().y"
          (click)="$event.stopPropagation()"
          (contextmenu)="$event.stopPropagation()"
        >
          @for (item of menu.items; track $index) {
            @if (item.separator) {
              <div class="h-px bg-white/[0.08] my-1 mx-2"></div>
            } @else {
              <button
                type="button"
                class="group flex items-center gap-2.5 w-full px-3 py-2 rounded-xl text-xs font-medium text-left transition-colors cursor-pointer disabled:opacity-40 disabled:cursor-not-allowed whitespace-nowrap"
                [class.text-zinc-200]="!item.danger && !item.disabled"
                [class.hover:bg-white/[0.08]]="!item.danger && !item.disabled"
                [class.hover:text-white]="!item.danger && !item.disabled"
                [class.text-red-400]="item.danger"
                [class.hover:bg-red-500/15]="item.danger"
                [class.hover:text-red-300]="item.danger"
                [disabled]="item.disabled"
                (click)="onItemClick(item)"
              >
                @if (item.icon) {
                  <app-icon
                    [name]="item.icon"
                    [size]="14"
                    class="shrink-0 transition-colors"
                    [class.text-zinc-400]="!item.danger"
                    [class.group-hover:text-white]="!item.danger && !item.disabled"
                    [class.text-red-400]="item.danger"
                  />
                }
                <span class="flex-1 truncate">{{ item.label }}</span>
              </button>
            }
          }
        </div>
      </div>
    }
  `,
})
export class ContextMenuComponent {
  readonly contextMenu = inject(ContextMenuService);

  readonly adjustedPosition = computed(() => {
    const state = this.contextMenu.state();
    if (!state) return { x: 0, y: 0 };

    const menuWidth = 220;
    const estimatedItemHeight = 36;
    const menuHeight = state.items.length * estimatedItemHeight + 20;
    const bottomPlayerHeight = 86;

    let x = state.x;
    let y = state.y;

    if (typeof window !== 'undefined') {
      const maxX = window.innerWidth - menuWidth - 12;
      if (x > maxX) {
        x = Math.max(12, maxX);
      }

      const maxY = window.innerHeight - bottomPlayerHeight - menuHeight - 12;
      if (y > maxY) {
        y = Math.max(12, state.y - menuHeight);
      }
    }

    return { x, y };
  });

  onItemClick(item: ContextMenuItem): void {
    if (item.disabled) return;
    this.contextMenu.close();
    if (item.action) {
      item.action();
    }
  }

  onBackdropContextMenu(event: MouseEvent): void {
    event.preventDefault();
    this.contextMenu.close();
  }
}

