import { Component, computed, inject, input, output } from '@angular/core';
import { Track } from '../../../domain/models';
import { AudioPlayerService } from '../../../core/services/audio-player.service';
import { IconComponent } from '../icon/icon.component';
import { EqualizerIndicatorComponent } from '../equalizer-indicator/equalizer-indicator.component';
import { CoverUrlPipe } from '../../pipes/cover-url.pipe';
import { DurationPipe } from '../../pipes/duration.pipe';

@Component({
  selector: 'app-track-row',
  imports: [IconComponent, EqualizerIndicatorComponent, CoverUrlPipe, DurationPipe],
  templateUrl: './track-row.component.html',
})
export class TrackRowComponent {
  readonly player = inject(AudioPlayerService);

  readonly track = input.required<Track>();
  readonly index = input<number>(0);
  readonly context = input<'library' | 'playlist'>('library');
  readonly isSmartPlaylist = input<boolean>(false);
  readonly showRankBadge = input<boolean>(false);

  readonly play = output<Track>();
  readonly addToPlaylist = output<{ track: Track; event: Event }>();
  readonly editMetadata = output<Track>();
  readonly openFolder = output<string>();
  readonly delete = output<Track>();
  readonly removeFromPlaylist = output<Track>();

  readonly isCurrent = computed(() => this.player.currentTrack()?.id === this.track().id);
  readonly isPlaying = computed(() => this.isCurrent() && this.player.isPlaying());

  onPlayAction(event?: Event): void {
    if (event) {
      event.stopPropagation();
    }
    if (this.isCurrent()) {
      this.player.togglePlay();
    } else {
      this.play.emit(this.track());
    }
  }

  onRowDblClick(): void {
    this.onPlayAction();
  }

  onAddToPlaylist(event: Event): void {
    event.stopPropagation();
    this.addToPlaylist.emit({ track: this.track(), event });
  }

  onEditMetadata(event: Event): void {
    event.stopPropagation();
    this.editMetadata.emit(this.track());
  }

  onOpenFolder(event: Event): void {
    event.stopPropagation();
    this.openFolder.emit(this.track().id);
  }

  onDelete(event: Event): void {
    event.stopPropagation();
    this.delete.emit(this.track());
  }

  onRemoveFromPlaylist(event: Event): void {
    event.stopPropagation();
    this.removeFromPlaylist.emit(this.track());
  }
}
