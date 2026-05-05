import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
  computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Router } from '@angular/router';
import { LeagueApi, LeagueAssetUploadKind } from '../../services/league.api';
import { AdminTokenService } from '../../services/admin-token.service';
import {
  BalanceEntry,
  BalanceEntryDraft,
  BalanceGuidedField,
  BalanceIssue,
  BalanceSheet,
  BalanceStadiumOption,
  GuidedBalance,
  Season,
  Team,
  TeamAdminStatus,
} from '../../models/league.model';

const ROLE_ORDER = ['P', 'D', 'C', 'A', 'ALTRO'];

type UploadCard = {
  kind: LeagueAssetUploadKind;
  title: string;
  description: string;
  uploadLabel?: string;
  refreshLabel?: string;
  note?: string;
};

const UPLOAD_CARDS: UploadCard[] = [
  {
    kind: 'rose',
    title: 'Rose',
    description: 'Le rose si importano solo da file Excel, come nel flusso originario.',
    uploadLabel: 'Carica Excel rose',
  },
  {
    kind: 'calendar',
    title: 'Calendario',
    description:
      'Importa prima lo storico da Excel, poi aggiorna solo l’ultima giornata dalla home pubblica della lega.',
    uploadLabel: 'Carica storico Excel',
    refreshLabel: 'Aggiorna ultima giornata',
  },
  {
    kind: 'classifica',
    title: 'Classifica',
    description:
      'Aggiornamento manuale disponibile sempre. Inoltre viene aggiornata automaticamente ogni martedi alle 01:00.',
    refreshLabel: 'Aggiorna classifica',
  },
];

