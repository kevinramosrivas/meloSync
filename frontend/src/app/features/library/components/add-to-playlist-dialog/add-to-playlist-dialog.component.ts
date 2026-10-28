import { Component, effect, inject, input, output, signal } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { PlaylistsApiService } from '../../../../data/playlists-api.service';
import { PlaylistSummary, Track } from '../../../../domain/models';
import { ToastService } from '../../../../core/services/toast.service';
import { IconComponent } from '../../../../shared/components/icon/icon.component';

@Component({
  selector: 'app-add-to-playlist-dialog',
  imports: [FormsModule, IconComponent],
  template: `
    @if (isOpen() && track()) {
      <div 
        class="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/75 backdrop-blur-md animate-in fade-in duration-200"
        (click)="onBackdropClick($event)"
      >
        <div 
          class="relative w-full max-w-md rounded-2xl bg-[#14141c] border border-white/[0.08] shadow-2xl p-6 flex flex-col gap-4 text-white select-none animate-in zoom-in-95 duration-150"
          (click)="$event.stopPropagation()"
        >
          <!-- Header -->
          <div class="flex items-center justify-between">
            <div class="flex items-center gap-2.5 min-w-0">
              <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-[#fa2d48] to-[#ff385c] text-white shadow-md shadow-[#fa2d48]/30">
                <app-icon name="list-music" [size]="18" />
              </div>
              <div class="flex flex-col min-w-0">
                <h2 class="text-base font-bold text-white tracking-tight truncate">
                  Añadir a Playlist
                </h2>
                <span class="text-xs text-zinc-400 truncate">
                  {{ track()?.display_title }} • {{ track()?.display_artist }}
                </span>
              </div>
            </div>
            <button
              type="button"
              class="flex h-8 w-8 items-center justify-center rounded-lg text-zinc-400 hover:text-white hover:bg-white/[0.08] transition-colors cursor-pointer shrink-0"
              (click)="onClose()"
              title="Cerrar"
            >
              <app-icon name="x" [size]="18" />
            </button>
          </div>

          <!-- Quick Create Mode Toggle -->
          @if (!showCreateForm()) {
            <div class="flex flex-col gap-2">
              <div class="flex items-center justify-between pt-1">
                <span class="text-xs font-semibold uppercase tracking-wider text-zinc-400">
                  Tus Listas
                </span>
                <button
                  type="button"
                  class="text-xs font-medium text-[#fa2d48] hover:text-[#ff385c] transition-colors cursor-pointer"
                  (click)="showCreateForm.set(true)"
                >
                  + Nueva Lista
                </button>
              </div>

              <!-- List of Custom Playlists -->
              <div class="flex flex-col gap-1.5 max-h-60 overflow-y-auto pr-1 select-none">
                @if (isLoading()) {
                  <div class="py-8 text-center text-xs text-zinc-500">
                    Cargando listas...
                  </div>
                } @else if (userPlaylists().length === 0) {
                  <div class="py-6 flex flex-col items-center justify-center gap-2 text-center text-zinc-400">
                    <p class="text-xs">Aún no has creado ninguna playlist personal.</p>
                    <button
                      type="button"
                      class="h-8 px-3 rounded-lg text-xs font-semibold text-white bg-white/[0.08] hover:bg-white/[0.14] transition-colors cursor-pointer"
                      (click)="showCreateForm.set(true)"
                    >
                      Crear primera lista
                    </button>
                  </div>
                } @else {
                  @for (playlist of userPlaylists(); track playlist.id) {
                    <button
                      type="button"
                      class="flex items-center justify-between p-2.5 rounded-xl bg-white/[0.03] hover:bg-white/[0.08] border border-transparent hover:border-white/[0.08] transition-all text-left group cursor-pointer"
                      (click)="addToPlaylist(playlist)"
                      [disabled]="isAdding()"
                    >
                      <div class="flex items-center gap-3 min-w-0">
                        <div class="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-zinc-800 text-zinc-400 group-hover:text-white transition-colors">
                          <app-icon name="list" [size]="16" />
                        </div>
                        <div class="flex flex-col min-w-0">
                          <span class="text-sm font-medium text-white truncate group-hover:text-[#fa2d48] transition-colors">
                            {{ playlist.name }}
                          </span>
                          <span class="text-xs text-zinc-400">
                            {{ playlist.track_count }} {{ playlist.track_count === 1 ? 'canción' : 'canciones' }}
                          </span>
                        </div>
                      </div>
                      <span class="text-xs font-semibold text-zinc-400 group-hover:text-white transition-colors">
                        Añadir +
                      </span>
                    </button>
                  }
                }
              </div>
            </div>
          } @else {
            <!-- Embedded Create Form -->
            <form class="flex flex-col gap-3 py-1" (ngSubmit)="onCreateAndAdd()">
              <div class="flex flex-col gap-1.5">
                <label for="quick-playlist-name" class="text-xs font-semibold text-zinc-300">
                  Nombre de la nueva lista <span class="text-[#fa2d48]">*</span>
                </label>
                <input
                  id="quick-playlist-name"
                  type="text"
                  required
                  placeholder="Ej. Favoritas del Mes"
                  [ngModel]="newPlaylistName()"
                  (ngModelChange)="newPlaylistName.set($event)"
                  name="newPlaylistName"
                  class="h-10 w-full rounded-xl bg-white/[0.05] border border-white/[0.08] px-3.5 text-sm text-white placeholder-zinc-500 focus:outline-none focus:border-[#fa2d48] focus:ring-1 focus:ring-[#fa2d48] transition-all"
                  autofocus
                />
              </div>

              <div class="flex items-center justify-end gap-2 pt-2">
                <button
                  type="button"
                  class="h-8 px-3 rounded-xl text-xs font-medium text-zinc-400 hover:text-white transition-colors cursor-pointer"
                  (click)="showCreateForm.set(false)"
                >
                  Volver a la lista
                </button>
                <button
                  type="submit"
                  [disabled]="!newPlaylistName().trim() || isAdding()"
                  class="h-8 px-4 rounded-xl text-xs font-semibold text-white bg-gradient-to-r from-[#fa2d48] to-[#ff385c] hover:opacity-95 disabled:opacity-40 transition-all cursor-pointer shadow-md shadow-[#fa2d48]/25"
                >
                  Crear y Añadir
                </button>
              </div>
            </form>
          }
        </div>
      </div>
    }
  `,
})
export class AddToPlaylistDialogComponent {
  private readonly playlistsApi = inject(PlaylistsApiService);
  private readonly toast = inject(ToastService);

