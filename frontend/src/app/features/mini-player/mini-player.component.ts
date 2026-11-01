import { Component, OnInit, OnDestroy, computed, inject, signal } from '@angular/core';
import { IconComponent } from '../../shared/components/icon/icon.component';
import { DurationPipe } from '../../shared/pipes/duration.pipe';
import { MarqueeTextComponent } from '../../shared/components/marquee-text/marquee-text.component';
import { MiniPlayerSyncService } from '../../core/services/mini-player-sync.service';

@Component({
  selector: 'app-mini-player',
  imports: [IconComponent, DurationPipe, MarqueeTextComponent],
  templateUrl: './mini-player.component.html'
})
export class MiniPlayerComponent implements OnInit, OnDestroy {
  readonly sync = inject(MiniPlayerSyncService);

  readonly windowHeight = signal<number>(
    typeof window !== 'undefined' ? window.innerHeight : 320
  );

  readonly windowWidth = signal<number>(
    typeof window !== 'undefined' ? window.innerWidth : 320
  );

  readonly isPillMode = computed(() => this.windowHeight() < 140);
  readonly canShowPreviousInPill = computed(() => this.windowWidth() >= 290);

  private resizeListener = (): void => {
    if (typeof window !== 'undefined') {
      this.windowHeight.set(window.innerHeight);
      this.windowWidth.set(window.innerWidth);
    }
  };

  ngOnInit(): void {
    if (typeof window !== 'undefined') {
      this.windowHeight.set(window.innerHeight);
      this.windowWidth.set(window.innerWidth);
      window.addEventListener('resize', this.resizeListener);
    }
  }

  ngOnDestroy(): void {
    if (typeof window !== 'undefined') {
      window.removeEventListener('resize', this.resizeListener);
    }
  }

  onSeekClick(event: MouseEvent): void {
    const target = event.currentTarget as HTMLElement;
    if (!target) return;
    const rect = target.getBoundingClientRect();
    if (rect.width <= 0) return;
    const clickX = event.clientX - rect.left;
    const pct = Math.max(0, Math.min(1, clickX / rect.width));
    const dur = this.sync.duration();
    if (dur > 0) {
      this.sync.seek(pct * dur);
    }
  }

  onStartDrag(event: MouseEvent): void {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest('button, input, a, [data-tauri-drag-region="false"]')) {
      return;
    }
    this.sync.startDragging();
  }

  closeMiniPlayer(): void {
    this.sync.closeMiniPlayer();
  }

  restoreMainWindow(): void {
    this.sync.focusMainWindow();
  }
}
