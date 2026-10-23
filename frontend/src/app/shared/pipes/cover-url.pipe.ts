import { Pipe, PipeTransform, inject } from '@angular/core';
import { Track } from '../../domain/models';
import { CoverCacheService } from '../../core/services/cover-cache.service';

@Pipe({
  name: 'coverUrl',
  pure: true
})
export class CoverUrlPipe implements PipeTransform {
  private readonly coverCache = inject(CoverCacheService);

  transform(track: Track | null | undefined): string | null {
    if (!track) return null;
    return this.coverCache.getCoverUrl(track);
  }
}
