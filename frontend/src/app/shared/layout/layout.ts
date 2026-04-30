import {
  Component,
  signal,
  computed,
  OnInit,
  OnDestroy,
  ChangeDetectionStrategy,
  inject,
} from '@angular/core';
import { ActivatedRoute, NavigationEnd, Router, RouterLink, RouterOutlet } from '@angular/router';
import { filter } from 'rxjs/operators';
import { SidebarComponent } from '../sidebar/sidebar';
import { AdminTokenService } from '../../services/admin-token.service';
import { TeamSessionService } from '../../services/team-session.service';

interface PageMeta {
  title: string;
  subtitle?: string;
}

@Component({
  selector: 'app-layout',
  imports: [RouterOutlet, RouterLink, SidebarComponent],
  templateUrl: './layout.html',
  styleUrl: './layout.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class LayoutComponent implements OnInit, OnDestroy {
  isSidebarOpen = signal(false);
  isMobile = signal(false);
  pageMeta = signal<PageMeta>({ title: 'CENA MASKIA CHAMPIONSHIP' });

  showOverlay = computed(() => this.isSidebarOpen() && this.isMobile());

  readonly admin = inject(AdminTokenService);
  readonly teamSession = inject(TeamSessionService);
  private readonly router = inject(Router);
  private readonly route = inject(ActivatedRoute);

  private resizeObserver?: ResizeObserver;

  ngOnInit() {
    this.checkScreenSize();
    this.initializeResizeObserver();
    this.router.events
      .pipe(filter((e) => e instanceof NavigationEnd))
      .subscribe(() => this.updatePageMeta());
    this.updatePageMeta();
  }

  ngOnDestroy() {
    this.resizeObserver?.disconnect();
  }

  toggleSidebar() {
    this.isSidebarOpen.update((v) => !v);
  }

  closeSidebar() {
    this.isSidebarOpen.set(false);
  }

  private updatePageMeta() {
    let r = this.route;
    while (r.firstChild) r = r.firstChild;
    const data = r.snapshot.data ?? {};
    this.pageMeta.set({
      title: data['title'] ?? 'CENA MASKIA CHAMPIONSHIP',
      subtitle: data['subtitle'],
    });
  }

  private checkScreenSize() {
    if (typeof window !== 'undefined') {
      const mobile = window.innerWidth < 768;
      this.isMobile.set(mobile);
      if (mobile) this.isSidebarOpen.set(false);
    }
  }

  private initializeResizeObserver() {
    if (typeof window === 'undefined' || !('ResizeObserver' in window)) return;
    this.resizeObserver = new ResizeObserver((entries) => {
      for (const entry of entries) {
        const mobile = entry.contentRect.width < 768;
        this.isMobile.set(mobile);
        if (mobile && this.isSidebarOpen()) {
          this.isSidebarOpen.set(false);
        }
      }
    });
    this.resizeObserver.observe(document.body);
  }
}
