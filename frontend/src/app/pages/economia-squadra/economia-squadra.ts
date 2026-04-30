import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { LeagueApi } from '../../services/league.api';
import { TeamSessionService } from '../../services/team-session.service';
import {
  BalanceEntryDraft,
  BalanceGuidedField,
  BalanceStadiumOption,
  GuidedBalance,
  TeamDashboard,
} from '../../models/league.model';

@Component({
  selector: 'app-economia-squadra',
  standalone: true,
  imports: [CommonModule, FormsModule, RouterLink],
  templateUrl: './economia-squadra.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class EconomiaSquadraComponent {
  private readonly api = inject(LeagueApi);
  readonly session = inject(TeamSessionService);

  dashboard = signal<TeamDashboard | null>(null);
  guidedBalance = signal<GuidedBalance | null>(null);
  guidedFields = signal<BalanceGuidedField[]>([]);
  autoEntries = signal<BalanceEntryDraft[]>([]);
  extraManualEntries = signal<BalanceEntryDraft[]>([]);
  stadiums = signal<BalanceStadiumOption[]>([]);
  selectedStadiumId = signal('');
  saving = signal(false);
  error = signal<string | null>(null);
  message = signal<string | null>(null);

  readonly canEditEconomy = computed(() => this.guidedBalance()?.balance.status === 'draft');
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
    if (this.session.isLoggedIn()) {
      this.load();
    }
  }

  load() {
    this.error.set(null);
    this.api.getTeamDashboard().subscribe({
      next: (dashboard) => {
        this.dashboard.set(dashboard);
        this.session.updateTeam(dashboard.team);
        this.loadEconomyArea(dashboard.current_season?.id ?? undefined);
      },
      error: (error) => {
        this.error.set(error?.error?.detail ?? 'Errore caricamento area economica');
      },
    });
  }

  loadEconomyArea(seasonId?: string) {
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
        this.error.set(error?.error?.detail ?? 'Errore caricamento area economica');
      },
    });
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

    this.saving.set(true);
    this.error.set(null);
    this.api.updateBalanceDraft(balance.id, this.compileEconomyEntries()).subscribe({
      next: () => {
        this.saving.set(false);
        this.message.set('Area economica aggiornata');
        this.load();
      },
      error: (error) => {
        this.saving.set(false);
        this.error.set(error?.error?.detail ?? 'Errore salvataggio area economica');
      },
    });
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
