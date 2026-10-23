import { Component } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterOutlet } from '@angular/router';
import { TuiRoot } from '@taiga-ui/core';
import { SidebarComponent } from './shared/components/sidebar/sidebar.component';
import { BottomPlayerComponent } from './shared/components/bottom-player/bottom-player.component';
import { ToastContainerComponent } from './shared/components/toast-container/toast-container.component';

@Component({
  selector: 'app-root',
  imports: [
    CommonModule,
    RouterOutlet,
    TuiRoot,
    SidebarComponent,
    BottomPlayerComponent,
    ToastContainerComponent
  ],
  templateUrl: './app.html'
})
export class App {}
