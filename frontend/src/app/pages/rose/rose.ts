import { ChangeDetectionStrategy, Component, computed, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LeagueApi } from '../../services/league.api';
import { AdminTokenService } from '../../services/admin-token.service';
import { TeamSessionService } from '../../services/team-session.service';
import {
  Player,
  PlayerAcquisition,
  PlayerCreate,
  PlayerFascia,
  Season,
  Team,
} from '../../models/league.model';
import {
  PlayerDetailData,
  PlayerDetailModalComponent,
} from '../../shared/player-detail-modal/player-detail-modal';

const ACQ: { value: PlayerAcquisition; label: string }[] = [
  { value: 'owned', label: 'Di proprietà' },
  { value: 'loan_dry', label: 'Prestito secco' },
  { value: 'loan_with_right', label: 'Prestito con diritto' },
  { value: 'loan_with_obligation', label: 'Prestito con obbligo' },
  { value: 'sold_definitively', label: 'Venduto definitivamente' },
];

const FASCE: Array<{
  value: PlayerFascia;
  label: string;
  min: number;
  max: number | null;
  salary: number;
}> = [
  { value: '1_9', label: '1-9', min: 1, max: 9, salary: 0.5 },
  { value: '10_19', label: '10-19', min: 10, max: 19, salary: 1 },
  { value: '20_34', label: '20-34', min: 20, max: 34, salary: 2 },
  { value: '35_49', label: '35-49', min: 35, max: 49, salary: 3 },
  { value: '50_69', label: '50-69', min: 50, max: 69, salary: 4.5 },
  { value: '70_89', label: '70-89', min: 70, max: 89, salary: 6 },
  { value: '90_120', label: '90-120', min: 90, max: 120, salary: 8 },
  { value: '120_plus', label: '120+', min: 121, max: null, salary: 10 },
];

const LEGACY_FASCIA_TO_VALUE: Record<string, PlayerFascia> = {
  '1_19': '10_19',
  '20_59': '35_49',
  '60_plus': '90_120',
};

const ROLE_ORDER = ['P', 'B', 'DC', 'DD', 'DS', 'E', 'M', 'C', 'T', 'W', 'A', 'PC'];

type SortColumn =
  | 'name'
  | 'role'
  | 'fascia'
  | 'salary'
  | 'market_value'
  | 'contract'
  | 'acquisition';
type SortDirection = 'asc' | 'desc';

