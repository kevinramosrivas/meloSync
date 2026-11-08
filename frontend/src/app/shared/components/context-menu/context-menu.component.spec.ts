import { ComponentFixture, TestBed } from '@angular/core/testing';
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ContextMenuComponent } from './context-menu.component';
import { ContextMenuService } from '../../../core/services/context-menu.service';

describe('ContextMenuComponent', () => {
  let component: ContextMenuComponent;
  let fixture: ComponentFixture<ContextMenuComponent>;
  let service: ContextMenuService;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ContextMenuComponent],
      providers: [ContextMenuService],
    }).compileComponents();

    fixture = TestBed.createComponent(ContextMenuComponent);
    component = fixture.componentInstance;
    service = TestBed.inject(ContextMenuService);
    fixture.detectChanges();
  });

  it('should not render anything when state is null', () => {
    const el = fixture.nativeElement as HTMLElement;
    expect(el.querySelector('.fixed')).toBeNull();
  });

  it('should render items when opened', () => {
    service.open({
      x: 100,
      y: 100,
      items: [
        { label: 'Reproducir', icon: 'play' },
        { separator: true },
        { label: 'Eliminar', icon: 'trash', danger: true },
      ],
    });
    fixture.detectChanges();

    const el = fixture.nativeElement as HTMLElement;
    expect(el.textContent).toContain('Reproducir');
    expect(el.textContent).toContain('Eliminar');
  });

  it('should execute action and close menu when item clicked', () => {
    const actionSpy = vi.fn();
    service.open({
      x: 100,
      y: 100,
      items: [{ label: 'Acción', action: actionSpy }],
    });
    fixture.detectChanges();

    component.onItemClick({ label: 'Acción', action: actionSpy });
    expect(actionSpy).toHaveBeenCalled();
    expect(service.state()).toBeNull();
  });
});

