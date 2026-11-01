import { describe, it, expect } from 'vitest';
import { API_CONFIG } from './api.config';

describe('API_CONFIG (ApiConfigManager)', () => {
  it('should initialize with default port 8000', () => {
    API_CONFIG.setPort(8000);
    expect(API_CONFIG.port).toBe(8000);
    expect(API_CONFIG.baseUrl).toBe('http://127.0.0.1:8000');
    expect(API_CONFIG.wsUrl).toBe('ws://127.0.0.1:8000/ws/events');
  });

  it('should dynamically update baseUrl and wsUrl when port changes', () => {
    API_CONFIG.setPort(54321);
    expect(API_CONFIG.port).toBe(54321);
    expect(API_CONFIG.baseUrl).toBe('http://127.0.0.1:54321');
    expect(API_CONFIG.wsUrl).toBe('ws://127.0.0.1:54321/ws/events');

    // Reset back to 8000 for other tests
    API_CONFIG.setPort(8000);
  });

  it('should ignore invalid port numbers', () => {
    API_CONFIG.setPort(8000);
    API_CONFIG.setPort(-1);
    expect(API_CONFIG.port).toBe(8000);

    API_CONFIG.setPort(70000);
    expect(API_CONFIG.port).toBe(8000);
  });

  it('should provide correct REST endpoints', () => {
    expect(API_CONFIG.endpoints.library).toBe('/api/v1/library');
    expect(API_CONFIG.endpoints.stream('track-123')).toBe('/api/v1/library/track-123/stream');
    expect(API_CONFIG.endpoints.cover('track-123')).toBe('/api/v1/library/track-123/cover');
  });
});