@Component({
  selector: 'app-rose',
  standalone: true,
  imports: [CommonModule, FormsModule, PlayerDetailModalComponent],
  templateUrl: './rose.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class RoseComponent {
  private readonly api = inject(LeagueApi);
  readonly admin = inject(AdminTokenService);
  readonly teamSession = inject(TeamSessionService);

  readonly seasons = signal<Season[]>([]);
  readonly teams = signal<Team[]>([]);
  readonly players = signal<Player[]>([]);
  readonly seasonId = signal<string | null>(null);
  readonly teamId = signal<string | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly search = signal('');
  readonly roleFilter = signal('');
  readonly fasciaFilter = signal('');
  readonly sortColumn = signal<SortColumn>('role');
  readonly sortDirection = signal<SortDirection>('asc');

  readonly editing = signal<Partial<Player> | null>(null);
  readonly creating = signal<PlayerCreate | null>(null);
  readonly playerDetail = signal<PlayerDetailData | null>(null);

  readonly ACQ = ACQ;
  readonly FASCE = FASCE;

  readonly canEdit = computed(() => this.admin.isAdmin());
  readonly currentTeamId = computed(() => this.teamSession.team()?.id ?? null);
  readonly selectedSeasonName = computed(
    () => this.seasons().find((s) => s.id === this.seasonId())?.name ?? null,
  );
  readonly selectedTeamName = computed(() => {
    const tid = this.teamId();
    if (tid) return this.teams().find((t) => t.id === tid)?.name ?? 'Rosa selezionata';
    if (!this.canEdit()) return this.teamSession.team()?.name ?? 'La tua rosa';
    return 'Tutte le squadre';
  });
  readonly roleOptions = computed(() => {
    const values = new Set(this.players().flatMap((p) => this.roleTokens(p.role)));
    return ROLE_ORDER.filter((role) => values.has(role));
  });
  readonly activeFilterCount = computed(() => {
    let count = 0;
    if (this.search().trim()) count += 1;
    if (this.roleFilter()) count += 1;
    if (this.fasciaFilter()) count += 1;
    if (this.canEdit() && this.teamId()) count += 1;
    return count;
  });
  readonly visiblePlayers = computed(() => {
    const query = this.search().trim().toLowerCase();
    const role = this.roleFilter();
    const fascia = this.fasciaFilter();
    return this.players().filter((p) => {
      const matchesQuery =
        !query ||
        p.name.toLowerCase().includes(query) ||
        p.role.toLowerCase().includes(query) ||
        this.acqLabel(p.acquisition_type).toLowerCase().includes(query);
      const matchesRole = !role || this.roleTokens(p.role).includes(role);
      const matchesFascia = !fascia || this.playerFasciaValue(p) === fascia;
      return matchesQuery && matchesRole && matchesFascia;
    });
  });

  readonly summary = computed(() => {
    const list = this.visiblePlayers();
    let totalSalary = 0;
    let totalValue = 0;
    const byFascia: Record<string, number> = {};
    let inactive = 0;
    for (const p of list) {
      if (!p.is_active) {
        inactive += 1;
      } else {
        totalSalary += this.playerSalaryValue(p);
        totalValue += +(p.market_value ?? 0);
        const fascia = this.playerFasciaValue(p);
        byFascia[fascia] = (byFascia[fascia] ?? 0) + 1;
      }
    }
    const count = list.filter((p) => p.is_active).length;
    return {
      count,
      inactive,
      totalSalary,
      totalValue,
      avgSalary: count ? totalSalary / count : 0,
      avgValue: count ? totalValue / count : 0,
      byFascia,
    };
  });
  readonly fasciaBreakdown = computed(() =>
    this.FASCE.map((fascia) => ({
      ...fascia,
      count: this.summary().byFascia[fascia.value] ?? 0,
      ratio: this.summary().count
        ? ((this.summary().byFascia[fascia.value] ?? 0) / this.summary().count) * 100
        : 0,
    })),
  );
  readonly sortedVisiblePlayers = computed(() => {
    const list = [...this.visiblePlayers()];
    const direction = this.sortDirection() === 'asc' ? 1 : -1;
    const column = this.sortColumn();

    return list.sort((left, right) => direction * this.comparePlayers(left, right, column));
  });

  ngOnInit() {
    this.api.listSeasons().subscribe({
      next: (s) => {
        this.seasons.set(s);
        const current = s.find((x) => x.is_current) ?? s[0];
        if (current) this.seasonId.set(current.id);
        this.loadInitial();
      },
      error: () => this.loadInitial(),
    });
    if (this.admin.isAdmin()) {
      this.api.listTeams().subscribe({ next: (t) => this.teams.set(t) });
    } else if (this.teamSession.team()) {
      this.teamId.set(this.teamSession.team()!.id);
    }
  }

  private loadInitial() {
    if (this.admin.isAdmin()) {
      // start by listing all in current season
      this.reload();
    } else if (this.teamSession.team()) {
      this.teamId.set(this.teamSession.team()!.id);
      this.reload();
    }
  }

  reload() {
    const sid = this.seasonId();
    const tid = this.teamId();
    if (!sid) return;
    this.loading.set(true);
    this.error.set(null);
    this.api.listPlayers({ season_id: sid, team_id: tid ?? undefined }).subscribe({
      next: (p) => {
        this.players.set(p);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.detail ?? 'Errore caricamento rosa');
        this.loading.set(false);
      },
    });
  }

  onSeasonChange(id: string) {
    this.seasonId.set(id);
    this.reload();
  }
  onTeamChange(id: string) {
    this.teamId.set(id || null);
    this.reload();
  }
  onSearchChange(value: string) {
    this.search.set(value);
  }
  onRoleFilterChange(value: string) {
    this.roleFilter.set(value);
  }
  onFasciaFilterChange(value: string) {
    this.fasciaFilter.set(value);
  }
  onSortChange(column: SortColumn) {
    if (this.sortColumn() === column) {
      this.sortDirection.set(this.sortDirection() === 'asc' ? 'desc' : 'asc');
      return;
    }
    this.sortColumn.set(column);
    this.sortDirection.set(column === 'role' || column === 'name' ? 'asc' : 'desc');
  }
  resetFilters() {
    this.search.set('');
    this.roleFilter.set('');
    this.fasciaFilter.set('');
    if (this.canEdit()) {
      this.teamId.set(null);
      this.reload();
    }
  }
  normalizeRoleToken(role: string | null | undefined): string {
    const token = String(role ?? '')
      .trim()
      .toUpperCase();
    return token === 'POR' ? 'P' : token;
  }
  roleTokens(role: string | null | undefined): string[] {
    return String(role ?? '')
      .split(';')
      .map((token) => this.normalizeRoleToken(token))
      .filter(Boolean);
  }

  sortIcon(column: SortColumn): string {
    if (this.sortColumn() !== column) return '↕';
    return this.sortDirection() === 'asc' ? '↑' : '↓';
  }

  isSortedBy(column: SortColumn): boolean {
    return this.sortColumn() === column;
  }

  startCreate() {
    const sid = this.seasonId();
    const tid = this.teamId() ?? this.teams()[0]?.id ?? '';
    if (!sid || !tid) return;
    this.creating.set({
      team_id: tid,
      season_id: sid,
      name: '',
      role: 'A',
      fascia: '20_34',
      salary: 0,
      market_value: 0,
      contract_years_total: 1,
      contract_years_remaining: 1,
      acquisition_type: 'owned',
    });
  }
  cancelCreate() {
    this.creating.set(null);
  }
  saveCreate() {
    const c = this.creating();
    if (!c) return;
    this.api.createPlayer(c as PlayerCreate).subscribe({
      next: () => {
        this.creating.set(null);
        this.reload();
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore creazione'),
    });
  }

  startEdit(p: Player) {
    this.editing.set({ ...p });
  }
  openPlayerDetail(player: Player) {
    this.playerDetail.set({
      playerName: player.name,
      ownerTeamName: this.playerOwnerName(player),
      role: this.roleTokens(player.role).join(' · '),
      contractType: this.acqLabel(player.acquisition_type),
      marketValue: Number(player.market_value ?? 0),
      salary: this.playerSalaryValue(player),
      fascia: this.fasciaLabel(this.playerFasciaValue(player)),
      contractYearsTotal: Number(player.contract_years_total ?? 0),
      contractYearsRemaining: Number(player.contract_years_remaining ?? 0),
    });
  }
  closePlayerDetail() {
    this.playerDetail.set(null);
  }
  cancelEdit() {
    this.editing.set(null);
  }
  saveEdit() {
    const e = this.editing();
    if (!e?.id) return;
    this.api.updatePlayer(e.id, e).subscribe({
      next: () => {
        this.editing.set(null);
        this.reload();
      },
      error: (err) => this.error.set(err?.error?.detail ?? 'Errore aggiornamento'),
    });
  }

  fasciaForValue(value: number | null | undefined): PlayerFascia {
    const numericValue = Number(value ?? 0);
    return (this.FASCE.find(
      (fascia) => numericValue >= fascia.min && (fascia.max === null || numericValue <= fascia.max),
    )?.value ?? '1_9') as PlayerFascia;
  }

  salaryForValue(value: number | null | undefined): number {
    const numericValue = Number(value ?? 0);
    return (
      this.FASCE.find(
        (fascia) =>
          numericValue >= fascia.min && (fascia.max === null || numericValue <= fascia.max),
      )?.salary ?? 0.5
    );
  }

  playerFasciaValue(player: Pick<Player, 'fascia' | 'market_value'>): string {
    const marketValue = Number(player.market_value ?? 0);
    if (marketValue > 0) {
      return this.fasciaForValue(marketValue);
    }

    const rawFascia = String(player.fascia ?? '').trim();
    if (this.FASCE.some((fascia) => fascia.value === rawFascia)) {
      return rawFascia;
    }
    if (rawFascia in LEGACY_FASCIA_TO_VALUE) {
      return LEGACY_FASCIA_TO_VALUE[rawFascia];
    }
    return this.fasciaForValue(player.market_value);
  }

  playerSalaryValue(player: Pick<Player, 'salary' | 'market_value'>): number {
    const marketValue = Number(player.market_value ?? 0);
    if (marketValue > 0) {
      return this.salaryForValue(marketValue);
    }
    return Number(player.salary ?? 0);
  }

  onCreateValueChange(value: number | string) {
    const current = this.creating();
    if (!current) return;
    const marketValue = Number(value || 0);
    this.creating.set({
      ...current,
      market_value: marketValue,
      fascia: this.fasciaForValue(marketValue),
      salary: this.salaryForValue(marketValue),
    });
  }

  onEditValueChange(value: number | string) {
    const current = this.editing();
    if (!current) return;
    const marketValue = Number(value || 0);
    this.editing.set({
      ...current,
      market_value: marketValue,
      fascia: this.fasciaForValue(marketValue),
      salary: this.salaryForValue(marketValue),
    });
  }

  remove(p: Player) {
    if (!confirm(`Eliminare ${p.name}?`)) return;
    this.api.deletePlayer(p.id).subscribe({ next: () => this.reload() });
  }

  private comparePlayers(left: Player, right: Player, column: SortColumn): number {
    switch (column) {
      case 'name':
        return this.compareText(left.name, right.name);
      case 'role':
        return this.compareRole(left.role, right.role) || this.compareText(left.name, right.name);
      case 'fascia':
        return (
          this.compareFascia(this.playerFasciaValue(left), this.playerFasciaValue(right)) ||
          this.compareText(left.name, right.name)
        );
      case 'salary':
        return (
          this.compareNumber(this.playerSalaryValue(left), this.playerSalaryValue(right)) ||
          this.compareText(left.name, right.name)
        );
      case 'market_value':
        return (
          this.compareNumber(Number(left.market_value ?? 0), Number(right.market_value ?? 0)) ||
          this.compareText(left.name, right.name)
        );
      case 'contract':
        return (
          this.compareNumber(
            Number(left.contract_years_remaining ?? 0),
            Number(right.contract_years_remaining ?? 0),
          ) || this.compareText(left.name, right.name)
        );
      case 'acquisition':
        return (
          this.compareText(
            this.acqLabel(left.acquisition_type),
            this.acqLabel(right.acquisition_type),
          ) || this.compareText(left.name, right.name)
        );
    }
  }

  private compareRole(leftRole: string, rightRole: string): number {
    const leftIndex = this.primaryRoleIndex(leftRole);
    const rightIndex = this.primaryRoleIndex(rightRole);
    return leftIndex - rightIndex || this.compareText(leftRole, rightRole);
  }

  private compareFascia(leftFascia: string, rightFascia: string): number {
    const leftIndex = this.FASCE.findIndex((fascia) => fascia.value === leftFascia);
    const rightIndex = this.FASCE.findIndex((fascia) => fascia.value === rightFascia);
    return leftIndex - rightIndex;
  }

  private primaryRoleIndex(role: string): number {
    const primaryToken = this.roleTokens(role)[0] ?? '';
    const index = ROLE_ORDER.indexOf(primaryToken);
    return index === -1 ? ROLE_ORDER.length : index;
  }

  private compareText(left: string | null | undefined, right: string | null | undefined): number {
    return String(left ?? '').localeCompare(String(right ?? ''), 'it', { sensitivity: 'base' });
  }

  private compareNumber(left: number, right: number): number {
    return left - right;
  }

  playerOwnerName(player: Player): string {
    if (player.team_id) {
      const foundTeam = this.teams().find((team) => team.id === player.team_id)?.name;
      if (foundTeam) return foundTeam;
      // fallback: if the player belongs to the logged-in team
      const sessionTeam = this.teamSession.team();
      if (sessionTeam && sessionTeam.id === player.team_id) return sessionTeam.name;
    }
    return this.teamSession.team()?.name ?? 'Squadra';
  }

  acqLabel(v: string) {
    return ACQ.find((x) => x.value === v)?.label ?? v;
  }
  fasciaLabel(v: string) {
    const normalizedValue = LEGACY_FASCIA_TO_VALUE[v] ?? v;
    return FASCE.find((x) => x.value === normalizedValue)?.label ?? normalizedValue;
  }
  fasciaBadgeClass(v: string) {
    return (
      (
        {
          '1_9': 'bg-purple-100 text-purple-800 border border-purple-200',
          '10_19': 'bg-fuchsia-100 text-fuchsia-800 border border-fuchsia-200',
          '20_34': 'bg-orange-100 text-orange-800 border border-orange-200',
          '35_49': 'bg-amber-100 text-amber-800 border border-amber-200',
          '50_69': 'bg-lime-100 text-lime-800 border border-lime-200',
          '70_89': 'bg-sky-100 text-sky-800 border border-sky-200',
          '90_120': 'bg-cyan-100 text-cyan-800 border border-cyan-200',
          '120_plus': 'bg-teal-100 text-teal-800 border border-teal-200',
        } as Record<string, string>
      )[v] ?? 'bg-surface-inset text-text border border-border'
    );
  }
  fasciaBarClass(v: string) {
    return (
      (
        {
          '1_9': 'bg-purple-500',
          '10_19': 'bg-fuchsia-500',
          '20_34': 'bg-orange-500',
          '35_49': 'bg-amber-500',
          '50_69': 'bg-lime-500',
          '70_89': 'bg-sky-500',
          '90_120': 'bg-cyan-500',
          '120_plus': 'bg-teal-500',
        } as Record<string, string>
      )[v] ?? 'bg-brand'
    );
  }
  acquisitionBadgeClass(v: string) {
    return (
      (
        {
          owned: 'bg-surface-inset text-text border border-border',
          loan_dry: 'bg-warning-soft text-warning border border-warning/30',
          loan_with_right: 'bg-brand-soft text-pitch border border-brand/20',
          loan_with_obligation: 'bg-accent-soft text-pitch-dark border border-accent/40',
          sold_definitively: 'bg-danger-soft text-danger border border-danger/30',
        } as Record<string, string>
      )[v] ?? 'bg-surface-inset text-text border border-border'
    );
  }
  roleBadgeClass(role: string) {
    const key = this.normalizeRoleToken(role);
    if (['P'].includes(key)) {
      return 'bg-yellow-100 text-yellow-800 border border-yellow-300';
    }
    if (['DC', 'DD', 'DS', 'B'].includes(key)) {
      return 'bg-emerald-100 text-emerald-800 border border-emerald-200';
    }
    if (['E', 'M', 'C', 'T'].includes(key)) {
      return 'bg-blue-100 text-blue-800 border border-blue-200';
    }
    if (['W', 'A', 'PC'].includes(key)) {
      return 'bg-red-100 text-red-800 border border-red-200';
    }
    return 'bg-surface-inset text-text border border-border';
  }
}
