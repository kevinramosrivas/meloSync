import { Component, inject } from '@angular/core';
import { ConfirmDialogService } from '../../../core/services/confirm-dialog.service';
import { IconComponent } from '../icon/icon.component';

@Component({
  selector: 'app-confirm-dialog',
  imports: [IconComponent],
  host: {
    '(keydown.escape)': 'onCancel()',
    '(keydown.enter)': 'onConfirm()',
  },
  template: `
    @if (confirmService.state(); as dialog) {
      <div
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-fade-in"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-desc"
        (click)="onBackdropClick($event)"
      >
        <div
          class="relative w-full max-w-md rounded-2xl bg-[#15151c]/95 border border-white/10 shadow-[0_20px_50px_rgba(0,0,0,0.8)] p-6 flex flex-col gap-5 text-white select-none animate-fade-in backdrop-blur-2xl"
          (click)="$event.stopPropagation()"
        >
          <!-- Top Row: Icon Badge & Content -->
          <div class="flex items-start gap-4">
            <div
              class="w-11 h-11 rounded-2xl flex items-center justify-center shrink-0 shadow-lg"
              [class.bg-red-500/15]="dialog.danger"
              [class.border]="true"
              [class.border-red-500/30]="dialog.danger"
              [class.text-red-400]="dialog.danger"
              [class.shadow-red-500/10]="dialog.danger"
              [class.bg-[#fa2d48]/15]="!dialog.danger"
              [class.border-[#fa2d48]/30]="!dialog.danger"
              [class.text-[#fa2d48]]="!dialog.danger"
            >
              <app-icon [name]="dialog.icon || 'alert-circle'" [size]="22" />
            </div>

            <div class="flex flex-col gap-1.5 min-w-0 flex-1">
              <h2 id="confirm-dialog-title" class="text-base font-bold text-white tracking-tight leading-snug">
                {{ dialog.title }}
              </h2>
              <p id="confirm-dialog-desc" class="text-xs text-zinc-300/90 leading-relaxed break-words">
                {{ dialog.message }}
              </p>
            </div>
          </div>

          <!-- Action Buttons -->
          <div class="flex items-center justify-end gap-2.5 pt-2 border-t border-white/10">
            <button
              type="button"
              class="h-9 px-4 rounded-xl text-xs font-semibold text-zinc-300 hover:text-white bg-white/[0.06] hover:bg-white/[0.12] border border-white/[0.08] transition-colors cursor-pointer"
              (click)="onCancel()"
            >
              {{ dialog.cancelText }}
            </button>

            <button
              type="button"
              class="flex items-center gap-1.5 h-9 px-5 rounded-xl text-xs font-semibold text-white transition-all cursor-pointer shadow-md active:scale-95 bg-gradient-to-r"
              [class.from-red-600]="dialog.danger"
              [class.to-rose-600]="dialog.danger"
              [class.hover:from-red-500]="dialog.danger"
              [class.hover:to-rose-500]="dialog.danger"
              [class.shadow-red-600/30]="dialog.danger"
              [class.border]="dialog.danger"
              [class.border-red-500/30]="dialog.danger"
              [class.from-[#fa2d48]]="!dialog.danger"
              [class.to-[#ff385c]]="!dialog.danger"
              [class.hover:opacity-95]="!dialog.danger"
              [class.shadow-[#fa2d48]/25]="!dialog.danger"
              (click)="onConfirm()"
            >
              @if (dialog.danger) {
                <app-icon name="trash" [size]="14" />
              } @else {
                <app-icon name="check" [size]="14" />
              }
              <span>{{ dialog.confirmText }}</span>
            </button>
          </div>
        </div>
      </div>
    }
  `,
})
export class ConfirmDialogComponent {
  readonly confirmService = inject(ConfirmDialogService);

  onConfirm(): void {
    this.confirmService.close(true);
  }

  onCancel(): void {
    this.confirmService.close(false);
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.onCancel();
    }
  }
}

