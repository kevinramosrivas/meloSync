import { Track } from './track.model';

export type PlaylistType = 'custom' | 'top_played' | 'on_repeat' | 'artist' | 'genre';

export interface PlaylistSummary {
  id: string;
  name: string;
  description: string;
  is_smart: boolean;
  playlist_type: PlaylistType;
  filter_query?: string | null;
  cover_url?: string | null;
  track_count: number;
  duration_seconds: number;
  created_at_iso: string;
  updated_at_iso: string;
  sample_cover_track_ids?: string[];
}

export interface Playlist extends PlaylistSummary {
  tracks: Track[];
}

export interface PlaylistsGroupedResponse {
  user_playlists: PlaylistSummary[];
  for_you_playlists: PlaylistSummary[];
  artist_playlists: PlaylistSummary[];
  genre_playlists: PlaylistSummary[];
}

export interface CreatePlaylistRequest {
  name: string;
  description?: string;
}

export interface UpdatePlaylistRequest {
  name?: string;
  description?: string;
}

export interface AddTrackToPlaylistRequest {
  track_id: string;
}
