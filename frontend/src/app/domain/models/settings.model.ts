import { AudioQuality } from './track.model';

export interface AppSettings {
  music_download_directory: string;
  default_audio_quality: AudioQuality;
  normalize_audio_lufs: number;
  auto_tag_metadata: boolean;
}

export interface UpdateSettingsRequest {
  music_download_directory: string;
  default_audio_quality: AudioQuality;
  normalize_audio_lufs: number;
  auto_tag_metadata: boolean;
}