@Component({
  selector: 'app-admin',
  imports: [CommonModule, FormsModule],
  templateUrl: './admin.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  readonly admin = inject(AdminTokenService);

  // Login
  password = signal('');
  loginError = signal<string | null>(null);

  // Data
  seasons = signal<Season[]>([]);
  teams = signal<Team[]>([]);
  teamStatuses = signal<TeamAdminStatus[]>([]);
  balances = signal<BalanceSheet[]>([]);
  balanceSeasonId = signal('');
  balanceLoading = signal(false);
  balanceError = signal<string | null>(null);
  balanceMessage = signal<string | null>(null);
  message = signal<string | null>(null);
  uploadError = signal<string | null>(null);
  uploadingKind = signal<LeagueAssetUploadKind | null>(null);
  readonly uploadCards = UPLOAD_CARDS;

  ngOnInit() {
    if (this.admin.isAdmin()) this.loadData();
  }

  loadData() {
    this.api.listSeasons().subscribe((s) => {
      this.seasons.set(s);
      if (!this.balanceSeasonId()) {
        this.balanceSeasonId.set((s.find((season) => season.is_current) ?? s[0])?.id ?? '');
      }
      this.loadBalances();
    });
    this.api.listTeams().subscribe((t) => this.teams.set(t));
    this.api.getAdminTeamStatuses().subscribe((rows) => this.teamStatuses.set(rows));
  }

  loadBalances() {
    if (!this.admin.isAdmin()) return;
    this.balanceLoading.set(true);
    this.balanceError.set(null);
    this.api.listBalances(this.balanceSeasonId() || undefined).subscribe({
      next: (balances) => {
        this.balances.set(balances);
        this.balanceLoading.set(false);
      },
      error: (error) => {
        this.balanceError.set(error?.error?.detail ?? 'Errore caricamento bilanci');
        this.balanceLoading.set(false);
      },
    });
  }

  login() {
    const token = this.password().trim();
    if (!token) {
      this.loginError.set('Inserisci la password admin');
      return;
    }

    this.admin.set(token);
    this.api.verifyAdmin().subscribe({
      next: () => {
        this.loginError.set(null);
        this.password.set('');
        this.loadData();
      },
      error: () => {
        this.admin.clear();
        this.loginError.set('Accesso admin non riuscito');
      },
    });
  }

  logout() {
    this.admin.clear();
    this.password.set('');
  }

  notify(m: string) {
    this.message.set(m);
    setTimeout(() => this.message.set(null), 3000);
  }

  isUploading(kind: LeagueAssetUploadKind): boolean {
    return this.uploadingKind() === kind;
  }

  onAssetFileSelected(event: Event, kind: LeagueAssetUploadKind) {
    const input = event.target as HTMLInputElement;
    const file = input.files?.[0];
    if (!file) {
      return;
    }

    this.uploadAsset(kind, file);
    input.value = '';
  }

  uploadAsset(kind: LeagueAssetUploadKind, file: File) {
    this.uploadError.set(null);
    this.uploadingKind.set(kind);

    this.api.uploadLeagueAsset(kind, file).subscribe({
      next: (response) => {
        this.uploadingKind.set(null);
        this.notify(`${this.assetLabel(kind)} importato da Excel (${response.imported})`);
      },
      error: (error) => {
        this.uploadingKind.set(null);
        this.uploadError.set(
          error?.error?.detail ?? `Errore upload ${this.assetLabel(kind).toLowerCase()}`,
        );
      },
    });
  }

  refreshAsset(kind: LeagueAssetUploadKind) {
    this.uploadError.set(null);
    this.uploadingKind.set(kind);

    this.api.refreshLeagueAsset(kind).subscribe({
      next: (response) => {
        this.uploadingKind.set(null);
        const sourceLabel = response.source_kind === 'html' ? 'scraping HTML' : 'download Excel';
        const actionLabel =
          kind === 'calendar'
            ? 'Ultima giornata calendario aggiornata'
            : `${this.assetLabel(kind)} aggiornato con successo`;
        this.notify(`${actionLabel} (${sourceLabel})`);
      },
      error: (error) => {
        this.uploadingKind.set(null);
        this.uploadError.set(
          error?.error?.detail ?? `Errore refresh ${this.assetLabel(kind).toLowerCase()}`,
        );
      },
    });
  }

  assetLabel(kind: LeagueAssetUploadKind): string {
    return this.uploadCards.find((card) => card.kind === kind)?.title ?? kind;
  }

  setPassword(value: string) {
    this.password.set(value);
  }

  onBalanceSeasonChange(value: string) {
    this.balanceSeasonId.set(value);
    this.loadBalances();
  }

  okTeamsCount(): number {
    return this.teamStatuses().filter((row) => row.is_ok).length;
  }

  teamName(id: string): string {
    return this.teams().find((team) => team.id === id)?.name ?? '—';
  }

  seasonName(id: string): string {
    return this.seasons().find((season) => season.id === id)?.name ?? '—';
  }

  sanctionLabel(level: string): string {
    return (
      ({ none: 'OK', light: 'Lieve', medium: 'Media', heavy: 'Grave' } as Record<string, string>)[
        level
      ] ?? level
    );
  }

  sanctionClass(level: string): string {
    return (
      (
        {
          none: 'badge badge-success',
          light: 'badge badge-warning',
          medium: 'badge badge-warning',
          heavy: 'badge badge-danger',
        } as Record<string, string>
      )[level] ?? 'badge badge-neutral'
    );
  }

  sanctionPanelClass(level: string): string {
    return (
      (
        {
          none: 'bg-success-soft border-success/30 text-pitch-dark',
          light: 'bg-warning-soft border-warning/30 text-warning',
          medium: 'bg-warning-soft border-warning/30 text-warning',
          heavy: 'bg-danger-soft border-danger/30 text-danger',
        } as Record<string, string>
      )[level] ?? 'bg-surface-inset border-border text-text'
    );
  }

  balanceStatusLabel(status: string): string {
    return status === 'draft' ? 'Bozza' : 'Consegnato';
  }

  balanceStatusBadgeClass(status: string): string {
    return status === 'draft' ? 'badge badge-warning' : 'badge badge-success';
  }

  balanceStatusPanelClass(status: string): string {
    return status === 'draft'
      ? 'border-warning/30 bg-warning-soft text-warning'
      : 'border-success/30 bg-success-soft text-pitch-dark';
  }

  warningTeamsCount(): number {
    return this.teamStatuses().length - this.okTeamsCount();
  }

  anomalyTeamsCount(): number {
    return this.teamStatuses().filter((row) => row.anomalies?.length > 0).length;
  }

  anomalyBadge(issue: TeamAdminStatus['anomalies'][number]): string {
    return issue.severity === 'critical'
      ? 'badge badge-danger'
      : issue.severity === 'info'
        ? 'badge badge-info'
        : 'badge badge-warning';
  }

  statusBadge(row: TeamAdminStatus): string {
    if (row.anomalies?.some((issue) => issue.severity === 'critical')) {
      return 'badge badge-danger';
    }
    return row.is_ok ? 'badge badge-success' : 'badge badge-warning';
  }

  submittedBalancesCount(): number {
    return this.balances().filter((balance) => balance.status === 'submitted').length;
  }

  draftBalancesCount(): number {
    return this.balances().filter((balance) => balance.status === 'draft').length;
  }

  totalLeagueResult(): number {
    return this.balances().reduce((total, balance) => total + Number(balance.utile ?? 0), 0);
  }
}
