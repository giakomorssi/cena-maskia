import { Routes } from '@angular/router';

export const routes: Routes = [
  {
    path: '',
    loadComponent: () => import('./shared/layout/layout').then((m) => m.LayoutComponent),
    children: [
      {
        path: '',
        loadComponent: () => import('./pages/home/home').then((m) => m.HomeComponent),
        title: 'Home',
        data: { title: 'Home' },
      },
      {
        path: 'regolamento',
        loadComponent: () =>
          import('./pages/regolamento/regolamento').then((m) => m.RegolamentoComponent),
        title: 'Regolamento',
        data: { title: 'Regolamento' },
      },
      {
        path: 'bilanci',
        loadComponent: () => import('./pages/bilanci/bilanci').then((m) => m.BilanciComponent),
        title: 'Bilanci',
        data: { title: 'Bilanci' },
      },
      {
        path: 'mercato',
        loadComponent: () => import('./pages/mercato/mercato').then((m) => m.MercatoComponent),
        title: 'Mercato',
        data: { title: 'Mercato' },
      },
      {
        path: 'rose',
        loadComponent: () => import('./pages/rose/rose').then((m) => m.RoseComponent),
        title: 'Rose',
        data: { title: 'Rose' },
      },
      {
        path: 'economia-squadra',
        loadComponent: () =>
          import('./pages/economia-squadra/economia-squadra').then(
            (m) => m.EconomiaSquadraComponent,
          ),
        title: 'Economia squadra',
        data: { title: 'Economia squadra' },
      },
      {
        path: 'albo-doro',
        loadComponent: () => import('./pages/albo-doro/albo-doro').then((m) => m.AlboDoroComponent),
        title: "Albo d'oro",
        data: { title: "Albo d'oro" },
      },
      {
        path: 'calendario',
        loadComponent: () =>
          import('./pages/calendario/calendario').then((m) => m.CalendarioComponent),
        title: 'Calendario e classifica',
        data: { title: 'Calendario e classifica' },
      },
      {
        path: 'cassa',
        loadComponent: () => import('./pages/cassa/cassa').then((m) => m.CassaComponent),
        title: 'Cassa comune',
        data: { title: 'Cassa comune' },
      },
      {
        path: 'bacheca',
        loadComponent: () => import('./pages/bacheca/bacheca').then((m) => m.BachecaComponent),
        title: 'Bacheca',
        data: { title: 'Bacheca' },
      },
      {
        path: 'admin',
        loadComponent: () => import('./pages/admin/admin').then((m) => m.AdminComponent),
        title: 'Admin',
        data: { title: 'Admin' },
      },
      {
        path: 'admin/bilanci/:balanceId',
        loadComponent: () =>
          import('./pages/admin-balance/admin-balance').then((m) => m.AdminBalanceComponent),
        title: 'Bilancio Admin',
        data: { title: 'Bilancio Admin' },
      },
      {
        path: 'profilo-squadra',
        loadComponent: () =>
          import('./pages/profilo-squadra/profilo-squadra').then((m) => m.ProfiloSquadraComponent),
        title: 'Profilo squadra',
        data: { title: 'Profilo squadra' },
      },
    ],
  },
  { path: '**', redirectTo: '' },
];
