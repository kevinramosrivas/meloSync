import { describe, it, expect, beforeEach } from 'vitest';
import { ConfirmDialogService } from './confirm-dialog.service';

describe('ConfirmDialogService', () => {
  let service: ConfirmDialogService;

  beforeEach(() => {
    service = new ConfirmDialogService();
  });

  it('should initialize with null state', () => {
    expect(service.state()).toBeNull();
  });

  it('should open confirm dialog and resolve true when closed with true', async () => {
    const promise = service.confirm({
      title: 'Eliminar elemento',
      message: '¿Estás seguro de continuar?',
      danger: true,
    });

    const state = service.state();
    expect(state).not.toBeNull();
    expect(state?.title).toBe('Eliminar elemento');
    expect(state?.confirmText).toBe('Eliminar');
    expect(state?.danger).toBe(true);

    service.close(true);

    const result = await promise;
    expect(result).toBe(true);
    expect(service.state()).toBeNull();
  });

  it('should resolve false when closed with false', async () => {
    const promise = service.confirm({
      title: 'Confirmar acción',
      message: 'Mensaje de prueba',
      danger: false,
    });

    expect(service.state()?.confirmText).toBe('Aceptar');

    service.close(false);

    const result = await promise;
    expect(result).toBe(false);
    expect(service.state()).toBeNull();
  });
});

