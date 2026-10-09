import { DownloadProgress } from './download.model';
import { Track } from './track.model';

export type WebSocketEventType =
  | 'connected'
  | 'download_progress'
  | 'download_completed'
  | 'download_error'
  | 'library_updated';

export interface WebSocketEvent<T = any> {
  event: WebSocketEventType;
  data: T;
  timestamp?: string;
}

export interface DownloadProgressEventData extends DownloadProgress {}

export interface DownloadCompletedEventData {
  track: Track;
}
