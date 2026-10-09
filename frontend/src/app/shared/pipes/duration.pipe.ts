import { Pipe, PipeTransform } from '@angular/core';

@Pipe({
  name: 'duration',
  standalone: true
})
export class DurationPipe implements PipeTransform {
  transform(seconds: number | undefined | null): string {
    if (!seconds || isNaN(seconds) || seconds < 0) {
      return '0:00';
    }

    const totalSeconds = Math.floor(seconds);
    const mins = Math.floor(totalSeconds / 60);
    const secs = totalSeconds % 60;
    const hours = Math.floor(mins / 60);
    const remMins = mins % 60;

    const formattedSecs = secs < 10 ? `0${secs}` : `${secs}`;

    if (hours > 0) {
      const formattedMins = remMins < 10 ? `0${remMins}` : `${remMins}`;
      return `${hours}:${formattedMins}:${formattedSecs}`;
    }

    return `${mins}:${formattedSecs}`;
  }
}
