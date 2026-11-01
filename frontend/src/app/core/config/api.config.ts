class ApiConfigManager {
  private _port: number = 8000;

  get port(): number {
    return this._port;
  }

  setPort(port: number): void {
    if (port && port > 0 && port <= 65535) {
      this._port = port;
    }
  }

  get baseUrl(): string {
    return `http://127.0.0.1:${this._port}`;
  }

  get wsUrl(): string {
    return `ws://127.0.0.1:${this._port}/ws/events`;
  }

  readonly endpoints = {
    search: '/api/v1/search',
    downloads: '/api/v1/downloads',
    library: '/api/v1/library',
    metadata: '/api/v1/metadata',
    settings: '/api/v1/settings',
    stream: (id: string) => `/api/v1/library/${id}/stream`,
    cover: (id: string) => `/api/v1/library/${id}/cover`,
    openFile: (id: string) => `/api/v1/library/${id}/open-file`,
    openFolder: (id: string) => `/api/v1/library/${id}/open-folder`,
    recordPlay: (id: string) => `/api/v1/library/${id}/record-play`,
    playlists: '/api/v1/playlists',
    playlistDetail: (id: string) => `/api/v1/playlists/${id}`,
    playlistTracks: (id: string) => `/api/v1/playlists/${id}/tracks`,
    playlistTrackDelete: (playlistId: string, trackId: string) => `/api/v1/playlists/${playlistId}/tracks/${trackId}`,
    playlistsSync: '/api/v1/playlists/sync-smart',
  };
}

export const API_CONFIG = new ApiConfigManager();
