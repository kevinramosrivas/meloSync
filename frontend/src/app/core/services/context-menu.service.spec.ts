import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ContextMenuService } from './context-menu.service';

describe('ContextMenuService', () => {
  let service: ContextMenuService;

  beforeEach(() => {
    service = new ContextMenuService();
  });

  it('should initialize with null state', () => {
    expect(service.state()).toBeNull();
  });

  it('should open context menu with valid items', () => {
    const actionSpy = vi.fn();
    service.open({
      x: 150,
      y: 200,
      items: [
        { label: 'Reproducir', icon: 'play', action: actionSpy },
        { separator: true },
        { label: 'Eliminar', icon: 'trash', danger: true },
      ],
    });

    const state = service.state();
    expect(state).not.toBeNull();
    expect(state?.x).toBe(150);
    expect(state?.y).toBe(200);
    expect(state?.items.length).toBe(3);
  });

  it('should ignore open if items array is empty', () => {
    service.open({
      x: 100,
      y: 100,
      items: [],
    });

    expect(service.state()).toBeNull();
  });

  it('should close context menu', () => {
    service.open({
      x: 100,
      y: 100,
      items: [{ label: 'Item' }],
    });
    expect(service.state()).not.toBeNull();

    service.close();
    expect(service.state()).toBeNull();
  });
});

