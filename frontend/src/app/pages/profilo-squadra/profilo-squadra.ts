import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { LeagueApi } from '../../services/league.api';
import { TeamSessionService } from '../../services/team-session.service';
import {
  BalanceEntryDraft,
  BalanceGuidedField,
  BalanceStadiumOption,
  GuidedBalance,
  TeamAccount,
  TeamDashboard,
} from '../../models/league.model';

@Component({
  selector: 'app-profilo-squadra',
  imports: [CommonModule, DatePipe, FormsModule, RouterLink],
  templateUrl: './profilo-squadra.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class ProfiloSquadraComponent {
  private readonly api = inject(LeagueApi);
  readonly session = inject(TeamSessionService);

  teams = signal<TeamAccount[]>([]);
  password = signal('');
  selectedTeamId = signal<string | null>(null);
  loginLoading = signal(false);
  loginError = signal<string | null>(null);
  dashboard = signal<TeamDashboard | null>(null);
  guidedBalance = signal<GuidedBalance | null>(null);
  saving = signal(false);
  financeSaving = signal(false);
  financeError = signal<string | null>(null);
  uploadError = signal<string | null>(null);
  uploadFile = signal<File | null>(null);
  message = signal<string | null>(null);
  guidedFields = signal<BalanceGuidedField[]>([]);
  autoEntries = signal<BalanceEntryDraft[]>([]);
  extraManualEntries = signal<BalanceEntryDraft[]>([]);
  stadiums = signal<BalanceStadiumOption[]>([]);
  selectedStadiumId = signal('');

  profileForm = signal({
    manager_name: '',
    logo_url: '',
    founded_year: '',
    profile_bio: '',
    home_city: '',
  });

  readonly canUpload = computed(() => !!this.dashboard()?.current_season);
  readonly canEditEconomy = computed(() => this.guidedBalance()?.balance.status === 'draft');
  readonly selectedTeam = computed(
    () => this.teams().find((team) => team.id === this.selectedTeamId()) ?? null,
  );
  readonly selectedStadium = computed(
    () => this.stadiums().find((stadium) => stadium.id === this.selectedStadiumId()) ?? null,
  );
  readonly sponsorField = computed(
    () =>
      this.guidedFields().find((field) => String(field.meta?.['kind'] ?? '') === 'sponsor') ?? null,
  );
  readonly premiField = computed(
    () =>
      this.guidedFields().find((field) => String(field.meta?.['kind'] ?? '') === 'premi') ?? null,
  );
  readonly capitaleField = computed(
    () =>
      this.guidedFields().find(
        (field) => String(field.meta?.['kind'] ?? '') === 'capitale_sociale',
      ) ?? null,
  );
  readonly orderedHonors = computed(() =>
    [...(this.dashboard()?.honors ?? [])].sort((left, right) => {
      if (left.season_id === right.season_id) {
        return (left.position ?? 99) - (right.position ?? 99);
      }
      return right.season_id.localeCompare(left.season_id);
    }),
  );

  constructor() {
    this.api.listTeams().subscribe((t) => this.teams.set(t));
    if (this.session.isLoggedIn()) {
      this.loadDashboard();
    }
  }

  selectTeam(team: TeamAccount) {
    this.selectedTeamId.set(team.id);
    this.password.set('');
    this.loginError.set(null);
  }

  loginSelectedTeam() {
    const team = this.selectedTeam();
    if (!team) {
      this.loginError.set('Seleziona una squadra');
      return;
    }

    const password = this.password().trim();
    if (!password) {
      this.loginError.set('Inserisci la password della squadra');
      return;
    }

    this.loginLoading.set(true);
    this.loginError.set(null);
    this.api.teamLogin(team.account_username, password).subscribe({
      next: (response) => {
        this.session.setSession(response.access_token, response.team);
        this.loginLoading.set(false);
        this.password.set('');
        this.selectedTeamId.set(null);
        this.loadDashboard();
      },
      error: () => {
        this.loginLoading.set(false);
        this.loginError.set('Accesso fallito per ' + team.name);
      },
    });
  }

  logout() {
    this.session.clear();
    this.password.set('');
    this.selectedTeamId.set(null);
    this.dashboard.set(null);
    this.guidedBalance.set(null);
    this.guidedFields.set([]);
    this.autoEntries.set([]);
    this.extraManualEntries.set([]);
    this.stadiums.set([]);
    this.selectedStadiumId.set('');
    this.financeError.set(null);
    this.profileForm.set({
      manager_name: '',
      logo_url: '',
      founded_year: '',
      profile_bio: '',
      home_city: '',
    });
  }

  setPassword(value: string) {
    this.password.set(value);
  }

  clearSelectedTeam() {
    this.selectedTeamId.set(null);
    this.password.set('');
    this.loginError.set(null);
  }

  isSelectedTeam(teamId: string): boolean {
    return this.selectedTeamId() === teamId;
  }

  loadDashboard() {
    this.api.getTeamDashboard().subscribe((dashboard) => {
      this.dashboard.set(dashboard);
      this.session.updateTeam(dashboard.team);
      this.profileForm.set({
        manager_name: dashboard.team.manager_name ?? '',
        logo_url: dashboard.team.logo_url ?? '',
        founded_year: dashboard.team.founded_year?.toString() ?? '',
        profile_bio: dashboard.team.profile_bio ?? '',
        home_city: dashboard.team.home_city ?? '',
      });
      this.loadEconomyArea(dashboard.current_season?.id ?? undefined);
    });
  }

  loadEconomyArea(seasonId?: string) {
    this.financeError.set(null);
    this.api.getMyGuidedBalance(seasonId).subscribe({
      next: (payload) => {
        this.guidedBalance.set(payload);
        this.guidedFields.set(
          payload.guided_fields.map((field) => ({ ...field, meta: field.meta ?? null })),
        );
        this.autoEntries.set(
          payload.auto_entries
            .map((entry) => ({ ...entry, meta: entry.meta ?? null }))
            .filter(
              (entry) =>
                !['stadium_revenue', 'stadium_cost'].includes(String(entry.meta?.['kind'] ?? '')),
            ),
        );
        this.extraManualEntries.set(
          payload.extra_manual_entries.map((entry) => ({ ...entry, meta: entry.meta ?? null })),
        );
        this.stadiums.set(payload.stadiums);
        this.selectedStadiumId.set(payload.selected_stadium_id ?? '');
      },
      error: (error) => {
        this.guidedBalance.set(null);
        this.financeError.set(error?.error?.detail ?? 'Errore caricamento area economica');
      },
    });
  }

  saveProfile() {
    this.saving.set(true);
    const form = this.profileForm();
    this.api
      .updateTeamMe({
        manager_name: form.manager_name || null,
        logo_url: form.logo_url || null,
        founded_year: form.founded_year ? Number(form.founded_year) : null,
        profile_bio: form.profile_bio || null,
        home_city: form.home_city || null,
      })
      .subscribe({
        next: (team) => {
          this.session.updateTeam(team);
          this.message.set('Profilo aggiornato');
          this.saving.set(false);
          this.loadDashboard();
        },
        error: () => {
          this.message.set('Errore durante il salvataggio');
          this.saving.set(false);
        },
      });
  }

  setField(field: keyof ReturnType<ProfiloSquadraComponent['profileForm']>, value: string) {
    this.profileForm.update((current) => ({ ...current, [field]: value }));
  }

  onFile(event: Event) {
    const file = (event.target as HTMLInputElement).files?.[0] ?? null;
    this.uploadFile.set(file);
  }

  updateGuidedAmount(kind: 'sponsor' | 'premi', value: string) {
    const amount = Number(value);
    this.guidedFields.update((fields) =>
      fields.map((field) =>
        String(field.meta?.['kind'] ?? '') === kind
          ? { ...field, amount: Number.isFinite(amount) ? amount : 0 }
          : field,
      ),
    );
  }

  selectStadium(stadiumId: string) {
    this.selectedStadiumId.set(stadiumId);
  }

  saveEconomyArea() {
    const balance = this.guidedBalance()?.balance;
    if (!balance || !this.canEditEconomy()) return;

    this.financeSaving.set(true);
    this.financeError.set(null);
    this.api.updateBalanceDraft(balance.id, this.compileEconomyEntries()).subscribe({
      next: () => {
        this.financeSaving.set(false);
        this.message.set('Area economica aggiornata');
        this.loadDashboard();
      },
      error: (error) => {
        this.financeSaving.set(false);
        this.financeError.set(error?.error?.detail ?? 'Errore salvataggio area economica');
      },
    });
  }

  uploadBalance() {
    const seasonId = this.dashboard()?.current_season?.id;
    const file = this.uploadFile();
    if (!seasonId || !file) {
      this.uploadError.set('Seleziona un file Excel da caricare');
      return;
    }
    this.uploadError.set(null);
    this.api.importMyBalance(seasonId, file).subscribe({
      next: () => {
        this.uploadFile.set(null);
        this.message.set('Bilancio caricato correttamente');
        this.loadDashboard();
      },
      error: (err) => {
        this.uploadError.set(err?.error?.detail ?? 'Upload non riuscito');
      },
    });
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

  private compileEconomyEntries(): BalanceEntryDraft[] {
    const stadium = this.selectedStadium();
    const stadiumEntries: BalanceEntryDraft[] = stadium
      ? [
          {
            section: 'ricavi',
            label: `Ricavi stadio · ${stadium.name}`,
            amount: stadium.revenue,
            meta: { kind: 'stadium_revenue', auto: true, guided: true, stadium_id: stadium.id },
          },
          {
            section: 'costi',
            label: `Costi stadio · ${stadium.name}`,
            amount: stadium.cost,
            meta: { kind: 'stadium_cost', auto: true, guided: true, stadium_id: stadium.id },
          },
        ]
      : [];

    return [
      ...this.guidedFields().map((field) => ({
        section: field.section,
        label: field.label,
        amount: field.amount,
        meta: field.meta ?? null,
      })),
      ...this.extraManualEntries(),
      ...this.autoEntries(),
      ...stadiumEntries,
    ];
  }
}
