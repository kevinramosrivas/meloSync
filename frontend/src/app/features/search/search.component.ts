import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { TuiButton } from '@taiga-ui/core';
import { SearchApiService } from '../../data/search-api.service';
import { DownloadsApiService } from '../../data/downloads-api.service';
import { ToastService } from '../../core/services/toast.service';
import { SearchResult } from '../../domain/models';
import { IconComponent } from '../../shared/components/icon/icon.component';

@Component({
  selector: 'app-search',
  standalone: true,
  imports: [CommonModule, FormsModule, TuiButton, IconComponent],
  templateUrl: './search.component.html',
  styleUrl: './search.component.css'
})
export class SearchComponent {
  private searchApi = inject(SearchApiService);
  private downloadsApi = inject(DownloadsApiService);
  private toast = inject(ToastService);
  private router = inject(Router);

  searchQuery = '';
  readonly isLoading = signal<boolean>(false);
  readonly hasSearched = signal<boolean>(false);
  readonly results = signal<SearchResult[]>([]);
  readonly downloadingIds = signal<Set<string>>(new Set());

  readonly popularTags = [
    'Daft Punk - Get Lucky',
    'The Weeknd - Blinding Lights',
    'Coldplay - Yellow',
    'Queen - Bohemian Rhapsody',
    'Michael Jackson - Billie Jean',
    'Lofi Beats to relax/study'
  ];

  onSearch(): void {
    const q = this.searchQuery.trim();
    if (!q) return;

    this.isLoading.set(true);
    this.hasSearched.set(true);

    this.searchApi.search(q, 16).subscribe({
      next: (data) => {
        this.results.set(data);
        this.isLoading.set(false);
      },
      error: (err) => {
        this.isLoading.set(false);
        this.toast.error('Error al buscar en YouTube', err.message);
      }
    });
  }

  searchTag(tag: string): void {
    this.searchQuery = tag;
    this.onSearch();
  }

  isDownloading(youtubeId: string): boolean {
    return this.downloadingIds().has(youtubeId);
  }

  download(item: SearchResult): void {
    this.downloadingIds.update(set => new Set(set).add(item.youtube_id));

    this.downloadsApi.startDownload({
      youtube_id: item.youtube_id,
      url: item.url,
      original_title: item.title,
      duration_seconds: item.duration_seconds,
      channel_name: item.channel_name,
    }).subscribe({
      next: () => {
        this.toast.success('Descarga encolada', item.title);
        this.router.navigate(['/downloads']);
      },
      error: (err) => {
        this.downloadingIds.update(set => {
          const next = new Set(set);
          next.delete(item.youtube_id);
          return next;
        });
        this.toast.error('Error al iniciar descarga', err.message);
      }
    });
  }
}
