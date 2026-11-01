import { describe, it, expect, beforeEach } from 'vitest';
import { ComponentFixture, TestBed } from '@angular/core/testing';
import { MarqueeTextComponent } from './marquee-text.component';

describe('MarqueeTextComponent', () => {
  let component: MarqueeTextComponent;
  let fixture: ComponentFixture<MarqueeTextComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [MarqueeTextComponent],
    }).compileComponents();

    fixture = TestBed.createComponent(MarqueeTextComponent);
    component = fixture.componentInstance;
    fixture.componentRef.setInput('text', 'Test Track Title');
    fixture.detectChanges();
  });

  it('should create the marquee text component', () => {
    expect(component).toBeTruthy();
  });

  it('should render the provided text', () => {
    const el: HTMLElement = fixture.nativeElement;
    expect(el.textContent?.trim()).toBe('Test Track Title');
  });

  it('should stay non-overflowing when content fits within container', () => {
    component.isOverflowing.set(false);
    fixture.detectChanges();

    const container = fixture.nativeElement.querySelector('div');
    expect(container.classList.contains('mask-fade')).toBe(false);
    expect(component.overflowDistance()).toBe(0);
    expect(component.animationDuration()).toBe('0s');
  });

  it('should enable marquee bounce animation and mask when overflowing', () => {
    component.overflowDistance.set(60);
    component.isOverflowing.set(true);
    fixture.detectChanges();

    const container = fixture.nativeElement.querySelector('div');
    expect(container.classList.contains('mask-fade')).toBe(true);

    const content = fixture.nativeElement.querySelector('.animate-marquee-bounce');
    expect(content).toBeTruthy();
    expect(parseFloat(component.animationDuration())).toBeGreaterThan(5);
  });
});

