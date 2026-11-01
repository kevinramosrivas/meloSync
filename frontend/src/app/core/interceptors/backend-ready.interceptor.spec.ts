import { describe, it, expect, beforeEach } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { HttpClient, provideHttpClient, withInterceptors } from '@angular/common/http';
import { HttpTestingController, provideHttpClientTesting } from '@angular/common/http/testing';
import { backendReadyInterceptor } from './backend-ready.interceptor';
import { BackendGateService } from '../services/backend-gate.service';
import { API_CONFIG } from '../config/api.config';

describe('backendReadyInterceptor', () => {
  let http: HttpClient;
  let httpMock: HttpTestingController;
  let gateService: BackendGateService;

  beforeEach(() => {
    API_CONFIG.setPort(8000);

    TestBed.configureTestingModule({
      providers: [
        BackendGateService,
        provideHttpClient(withInterceptors([backendReadyInterceptor])),
        provideHttpClientTesting()
      ]
    });

    http = TestBed.inject(HttpClient);
    httpMock = TestBed.inject(HttpTestingController);
    gateService = TestBed.inject(BackendGateService);
  });

  it('should let non-backend requests pass through immediately', () => {
    http.get('https://example.com/api/test').subscribe(res => {
      expect(res).toEqual({ ok: true });
    });

    const req = httpMock.expectOne('https://example.com/api/test');
    req.flush({ ok: true });
  });

  it('should let /health requests pass through immediately', () => {
    http.get('http://127.0.0.1:8000/health').subscribe(res => {
      expect(res).toEqual({ status: 'ok' });
    });

    const req = httpMock.expectOne('http://127.0.0.1:8000/health');
    req.flush({ status: 'ok' });
  });

  it('should rewrite URL and release held backend requests when gate opens', () => {
    // Start with gate closed
    gateService.isReady.set(false);
    gateService.ready$.next(false);

    let responseData: unknown = null;
    http.get('http://127.0.0.1:8000/api/v1/library').subscribe(data => {
      responseData = data;
    });

    // At this moment, request is suspended in queue waiting for backend ready
    httpMock.expectNone('http://127.0.0.1:8000/api/v1/library');

    // Backend confirms ready on new dynamic port 52345
    gateService.markReady(52345);

    // Request is released with rewritten URL!
    const req = httpMock.expectOne('http://127.0.0.1:52345/api/v1/library');
    req.flush([{ id: '1', title: 'Song' }]);

    expect(responseData).toEqual([{ id: '1', title: 'Song' }]);
  });
});

