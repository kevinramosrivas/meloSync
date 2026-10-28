export const API_CONFIG = {
  baseUrl: 'http://127.0.0.1:8000',
  wsUrl: 'ws://127.0.0.1:8000/ws/events',
  endpoints: {
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
  }
};
