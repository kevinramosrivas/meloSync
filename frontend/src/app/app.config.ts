import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideRouter, withComponentInputBinding } from '@angular/router';
import { provideHttpClient, withFetch } from '@angular/common/http';
import { provideNoopAnimations } from '@angular/platform-browser/animations';
import { NG_EVENT_PLUGINS } from '@taiga-ui/event-plugins';
import { provideTaiga } from '@taiga-ui/core';
import { routes } from './app.routes';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),
    provideNoopAnimations(),
    provideRouter(routes, withComponentInputBinding()),
    provideHttpClient(withFetch()),
    NG_EVENT_PLUGINS,
    provideTaiga({ mode: 'dark' })
  ]
};
