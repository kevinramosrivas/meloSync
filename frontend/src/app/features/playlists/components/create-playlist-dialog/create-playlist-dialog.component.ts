import { Component, effect, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PlaylistSummary } from '../../../../domain/models';
import { IconComponent } from '../../../../shared/components/icon/icon.component';

@Component({
  selector: 'app-create-playlist-dialog',
  imports: [FormsModule, IconComponent],
  template: `
    @if (isOpen()) {
      <div 
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-md animate-in fade-in duration-200"
        (click)="onBackdropClick($event)"
      >
        <div 
          class="relative w-full max-w-md rounded-2xl bg-[#14141c] border border-white/[0.08] shadow-2xl p-6 flex flex-col gap-5 text-white select-none animate-in zoom-in-95 duration-150"
          (click)="$event.stopPropagation()"
        >
          <!-- Header -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5">
              <div class="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-[#fa2d48] to-[#ff385c] text-white shadow-md shadow-[#fa2d48]/30">
                <app-icon name="list-music" [size]="18" />
              </div>
              <h2 class="text-lg font-bold text-white tracking-tight">
                {{ isEditMode() ? 'Editar Lista' : 'Crear Nueva Lista' }}
              </h2>
            </div>
            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
              (click)="onCancel()"
              title="Cerrar"
            >
              <app-icon name="x" [size]="18" />
            </button>
          </div>

          <!-- Form -->
          <form class="flex flex-col gap-4" (ngSubmit)="onSubmit()">
            <!-- Name Input -->
            <div class="flex flex-col gap-1.5">
              <label for="playlist-name-input" class="text-xs font-semibold text-zinc-300">
                Nombre de la lista <span class="text-[#fa2d48]">*</span>
              </label>
              <input
                id="playlist-name-input"
                type="text"
                required
                maxlength="256"
                placeholder="Ej. Mis Favoritas de Medianoche"
                [ngModel]="name()"
                (ngModelChange)="name.set($event)"
                name="name"
                class="h-10 w-full rounded-xl bg-white/[0.05] border border-white/[0.08] px-3.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-[#fa2d48] focus:ring-1 focus:ring-[#fa2d48] transition-all"
                autofocus
              />
            </div>

            <!-- Description Input -->
            <div class="flex flex-col gap-1.5">
              <label for="playlist-desc-input" class="text-xs font-semibold text-zinc-300">
                Descripción (opcional)
              </label>
              <textarea
                id="playlist-desc-input"
                rows="3"
                maxlength="1024"
                placeholder="Añade una descripción sobre el ambiente o género de esta lista..."
                [ngModel]="description()"
                (ngModelChange)="description.set($event)"
                name="description"
                class="w-full resize-none rounded-xl bg-white/[0.05] border border-white/[0.08] p-3 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-[#fa2d48] focus:ring-1 focus:ring-[#fa2d48] transition-all"
              ></textarea>
            </div>

            <!-- Action Buttons -->
            <div class="flex items-center justify-end gap-2.5 pt-2">
              <button
                type="button"
                class="h-9 px-4 rounded-xl text-sm font-medium text-zinc-300 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer"
                (click)="onCancel()"
              >
                Cancelar
              </button>
              <button
                type="submit"
                [disabled]="!name().trim()"
                class="h-9 px-5 rounded-xl text-sm font-semibold text-white bg-gradient-to-r from-[#fa2d48] to-[#ff385c] hover:opacity-95 active:scale-95 disabled:opacity-40 disabled:cursor-not-allowed shadow-md shadow-[#fa2d48]/25 transition-all cursor-pointer"
              >
                {{ isEditMode() ? 'Guardar Cambios' : 'Crear Lista' }}
              </button>
            </div>
          </form>
        </div>
      </div>
    }
  `,
})
export class CreatePlaylistDialogComponent {
  readonly isOpen = input<boolean>(false);
  readonly editPlaylist = input<PlaylistSummary | null>(null);

  readonly close = output<void>();
  readonly saved = output<{ id?: string; name: string; description: string }>();

  readonly name = signal('');
  readonly description = signal('');

  constructor() {
    effect(() => {
      const p = this.editPlaylist();
      if (p) {
        this.name.set(p.name);
        this.description.set(p.description || '');
      } else {
        this.name.set('');
        this.description.set('');
      }
    });
  }

  isEditMode(): boolean {
    return !!this.editPlaylist();
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.onCancel();
    }
  }

  onCancel(): void {
    this.close.emit();
  }

  onSubmit(): void {
    const trimmedName = this.name().trim();
    if (!trimmedName) return;

    this.saved.emit({
      id: this.editPlaylist()?.id,
      name: trimmedName,
      description: this.description().trim(),
    });
  }
}
