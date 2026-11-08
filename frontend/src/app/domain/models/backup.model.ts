export interface BackupTrackMetadata {
  title: string;
  artist: string;
  album: string;
  year?: number | null;
  genre?: string | null;
  track_number?: number | null;
  disc_number?: number | null;
  cover_url?: string | null;
  lyrics?: string | null;
}

export interface BackupTrack {
  youtube_id: string;
  url: string;
  original_title: string;
  duration_seconds: number;
  channel_name: string;
  metadata?: BackupTrackMetadata | null;
  play_count: number;
  last_played_at_iso?: string | null;
}

export interface BackupPlaylist {
  name: string;
  description: string;
  cover_url?: string | null;
  track_youtube_ids: string[];
}

export interface BackupSettings {
  default_audio_quality: string;
  normalize_audio_lufs: number;
  auto_tag_metadata: boolean;
  skip_non_music_sections?: boolean;
  trim_silence?: boolean;
  user_preferences: Record<string, unknown>;
}

export interface MeloSyncBackupPayload {
  format: string;
  version: number;
  exported_at_iso: string;
  app_version: string;
  settings: BackupSettings;
  tracks: BackupTrack[];
  playlists: BackupPlaylist[];
}

export interface ImportBackupOptions {
  download_missing_audio: boolean;
  restore_settings: boolean;
  restore_preferences: boolean;
  overwrite_existing_metadata: boolean;
}

export interface ImportBackupResult {
  status: string;
  message: string;
  total_tracks_in_backup: number;
  tracks_imported: number;
  tracks_already_present: number;
  tracks_queued_for_download: number;
  playlists_imported: number;
  settings_restored: boolean;
  user_preferences: Record<string, unknown>;
}

