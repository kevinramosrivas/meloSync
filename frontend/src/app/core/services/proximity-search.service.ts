import { Service } from '@angular/core';
import { Track } from '../../domain/models';

export interface MetadataFieldWeight {
  getter: (track: Track) => string;
  weight: number;
}

@Service()
export class ProximitySearchService {
  private readonly fieldExtractors: MetadataFieldWeight[] = [
    { getter: (t) => t.display_title || '', weight: 1.0 },
    { getter: (t) => t.display_artist || '', weight: 0.95 },
    { getter: (t) => t.display_album || '', weight: 0.8 },
    { getter: (t) => t.metadata?.genre || '', weight: 0.65 },
    { getter: (t) => (t.metadata?.year != null ? String(t.metadata.year) : ''), weight: 0.55 },
    { getter: (t) => t.channel_name || '', weight: 0.45 },
    { getter: (t) => t.original_title || '', weight: 0.4 },
    { getter: (t) => t.metadata?.lyrics || '', weight: 0.3 }
  ];

  /**
   * Searches and filters tracks using local fuzzy proximity scoring.
   * Ranks results descending by match relevance.
   */
  searchTracks(tracks: Track[], query: string, threshold = 0.28): Track[] {
    const cleanQuery = this.normalize(query);
    if (!cleanQuery) {
      return tracks;
    }

    const queryTokens = cleanQuery.split(' ').filter((tok) => tok.length > 0);
    if (queryTokens.length === 0) {
      return tracks;
    }

    const scoredTracks: { track: Track; score: number }[] = [];

    for (const track of tracks) {
      const score = this.calculateTrackScore(track, queryTokens, cleanQuery);
      if (score >= threshold) {
        scoredTracks.push({ track, score });
      }
    }

    // Sort descending by highest relevance score
    scoredTracks.sort((a, b) => b.score - a.score);

    return scoredTracks.map((item) => item.track);
  }

  /**
   * Evaluates how well a track matches all query tokens.
   */
  private calculateTrackScore(track: Track, tokens: string[], fullQuery: string): number {
    // Pre-extract and normalize all fields for this track
    const normalizedFields = this.fieldExtractors.map((f) => ({
      text: this.normalize(f.getter(track)),
      weight: f.weight
    }));

    // Check for full phrase exact or substring match (huge bonus)
    for (const field of normalizedFields) {
      if (!field.text) continue;
      if (field.text === fullQuery) {
        return 1.2 * field.weight;
      }
      if (field.text.startsWith(fullQuery)) {
        return 1.05 * field.weight;
      }
      if (field.text.includes(fullQuery)) {
        return 0.95 * field.weight;
      }
    }

    // Evaluate token by token: all tokens must match at least one field with sufficient proximity
    let totalScore = 0;

    for (const token of tokens) {
      let bestTokenScore = 0;

      for (const field of normalizedFields) {
        if (!field.text) continue;
        const fieldMatchScore = this.matchTokenInField(token, field.text);
        const weightedScore = fieldMatchScore * field.weight;
        if (weightedScore > bestTokenScore) {
          bestTokenScore = weightedScore;
        }
      }

      // If any token has no good proximity match, the track doesn't match the query
      if (bestTokenScore < 0.25) {
        return 0;
      }

      totalScore += bestTokenScore;
    }

    return totalScore / tokens.length;
  }

  /**
   * Matches a single token against a field string using exact, prefix,
   * substring, acronym, and Levenshtein edit distance.
   */
  private matchTokenInField(token: string, fieldText: string): number {
    if (fieldText === token) return 1.0;
    if (fieldText.startsWith(token)) return 0.9;
    if (fieldText.includes(token)) return 0.78;

    const words = fieldText.split(' ').filter((w) => w.length > 0);

    // Acronym match (e.g. "rhcp" for "red hot chili peppers")
    if (words.length > 1 && token.length === words.length) {
      const acronym = words.map((w) => w[0]).join('');
      if (acronym === token) return 0.85;
    }

    let bestWordScore = 0;

    for (const word of words) {
      if (word === token) return 1.0;
      if (word.startsWith(token)) return 0.88;
      if (token.startsWith(word) && word.length >= 3) return 0.8;

      // Fuzzy edit distance for typo tolerance
      const maxAllowedDistance = token.length <= 3 ? 0 : token.length <= 5 ? 1 : 2;
      if (maxAllowedDistance > 0 && Math.abs(word.length - token.length) <= maxAllowedDistance) {
        const dist = this.levenshtein(token, word, maxAllowedDistance);
        if (dist <= maxAllowedDistance) {
          const maxLen = Math.max(token.length, word.length);
          const similarity = 1 - dist / maxLen;
          const fuzzyScore = similarity * 0.75;
          if (fuzzyScore > bestWordScore) {
            bestWordScore = fuzzyScore;
          }
        }
      }
    }

    return bestWordScore;
  }

  /**
   * Calculates Levenshtein distance with early exit threshold.
   */
  private levenshtein(a: string, b: string, maxAllowed: number): number {
    const aLen = a.length;
    const bLen = b.length;

    if (Math.abs(aLen - bLen) > maxAllowed) return maxAllowed + 1;

    let v0 = new Array<number>(bLen + 1);
    let v1 = new Array<number>(bLen + 1);

    for (let i = 0; i <= bLen; i++) {
      v0[i] = i;
    }

    for (let i = 0; i < aLen; i++) {
      v1[0] = i + 1;
      let minRow = v1[0];

      for (let j = 0; j < bLen; j++) {
        const cost = a[i] === b[j] ? 0 : 1;
        v1[j + 1] = Math.min(v1[j] + 1, v0[j + 1] + 1, v0[j] + cost);
        if (v1[j + 1] < minRow) {
          minRow = v1[j + 1];
        }
      }

      if (minRow > maxAllowed) return maxAllowed + 1;

      // Swap rows
      const tmp = v0;
      v0 = v1;
      v1 = tmp;
    }

    return v0[bLen];
  }

  /**
   * Normalizes strings: lowercase, removes diacritics/accents and punctuation.
   */
  normalize(str: string): string {
    if (!str) return '';
    return str
      .toLowerCase()
      .normalize('NFD')
      .replace(/[\u0300-\u036f]/g, '')
      .replace(/[^\w\s]/g, ' ')
      .replace(/\s+/g, ' ')
      .trim();
  }
}
