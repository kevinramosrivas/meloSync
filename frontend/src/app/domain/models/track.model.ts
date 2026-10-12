export type DownloadStatus =
  | 'PENDIENTE'
  | 'DESCARGANDO'
  | 'PROCESANDO_AUDIO'
  | 'OBTENIENDO_METADATOS'
  | 'COMPLETADA'
  | 'ERROR'
  | 'CANCELADA';

export type AudioQuality = 'best' | '320k' | '256k' | '128k';

export interface TrackMetadata {
  title: string;
  artist: string;
  album: string;
  year?: number | null;
  genre?: string | null;
  track_number?: number | null;
  disc_number?: number | null;
  cover_url?: string | null;
  has_cover_bytes?: boolean;
  lyrics?: string | null;
}

export interface Track {
  id: string;
  youtube_id: string;
  url: string;
  original_title: string;
  display_title: string;
  display_artist: string;
  display_album: string;
  duration_seconds: number;
  duration_formatted: string;
  channel_name: string;
  status: DownloadStatus;
  progress_percent: number;
  file_path?: string | null;
  file_exists?: boolean;
  error_message?: string | null;
  metadata?: TrackMetadata | null;
  created_at_iso?: string;
  updated_at_iso?: string;
}

export interface SyncReport {
  repaired_count: number;
  imported_count: number;
  missing_count: number;
  total_tracks: number;
  message: string;
}
