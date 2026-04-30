import { Component, computed, input, output, ChangeDetectionStrategy, inject } from '@angular/core';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AdminTokenService } from '../../services/admin-token.service';
import { TeamSessionService } from '../../services/team-session.service';

interface NavItem {
  name: string;
  route: string;
  icon: string; // svg path d
}

interface NavGroup {
  label: string;
  items: NavItem[];
}

@Component({
  selector: 'app-sidebar',
  imports: [RouterLink, RouterLinkActive],
  templateUrl: './sidebar.html',
  styleUrl: './sidebar.css',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SidebarComponent {
  private readonly publicNavGroups: NavGroup[] = [
    {
      label: 'Lega',
      items: [
        { name: 'Home', route: '/', icon: 'M3 12l9-9 9 9M5 10v10h4v-6h6v6h4V10' },
        {
          name: 'Regolamento',
          route: '/regolamento',
          icon: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4zm3 4h8M8 12h8M8 16h5',
        },
        {
          name: 'Bacheca',
          route: '/bacheca',
          icon: 'M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-4 4v-4H5a2 2 0 0 1-2-2V5z',
        },
        {
          name: 'Calendario',
          route: '/calendario',
          icon: 'M8 2v3M16 2v3M4 7h16M5 4h14a1 1 0 0 1 1 1v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z',
        },
      ],
    },
    {
      label: 'Panoramica',
      items: [
        {
          name: "Albo d'oro",
          route: '/albo-doro',
          icon: 'M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4zM5 4H2v3a4 4 0 0 0 4 4M19 4h3v3a4 4 0 0 1-4 4',
        },
      ],
    },
  ];

  private readonly teamNavGroups: NavGroup[] = [
    {
      label: 'La Mia Squadra',
      items: [
        { name: 'Home', route: '/', icon: 'M3 12l9-9 9 9M5 10v10h4v-6h6v6h4V10' },
        {
          name: 'Profilo squadra',
          route: '/profilo-squadra',
          icon: 'M12 12a5 5 0 1 0-5-5 5 5 0 0 0 5 5zm0 2c-4.4 0-8 2-8 4.5V21h16v-2.5C20 16 16.4 14 12 14z',
        },
        {
          name: 'Rose',
          route: '/rose',
          icon: 'M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
        },
        {
          name: 'Economia squadra',
          route: '/economia-squadra',
          icon: 'M4 17l6-6 4 4 6-8M4 7h6M4 12h3M4 22h16',
        },
        { name: 'Bilanci', route: '/bilanci', icon: 'M3 3v18h18M7 14l3-3 3 3 5-5' },
        {
          name: 'Mercato',
          route: '/mercato',
          icon: 'M3 3h2l3 12h11l3-8H6M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm10 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
        },
      ],
    },
    {
      label: 'Lega',
      items: [
        {
          name: 'Bacheca',
          route: '/bacheca',
          icon: 'M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-4 4v-4H5a2 2 0 0 1-2-2V5z',
        },
        {
          name: 'Calendario',
          route: '/calendario',
          icon: 'M8 2v3M16 2v3M4 7h16M5 4h14a1 1 0 0 1 1 1v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z',
        },
        {
          name: "Albo d'oro",
          route: '/albo-doro',
          icon: 'M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4zM5 4H2v3a4 4 0 0 0 4 4M19 4h3v3a4 4 0 0 1-4 4',
        },
        {
          name: 'Regolamento',
          route: '/regolamento',
          icon: 'M5 4h11a3 3 0 0 1 3 3v13H8a3 3 0 0 1-3-3V4zm3 4h8M8 12h8M8 16h5',
        },
      ],
    },
  ];

  private readonly adminNavGroups: NavGroup[] = [
    {
      label: 'Gestione',
      items: [
        {
          name: 'Admin',
          route: '/admin',
          icon: 'M4 11h16v10H4zM8 11V7a4 4 0 0 1 8 0v4',
        },
        {
          name: 'Rose',
          route: '/rose',
          icon: 'M17 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2M9 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM23 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75',
        },
        { name: 'Bilanci', route: '/bilanci', icon: 'M3 3v18h18M7 14l3-3 3 3 5-5' },
        {
          name: 'Mercato',
          route: '/mercato',
          icon: 'M3 3h2l3 12h11l3-8H6M9 21a1 1 0 1 0 0-2 1 1 0 0 0 0 2zm10 0a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
        },
        {
          name: 'Cassa comune',
          route: '/cassa',
          icon: 'M3 7h18v12H3zM3 7l3-4h12l3 4M8 12h8',
        },
      ],
    },
    {
      label: 'Lega',
      items: [
        {
          name: 'Bacheca',
          route: '/bacheca',
          icon: 'M3 5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2h-7l-4 4v-4H5a2 2 0 0 1-2-2V5z',
        },
        {
          name: 'Calendario',
          route: '/calendario',
          icon: 'M8 2v3M16 2v3M4 7h16M5 4h14a1 1 0 0 1 1 1v14a2 2 0 0 1-2 2H6a2 2 0 0 1-2-2V5a1 1 0 0 1 1-1z',
        },
        {
          name: "Albo d'oro",
          route: '/albo-doro',
          icon: 'M8 21h8M12 17v4M7 4h10v5a5 5 0 0 1-10 0V4zM5 4H2v3a4 4 0 0 0 4 4M19 4h3v3a4 4 0 0 1-4 4',
        },
      ],
    },
  ];

  isOpen = input<boolean>(false);
  isMobile = input<boolean>(false);

  closeSidebar = output<void>();

  readonly admin = inject(AdminTokenService);
  readonly teamSession = inject(TeamSessionService);

  readonly navGroups = computed<NavGroup[]>(() => {
    if (this.admin.isAdmin()) return this.adminNavGroups;
    if (this.teamSession.isLoggedIn()) return this.teamNavGroups;
    return this.publicNavGroups;
  });

  showSidebar = computed(() => !this.isMobile() || this.isOpen());

  onNavClick() {
    this.closeSidebar.emit();
  }

  logoutAdmin() {
    this.admin.clear();
  }

  logoutTeam() {
    this.teamSession.clear();
  }
}
