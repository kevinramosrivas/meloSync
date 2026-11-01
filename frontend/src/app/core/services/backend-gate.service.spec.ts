import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { TestBed } from '@angular/core/testing';
import { BackendGateService } from './backend-gate.service';
import { API_CONFIG } from '../config/api.config';

describe('BackendGateService', () => {
  let service: BackendGateService;

  beforeEach(() => {
    // Reset API_CONFIG port to 8000
    API_CONFIG.setPort(8000);

    TestBed.configureTestingModule({
      providers: [BackendGateService],
    });
    service = TestBed.inject(BackendGateService);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('should initialize and report readiness correctly', () => {
    expect(service).toBeTruthy();
    expect(service.port()).toBe(8000);
  });

  it('should update port and open gate when markReady is called', () => {
    service.markReady(52100);
    expect(service.isReady()).toBe(true);
    expect(service.port()).toBe(52100);
    expect(API_CONFIG.port).toBe(52100);
    expect(service.ready$.value).toBe(true);
  });

  it('should identify backend requests accurately', () => {
    expect(service.isBackendRequest('http://127.0.0.1:8000/api/v1/library')).toBe(true);
    expect(service.isBackendRequest('http://localhost:5000/api/v1/settings')).toBe(true);
    expect(service.isBackendRequest('/api/v1/downloads')).toBe(true);
    expect(service.isBackendRequest('https://fonts.googleapis.com/css2')).toBe(false);
    expect(service.isBackendRequest('/assets/logo.svg')).toBe(false);
  });

  it('should rewrite URLs to the current dynamic baseUrl', () => {
    service.markReady(49152);
    const rewritten = service.rewriteUrlIfNeeded('http://127.0.0.1:8000/api/v1/library');
    expect(rewritten).toBe('http://127.0.0.1:49152/api/v1/library');
  });

  it('should validate meloSync API identity in probeHealth and reject foreign services on port 8000', async () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch').mockImplementation(async (input) => {
      const url = String(input);
      if (url.includes(':8000/health')) {
        // Simulate foreign server occupying port 8000
        return new Response(JSON.stringify({ status: 'ok', service: 'Other Server' }), {
          status: 200,
        });
      }
      if (url.includes(':54321/health')) {
        // Simulate meloSync backend on ephemeral port 54321
        return new Response(
          JSON.stringify({ status: 'ok', service: 'meloSync API', version: '2.0.0' }),
          { status: 200 }
        );
      }
      throw new Error('Connection refused');
    });

    const isForeignHealthy = await service.probeHealth(8000);
    expect(isForeignHealthy).toBe(false);

    const isEphemeralHealthy = await service.probeHealth(54321);
    expect(isEphemeralHealthy).toBe(true);
    expect(fetchSpy).toHaveBeenCalledTimes(2);
  });
});
