import { Component, input } from '@angular/core';

@Component({
  selector: 'app-equalizer-indicator',
  template: `
    <svg
      xmlns="http://www.w3.org/2000/svg"
      [attr.width]="size()"
      [attr.height]="size()"
      viewBox="0 0 16 16"
      fill="currentColor"
      class="app-equalizer-svg"
      [class.paused]="!isPlaying()"
      role="img"
      [attr.aria-label]="isPlaying() ? 'Pista en reproducción' : 'Pista en pausa'"
    >
      <rect x="1" y="2" width="2.2" height="12" rx="1" class="eq-bar bar-1" />
      <rect x="5" y="1" width="2.2" height="14" rx="1" class="eq-bar bar-2" />
      <rect x="9" y="3" width="2.2" height="11" rx="1" class="eq-bar bar-3" />
      <rect x="13" y="1" width="2.2" height="13" rx="1" class="eq-bar bar-4" />
    </svg>
  `,
  styles: `
    :host {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      line-height: 0;
      color: var(--color-accent, #fa2d48);
    }
    .app-equalizer-svg {
      display: block;
      flex-shrink: 0;
    }
    .eq-bar {
      transform-origin: bottom;
      animation: eqBounce 0.8s ease-in-out infinite alternate;
    }
    .bar-1 {
      animation-duration: 0.72s;
      animation-delay: 0.1s;
    }
    .bar-2 {
      animation-duration: 0.52s;
      animation-delay: 0.25s;
    }
    .bar-3 {
      animation-duration: 0.64s;
      animation-delay: 0.05s;
    }
    .bar-4 {
      animation-duration: 0.58s;
      animation-delay: 0.3s;
    }

    .paused .eq-bar {
      animation-play-state: paused;
      transform: scaleY(0.3);
    }

    @keyframes eqBounce {
      0% {
        transform: scaleY(0.2);
      }
      100% {
        transform: scaleY(1);
      }
    }
  `
})
export class EqualizerIndicatorComponent {
  readonly isPlaying = input<boolean>(true);
  readonly size = input<number>(16);
}
