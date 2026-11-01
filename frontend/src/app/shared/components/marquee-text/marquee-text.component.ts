import {
  Component,
  ElementRef,
  OnDestroy,
  afterNextRender,
  computed,
  effect,
  inject,
  input,
  signal,
  viewChild,
} from '@angular/core';

@Component({
  selector: 'app-marquee-text',
  host: {
    class: 'block overflow-hidden relative w-full min-w-0 select-none',
  },
  template: `
    <div
      #container
      class="relative w-full overflow-hidden whitespace-nowrap min-w-0 flex items-center"
      [class.mask-fade]="isOverflowing()"
      [attr.title]="text()"
      [attr.aria-label]="text()"
    >
      <div
        #content
        class="whitespace-nowrap inline-block min-w-0 transition-transform"
        [class.animate-marquee-bounce]="isOverflowing()"
        [class.truncate]="!isOverflowing()"
        [class]="customClass()"
        [style.--marquee-distance]="'-' + overflowDistance() + 'px'"
        [style.--marquee-duration]="animationDuration()"
      >
        {{ text() }}
      </div>
    </div>
  `,
  styles: `
    .mask-fade {
      mask-image: linear-gradient(
        90deg,
        transparent 0,
        black 6px,
        black calc(100% - 8px),
        transparent 100%
      );
      -webkit-mask-image: linear-gradient(
        90deg,
        transparent 0,
        black 6px,
        black calc(100% - 8px),
        transparent 100%
      );
    }

    @keyframes marqueeBounce {
      0%, 20% {
        transform: translateX(0);
      }
      70%, 85% {
        transform: translateX(var(--marquee-distance, 0px));
      }
      100% {
        transform: translateX(0);
      }
    }

    .animate-marquee-bounce {
      will-change: transform;
      animation: marqueeBounce var(--marquee-duration, 7s) cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite;
    }
  `,
})
export class MarqueeTextComponent implements OnDestroy {
  readonly text = input.required<string>();
  readonly customClass = input<string>('');

  private readonly containerRef = viewChild<ElementRef<HTMLElement>>('container');
  private readonly contentRef = viewChild<ElementRef<HTMLElement>>('content');

  readonly isOverflowing = signal<boolean>(false);
  readonly overflowDistance = signal<number>(0);

  readonly animationDuration = computed(() => {
    const dist = this.overflowDistance();
    if (dist <= 0) return '0s';
    // Smooth reading speed: ~30px per second plus 3.5s pause allowances
    const calculatedSec = Math.max(5.5, Math.min(14, dist / 28 + 3.5));
    return `${calculatedSec.toFixed(1)}s`;
  });

  private resizeObserver: ResizeObserver | null = null;

  constructor() {
    afterNextRender(() => {
      this.initObserver();
      this.checkOverflow();
    });

    effect(() => {
      // Re-evaluate whenever the input text changes
      this.text();
      setTimeout(() => this.checkOverflow(), 30);
    });
  }

  private initObserver(): void {
    if (typeof window === 'undefined' || typeof ResizeObserver === 'undefined') return;

    const containerEl = this.containerRef()?.nativeElement;
    const contentEl = this.contentRef()?.nativeElement;
    if (!containerEl || !contentEl) return;

    this.resizeObserver = new ResizeObserver(() => {
      this.checkOverflow();
    });

    this.resizeObserver.observe(containerEl);
    this.resizeObserver.observe(contentEl);
  }

  checkOverflow(): void {
    const container = this.containerRef()?.nativeElement;
    const content = this.contentRef()?.nativeElement;
    if (!container || !content) return;

    const containerWidth = container.clientWidth;
    const contentWidth = content.scrollWidth;

    const diff = contentWidth - containerWidth;
    if (diff > 4) {
      this.overflowDistance.set(diff + 10);
      this.isOverflowing.set(true);
    } else {
      this.overflowDistance.set(0);
      this.isOverflowing.set(false);
    }
  }

  ngOnDestroy(): void {
    if (this.resizeObserver) {
      this.resizeObserver.disconnect();
      this.resizeObserver = null;
    }
  }
}

