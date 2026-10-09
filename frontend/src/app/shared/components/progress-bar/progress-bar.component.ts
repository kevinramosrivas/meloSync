import { Component, input } from '@angular/core';
import { CommonModule } from '@angular/common';
import { TuiProgress } from '@taiga-ui/kit';

@Component({
  selector: 'app-progress-bar',
  standalone: true,
  imports: [CommonModule, TuiProgress],
  templateUrl: './progress-bar.component.html',
  styleUrl: './progress-bar.component.css'
})
export class ProgressBarComponent {
  percent = input<number>(0);
  height = input<number>(6);
  indeterminate = input<boolean>(false);
}
