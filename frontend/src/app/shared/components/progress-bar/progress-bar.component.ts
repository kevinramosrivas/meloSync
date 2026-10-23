import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TuiProgress } from '@taiga-ui/kit';

@Component({
  selector: 'app-progress-bar',
  imports: [CommonModule, TuiProgress],
  templateUrl: './progress-bar.component.html'
})
export class ProgressBarComponent {
  percent = input<number>(0);
  height = input<number>(6);
  indeterminate = input<boolean>(false);
}
