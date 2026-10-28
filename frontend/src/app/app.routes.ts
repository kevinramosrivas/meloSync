import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    redirectTo: 'search',
    pathMatch: 'full'
  },
  {
    path: 'search',
    loadComponent: () => import('./features/search/search.component').then(m => m.SearchComponent),
    title: 'meloSync — Buscar y Descargar'
  },
  {
    path: 'downloads',
    loadComponent: () => import('./features/downloads/downloads.component').then(m => m.DownloadsComponent),
    title: 'meloSync — Descargas'
  },
  {
    path: 'library',
    loadComponent: () => import('./features/library/library.component').then(m => m.LibraryComponent),
    title: 'meloSync — Biblioteca'
  },
  {
    path: 'playlists',
    loadComponent: () => import('./features/playlists/playlists.component').then(m => m.PlaylistsComponent),
    title: 'meloSync — Playlists'
  },
  {
    path: 'playlists/:id',
    loadComponent: () => import('./features/playlists/playlist-detail/playlist-detail.component').then(m => m.PlaylistDetailComponent),
    title: 'meloSync — Detalle de Playlist'
  },
  {
    path: 'settings',
    loadComponent: () => import('./features/settings/settings.component').then(m => m.SettingsComponent),
    title: 'meloSync — Ajustes'
  },
  {
    path: '**',
    redirectTo: 'search'
  }
];
