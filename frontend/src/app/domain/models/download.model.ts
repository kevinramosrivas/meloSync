import { AudioQuality, DownloadStatus } from './track.model';

export interface DownloadRequest {
  youtube_id: string;
  url: string;
  original_title: string;
  duration_seconds: number;
  channel_name: string;
  quality?: AudioQuality;
}

export interface DownloadProgress {
  track_id: string;
  youtube_id: string;
  status: DownloadStatus;
  progress_percent: number;
  stage_description: string;
  speed_text?: string;
  eta_text?: string;
}