  readonly isOpen = input<boolean>(false);
  readonly track = input<Track | null>(null);
  readonly close = output<void>();

  readonly userPlaylists = signal<PlaylistSummary[]>([]);
  readonly isLoading = signal(false);
  readonly isAdding = signal(false);
  readonly showCreateForm = signal(false);
  readonly newPlaylistName = signal('');

  constructor() {
    effect(() => {
      if (this.isOpen()) {
        this.loadPlaylists();
        this.showCreateForm.set(false);
        this.newPlaylistName.set('');
      }
    });
  }

  loadPlaylists(): void {
    this.isLoading.set(true);
    this.playlistsApi.getPlaylists().subscribe({
      next: (resp) => {
        this.userPlaylists.set(resp.user_playlists);
        this.isLoading.set(false);
      },
      error: () => {
        this.isLoading.set(false);
        this.toast.error('Error al cargar listas', 'No se pudieron recuperar las playlists del usuario.');
      },
    });
  }

  addToPlaylist(playlist: PlaylistSummary): void {
    const t = this.track();
    if (!t) return;

    this.isAdding.set(true);
    this.playlistsApi.addTrackToPlaylist(playlist.id, t.id).subscribe({
      next: () => {
        this.isAdding.set(false);
        this.toast.success(
          'Canción añadida',
          `"${t.display_title}" fue agregada a "${playlist.name}".`
        );
        this.onClose();
      },
      error: () => {
        this.isAdding.set(false);
        this.toast.error('No se pudo añadir', 'La canción ya podría estar en la lista o hubo un fallo de red.');
      },
    });
  }

  onCreateAndAdd(): void {
    const name = this.newPlaylistName().trim();
    const t = this.track();
    if (!name || !t) return;

    this.isAdding.set(true);
    this.playlistsApi.createPlaylist({ name }).subscribe({
      next: (created) => {
        this.playlistsApi.addTrackToPlaylist(created.id, t.id).subscribe({
          next: () => {
            this.isAdding.set(false);
            this.toast.success('Lista creada', `"${t.display_title}" fue añadida a "${created.name}".`);
            this.onClose();
          },
          error: () => {
            this.isAdding.set(false);
            this.onClose();
          },
        });
      },
      error: () => {
        this.isAdding.set(false);
        this.toast.error('Error al crear lista', 'No se pudo crear la playlist.');
      },
    });
  }

  onBackdropClick(event: MouseEvent): void {
    if (event.target === event.currentTarget) {
      this.onClose();
    }
  }

  onClose(): void {
    this.close.emit();
  }
}
