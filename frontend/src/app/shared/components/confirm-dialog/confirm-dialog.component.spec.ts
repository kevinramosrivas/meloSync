import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ConfirmDialogComponent } from './confirm-dialog.component';
import { ConfirmDialogService } from '../../../core/services/confirm-dialog.service';

describe('ConfirmDialogComponent', () => {
  let component: ConfirmDialogComponent;
  let fixture: ComponentFixture<ConfirmDialogComponent>;
  let service: ConfirmDialogService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ConfirmDialogComponent],
      providers: [ConfirmDialogService],
    }).compileComponents();

    fixture = TestBed.createComponent(ConfirmDialogComponent);
    component = fixture.componentInstance;
    service = TestBed.inject(ConfirmDialogService);
    fixture.detectChanges();
  });

  it('should not render anything when state is null', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role="alertdialog"]')).toBeNull();
  });

  it('should render dialog when opened', () => {
    service.confirm({
      title: 'Eliminar pista',
      message: '¿Estás seguro?',
      danger: true,
    });
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('[role="alertdialog"]')).not.toBeNull();
    expect(el.textContent).toContain('Eliminar pista');
    expect(el.textContent).toContain('¿Estás seguro?');
  });

  it('should trigger cancel when cancel button is clicked', () => {
    const closeSpy = vi.spyOn(service, 'close');
    service.confirm({
      title: 'Test',
      message: 'Desc',
    });
    fixture.detectChanges();

    component.onCancel();
    expect(closeSpy).toHaveBeenCalledWith(false);
  });

  it('should trigger confirm when confirm button is clicked', () => {
    const closeSpy = vi.spyOn(service, 'close');
    service.confirm({
      title: 'Test',
      message: 'Desc',
    });
    fixture.detectChanges();

    component.onConfirm();
    expect(closeSpy).toHaveBeenCalledWith(true);
  });
});

