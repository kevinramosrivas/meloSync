import { Component, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { SettingsApiService } from '../../data/settings-api.service';
import { ToastService } from '../../core/services/toast.service';
import { AppSettings, AudioQuality } from '../../domain/models';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-settings',
  imports: [CommonModule, FormsModule, IconComponent],
  templateUrl: './settings.component.html'
})
export class SettingsComponent implements OnInit {
  private settingsApi = inject(SettingsApiService);
  private toast = inject(ToastService);

  readonly isLoading = signal<boolean>(false);
  readonly isSaving = signal<boolean>(false);

  downloadDir = '';
  selectedQuality: AudioQuality = 'best';
  normalizeLufs = -14.0;
  autoTag = true;

  readonly qualityOptions: { label: string; value: AudioQuality; desc: string }[] = [
    { label: 'Mejor Calidad', value: 'best', desc: 'Flac/Opus/V0 original' },
    { label: '320 kbps (CBR)', value: '320k', desc: 'Máxima fidelidad MP3' },
    { label: '256 kbps', value: '256k', desc: 'Excelente balance' },
    { label: '128 kbps', value: '128k', desc: 'Ahorro de espacio' },
  ];

  ngOnInit(): void {
    this.loadSettings();
  }

  loadSettings(): void {
    this.isLoading.set(true);
    this.settingsApi.getSettings().subscribe({
      next: (s) => {
        this.downloadDir = s.music_download_directory;
        this.selectedQuality = s.default_audio_quality;
        this.normalizeLufs = s.normalize_audio_lufs;
        this.autoTag = s.auto_tag_metadata;
        this.isLoading.set(false);
      },
      error: (e) => {
        this.isLoading.set(false);
        this.toast.error('Error al cargar ajustes', e.message);
      }
    });
  }

  saveSettings(): void {
    this.isSaving.set(true);
    this.settingsApi.updateSettings({
      music_download_directory: this.downloadDir,
      default_audio_quality: this.selectedQuality,
      normalize_audio_lufs: this.normalizeLufs,
      auto_tag_metadata: this.autoTag,
    }).subscribe({
      next: (s) => {
        this.isSaving.set(false);
        this.downloadDir = s.music_download_directory;
        this.toast.success('Preferencias guardadas correctamente');
      },
      error: (e) => {
        this.isSaving.set(false);
        this.toast.error('Error al guardar ajustes', e.message);
      }
    });
  }

  openFolder(): void {
    this.settingsApi.openMusicFolder().subscribe({
      next: () => this.toast.info('Carpeta abierta en explorador'),
      error: (e) => this.toast.error('No se pudo abrir carpeta', e.message)
    });
  }
}
