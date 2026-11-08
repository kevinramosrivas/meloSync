import { AudioQuality } from './track.model';

export interface AppSettings {
  music_download_directory: string;
  default_audio_quality: AudioQuality;
  normalize_audio_lufs: number;
  auto_tag_metadata: boolean;
  skip_non_music_sections?: boolean;
  trim_silence?: boolean;
  backend_version?: string;
}

export interface UpdateSettingsRequest {
  music_download_directory: string;
  default_audio_quality: AudioQuality;
  normalize_audio_lufs: number;
  auto_tag_metadata: boolean;
  skip_non_music_sections?: boolean;
  trim_silence?: boolean;
}

export interface StorageStats {
  active_directory: string;
  active_dir_track_count: number;
  other_locations_track_count: number;
  missing_files_count: number;
  total_library_tracks: number;
  active_dir_size_bytes: number;
  active_dir_size_formatted: string;
}

export interface ConsolidateReport {
  moved_count: number;
  already_there_count: number;
  missing_count: number;
  total_tracks: number;
  target_directory: string;
  message: string;
}
