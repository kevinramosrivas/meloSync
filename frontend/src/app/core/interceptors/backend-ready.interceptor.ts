import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { filter, switchMap, take } from 'rxjs';
import { BackendGateService } from '../services/backend-gate.service';

export const backendReadyInterceptor: HttpInterceptorFn = (req, next) => {
  const backendGate = inject(BackendGateService);

  // External requests, assets, or font inlines pass immediately
  if (!backendGate.isBackendRequest(req.url)) {
    return next(req);
  }

  // Health-check requests pass immediately so they can probe the server
  if (req.url.endsWith('/health')) {
    return next(req);
  }

  // If backend is already verified and ready, rewrite URL if needed and proceed
  if (backendGate.isReady()) {
    const rewrittenUrl = backendGate.rewriteUrlIfNeeded(req.url);
    const updatedReq = rewrittenUrl !== req.url ? req.clone({ url: rewrittenUrl }) : req;
    return next(updatedReq);
  }

  // Otherwise, hold requests in reactive queue without failing until backend confirms ready
  return backendGate.ready$.pipe(
    filter(ready => ready === true),
    take(1),
    switchMap(() => {
      const rewrittenUrl = backendGate.rewriteUrlIfNeeded(req.url);
      const updatedReq = rewrittenUrl !== req.url ? req.clone({ url: rewrittenUrl }) : req;
      return next(updatedReq);
    })
  );
};

