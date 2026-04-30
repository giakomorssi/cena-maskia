import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { FormsModule } from '@angular/forms';
import { RouterLink } from '@angular/router';
import { LeagueApi } from '../../services/league.api';
import { AdminTokenService } from '../../services/admin-token.service';
import { TeamSessionService } from '../../services/team-session.service';
import {
  BalanceGuidedField,
  BalanceIssue,
  BalanceEntry,
  BalanceEntryDraft,
  BalanceSheet,
  BalanceStadiumOption,
  GuidedBalance,
  Season,
  Team,
} from '../../models/league.model';
import { MarkdownPipe } from '../../shared/markdown.pipe';
import { CommonModule, DatePipe } from '@angular/common';
import {
  PlayerDetailData,
  PlayerDetailModalComponent,
} from '../../shared/player-detail-modal/player-detail-modal';

type Tab = 'guida' | 'lista' | 'compila';
type AutoSectionKey = 'ricavi' | 'costi' | 'ammortamenti' | 'plus_minus';

const ROLE_ORDER = ['P', 'D', 'C', 'A', 'ALTRO'];

@Component({
  selector: 'app-bilanci',
  imports: [
    CommonModule,
    DatePipe,
    FormsModule,
    RouterLink,
    MarkdownPipe,
    PlayerDetailModalComponent,
  ],
  templateUrl: './bilanci.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BilanciComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  readonly admin = inject(AdminTokenService);
  readonly teamSession = inject(TeamSessionService);

  tab = signal<Tab>('guida');

  // Guide
  guida = signal<string>('');

  // Data
  seasons = signal<Season[]>([]);
  teams = signal<Team[]>([]);
  balances = signal<BalanceSheet[]>([]);
  selectedSeason = signal<string>('');
  authRequired = signal(false);

  // Selected balance for detail view
  selected = signal<BalanceSheet | null>(null);
  readonly isAdminView = computed(() => this.admin.isAdmin());
  readonly isTeamView = computed(() => this.teamSession.isLoggedIn() && !this.admin.isAdmin());
  readonly hasBalanceAccess = computed(() => this.admin.isAdmin() || this.teamSession.isLoggedIn());
  readonly submissionDeadlineLabel = '15/07';

  // Compila online (draft / submit)
  readonly compileBalance = signal<BalanceSheet | null>(null);
  readonly compileEntries = signal<BalanceEntryDraft[]>([]);
  readonly guidedFields = signal<BalanceGuidedField[]>([]);
  readonly autoEntries = signal<BalanceEntryDraft[]>([]);
  readonly extraManualEntries = signal<BalanceEntryDraft[]>([]);
  readonly stadiums = signal<BalanceStadiumOption[]>([]);
  readonly selectedStadiumId = signal('');
  readonly compileLoading = signal(false);
  readonly compileSaving = signal(false);
  readonly compileError = signal<string | null>(null);
  readonly compileMessage = signal<string | null>(null);
  readonly serverCompileIssues = signal<BalanceIssue[]>([]);
  readonly compileSeasonId = signal<string>('');
  readonly adminEditingBalanceId = signal<string | null>(null);
  readonly playerDetail = signal<PlayerDetailData | null>(null);
  readonly collapsedPublishedGroups = signal<Record<string, boolean>>({});
  readonly collapsedCompileGroups = signal<Record<string, boolean>>({});

  readonly compileTotals = computed(() => {
    let r = 0,
      c = 0,
      a = 0,
      p = 0;
    for (const e of this.compileEntries()) {
      const amt = +(e.amount || 0);
      if (e.section === 'ricavi') r += amt;
      else if (e.section === 'costi') c += amt;
      else if (e.section === 'ammortamenti') a += amt;
      else if (e.section === 'plus_minus') p += amt;
    }
    return { ricavi: r, costi: c, ammortamenti: a, plus_minus: p, utile: r - c - a + p };
  });

  readonly canSubmitDraft = computed(() => {
    const b = this.compileBalance();
    return !!b && b.status === 'draft' && this.canUploadAsTeam();
  });
  readonly compileIssues = computed(() => {
    const derived: BalanceIssue[] = [];
    const warnedCodes = new Set<string>();

    if (!this.selectedStadiumId()) {
      derived.push({
        code: 'stadium_missing',
        label: 'Stadio non selezionato',
        detail: 'Seleziona uno stadio per autocompilare ricavi e costi stadio.',
        severity: 'warning',
      });
      warnedCodes.add('stadium_missing');
    }

    for (const field of this.guidedFields()) {
      const key = String(field.meta?.['kind'] ?? '');
      if (['capitale_sociale', 'sponsor', 'premi'].includes(key) && (field.amount ?? 0) <= 0) {
        derived.push({
          code: `missing_${key}`,
          label: `${field.label} da verificare`,
          detail: `La voce ${field.label} e ancora a zero.`,
          severity: 'warning',
        });
        warnedCodes.add(`missing_${key}`);
      }
    }

    if (this.compileTotals().utile < 0) {
      derived.push({
        code: 'negative_result',
        label: 'Bilancio in perdita',
        detail: 'Il risultato netto e negativo e genera una sanzione automatica.',
        severity: this.compileTotals().utile < -20 ? 'critical' : 'warning',
      });
      warnedCodes.add('negative_result');
    }

    return [
      ...derived,
      ...this.serverCompileIssues().filter((issue) => !warnedCodes.has(issue.code)),
    ];
  });
  readonly autoEntriesBySection = computed(() => {
    const grouped: Record<string, BalanceEntryDraft[]> = {
      ricavi: [],
      costi: [],
      ammortamenti: [],
      plus_minus: [],
    };
    for (const entry of this.effectiveAutoEntries()) {
      const section = entry.section;
      if (!grouped[section]) grouped[section] = [];
      grouped[section].push(entry);
    }
    return grouped;
  });
  readonly autoEntriesBySectionAndRole = computed(() => ({
    ricavi: [{ role: 'Generale', entries: this.autoEntriesBySection()['ricavi'] }],
    costi: this.groupEntriesByRole(this.autoEntriesBySection()['costi']),
    ammortamenti: this.groupEntriesByRole(this.autoEntriesBySection()['ammortamenti']),
    plus_minus: [{ role: 'Generale', entries: this.autoEntriesBySection()['plus_minus'] }],
  }));

  ngOnInit() {
    this.api.getContent('guida-bilancio').subscribe((r) => this.guida.set(r.body_md));
    this.api.listSeasons().subscribe((s) => {
      this.seasons.set(s);
      const cur = s.find((x) => x.is_current) ?? s[0];
      if (cur) {
        this.selectedSeason.set(cur.id);
        this.refreshBalances();
      }
    });
    this.api.listTeams().subscribe((t) => this.teams.set(t));
  }

  setTab(t: Tab) {
    this.tab.set(t);
    this.selected.set(null);
    if (
      t === 'compila' &&
      !this.compileBalance() &&
      (this.canUploadAsTeam() || this.adminEditingBalanceId())
    ) {
      this.loadCompile();
    }
  }

  loadCompile(balanceId?: string) {
    this.compileLoading.set(true);
    this.compileError.set(null);
    this.compileMessage.set(null);
    if (this.admin.isAdmin()) {
      const targetBalanceId = balanceId ?? this.adminEditingBalanceId();
      if (!targetBalanceId) {
        this.compileLoading.set(false);
        return;
      }
      this.adminEditingBalanceId.set(targetBalanceId);
      this.api.getAdminGuidedBalance(targetBalanceId).subscribe({
        next: (payload) => {
          this.applyGuidedPayload(payload);
          this.compileLoading.set(false);
        },
        error: (e) => {
          this.compileError.set(e?.error?.detail ?? 'Errore caricamento bilancio');
          this.compileLoading.set(false);
        },
      });
      return;
    }

    if (!this.canUploadAsTeam()) {
      this.compileLoading.set(false);
      return;
    }

    const sid = this.compileSeasonId() || this.selectedSeason() || undefined;
    this.api.getMyGuidedBalance(sid).subscribe({
      next: (payload) => {
        this.adminEditingBalanceId.set(null);
        this.applyGuidedPayload(payload);
        this.compileLoading.set(false);
      },
      error: (e) => {
        this.compileError.set(e?.error?.detail ?? 'Errore caricamento bozza');
        this.compileLoading.set(false);
      },
    });
  }

  applyGuidedPayload(payload: GuidedBalance) {
    this.compileBalance.set(payload.balance);
    this.compileSeasonId.set(payload.balance.season_id);
    this.guidedFields.set(
      payload.guided_fields.map((field) => ({
        ...field,
        meta: field.meta ?? null,
      })),
    );
    this.autoEntries.set(
      payload.auto_entries
        .map((entry) => ({
          section: entry.section,
          label: entry.label,
          amount: entry.amount,
          meta: entry.meta ?? null,
        }))
        .filter(
          (entry) =>
            !['stadium_revenue', 'stadium_cost'].includes(String(entry.meta?.['kind'] ?? '')),
        ),
    );
    this.extraManualEntries.set(
      payload.extra_manual_entries.map((entry) => ({
        section: entry.section,
        label: entry.label,
        amount: entry.amount,
        meta: entry.meta ?? null,
      })),
    );
    this.stadiums.set(payload.stadiums);
    this.selectedStadiumId.set(payload.selected_stadium_id ?? '');
    this.serverCompileIssues.set(payload.issues);
    this.syncCompileEntries();
  }

  updateGuidedField(key: string, amount: number) {
    this.guidedFields.update((fields) =>
      fields.map((field) =>
        String(field.meta?.['kind'] ?? '') === key ? { ...field, amount } : field,
      ),
    );
    this.syncCompileEntries();
  }

  selectStadium(stadiumId: string) {
    this.selectedStadiumId.set(stadiumId);
    this.syncCompileEntries();
  }

  addExtraManualEntry(section: string) {
    this.extraManualEntries.update((entries) => [
      ...entries,
      { section, label: '', amount: 0, meta: { manual: true } },
    ]);
    this.syncCompileEntries();
  }

  removeExtraManualEntry(index: number) {
    this.extraManualEntries.update((entries) => entries.filter((_, i) => i !== index));
    this.syncCompileEntries();
  }

  updateExtraManualEntry(index: number, patch: Partial<BalanceEntryDraft>) {
    this.extraManualEntries.update((entries) =>
      entries.map((entry, i) => (i === index ? { ...entry, ...patch } : entry)),
    );
    this.syncCompileEntries();
  }

  extraEntriesBySection(section: string) {
    return this.extraManualEntries()
      .map((entry, index) => ({ entry, index }))
      .filter(({ entry }) => entry.section === section);
  }

  stadiumSelection(): BalanceStadiumOption | undefined {
    return this.stadiums().find((stadium) => stadium.id === this.selectedStadiumId());
  }

  issueClass(issue: BalanceIssue): string {
    return issue.severity === 'critical'
      ? 'badge badge-danger'
      : issue.severity === 'info'
        ? 'badge badge-info'
        : 'badge badge-warning';
  }

  autoEntryKey(entry: BalanceEntryDraft): string {
    return String(entry.meta?.['kind'] ?? entry.label);
  }

  normalizeRoleToken(role: string | null | undefined): string {
    const token = String(role ?? '')
      .split(';')[0]
      .trim()
      .toUpperCase();
    if (!token) return 'ALTRO';
    if (token === 'POR' || token === 'P') return 'P';
    if (['DD', 'DS', 'DC', 'B', 'D'].includes(token)) return 'D';
    if (['E', 'M', 'C', 'T', 'W'].includes(token)) return 'C';
    if (['A', 'PC'].includes(token)) return 'A';
    return 'ALTRO';
  }

  roleLabel(role: string): string {
    return (
      (
        {
          P: 'Portieri',
          D: 'Difensori',
          C: 'Centrocampisti',
          A: 'Attaccanti',
          ALTRO: 'Altri',
          Generale: 'Generale',
        } as Record<string, string>
      )[role] ?? role
    );
  }

  groupEntriesByRole(
    entries: BalanceEntryDraft[],
  ): Array<{ role: string; entries: BalanceEntryDraft[] }> {
    const grouped = new Map<string, BalanceEntryDraft[]>();
    for (const entry of entries) {
      const role = this.normalizeRoleToken(String(entry.meta?.['role'] ?? 'ALTRO'));
      grouped.set(role, [...(grouped.get(role) ?? []), entry]);
    }
    return [...grouped.entries()]
      .sort((left, right) => ROLE_ORDER.indexOf(left[0]) - ROLE_ORDER.indexOf(right[0]))
      .map(([role, roleEntries]) => ({ role, entries: roleEntries }));
  }

  autoRoleGroups(section: string): Array<{ role: string; entries: BalanceEntryDraft[] }> {
    const groups = this.autoEntriesBySectionAndRole();
    if (section === 'ricavi') return groups.ricavi;
    if (section === 'costi') return groups.costi;
    if (section === 'ammortamenti') return groups.ammortamenti;
    return groups.plus_minus;
  }

  entryPlayerDetail(entry: BalanceEntryDraft): string {
    const value = Number(entry.meta?.['market_value'] ?? 0);
    const fascia = String(entry.meta?.['fascia'] ?? '');
    const years = Number(entry.meta?.['contract_years_total'] ?? 0);
    const details: string[] = [];
    if (value > 0) details.push(`Valore ${value.toFixed(0)}`);
    if (fascia) details.push(`Fascia ${fascia.replace(/_/g, '-')}`);
    if (years > 0) details.push(`${years} anno${years > 1 ? 'i' : ''}`);
    return details.join(' · ');
  }

  isPlayerEntry(entry: BalanceEntry | BalanceEntryDraft): boolean {
    return Boolean(entry.meta && entry.meta['player_id']);
  }

  openPlayerDetail(entry: BalanceEntry | BalanceEntryDraft, ownerTeamId?: string | null) {
    if (!this.isPlayerEntry(entry)) return;
    const meta = (entry.meta ?? {}) as Record<string, unknown>;
    const ownerTeamName = ownerTeamId
      ? this.teamName(ownerTeamId)
      : this.teamName(this.compileBalance()?.team_id ?? '');
    this.playerDetail.set({
      playerName: this.playerNameFromLabel(entry.label),
      ownerTeamName,
      role: this.roleLabel(this.normalizeRoleToken(String(meta['role'] ?? 'ALTRO'))),
      contractType: this.contractTypeLabel(String(meta['acquisition_type'] ?? 'standard')),
      marketValue: Number(meta['market_value'] ?? 0),
      salary: this.playerSalary(meta),
      fascia: this.fasciaLabel(String(meta['fascia'] ?? '')),
      contractYearsTotal: Number(meta['contract_years_total'] ?? 0),
      contractYearsRemaining: Number(meta['contract_years_remaining'] ?? 0),
      sourceLabel: entry.label,
      amount: Number(entry.amount ?? 0),
    });
  }

  closePlayerDetail() {
    this.playerDetail.set(null);
  }

  playerNameFromLabel(label: string): string {
    return label
      .replace(/^Stipendio\s·\s/i, '')
      .replace(/^Ammortamento\s·\s/i, '')
      .trim();
  }

  playerSalary(meta: Record<string, unknown>): number {
    const explicitSalary = Number(meta['salary'] ?? 0);
    if (explicitSalary > 0) return explicitSalary;

    const marketValue = Number(meta['market_value'] ?? 0);
    if (marketValue >= 90) return 8;
    if (marketValue >= 70) return 6;
    if (marketValue >= 50) return 4.5;
    if (marketValue >= 35) return 3;
    if (marketValue >= 20) return 2;
    if (marketValue >= 10) return 1;
    if (marketValue >= 1) return 0.5;
    return 0;
  }

  contractTypeLabel(type: string): string {
    return (
      (
        {
          standard: 'Contratto standard',
          retained: 'Giocatore confermato',
          renewed: 'Contratto rinnovato',
          bought: 'Acquisto definitivo',
          youth: 'Contratto primavera',
          loan_in: 'Prestito in entrata',
          loan_out: 'Prestito in uscita',
          sold_definitively: 'Cessione definitiva',
        } as Record<string, string>
      )[type] ?? `Contratto ${type.replace(/_/g, ' ')}`
    );
  }

  fasciaLabel(fascia: string): string {
    return fascia ? fascia.replace(/_/g, '-') : '—';
  }

  groupTotal(
    entries: Array<Pick<BalanceEntryDraft, 'amount'> | Pick<BalanceEntry, 'amount'>>,
  ): number {
    return entries.reduce((total, entry) => total + Number(entry.amount ?? 0), 0);
  }

  compileGroupKey(section: string, role: string): string {
    return `${section}:${role}`;
  }

  publishedGroupKey(balanceId: string, section: string, role: string): string {
    return `${balanceId}:${section}:${role}`;
  }

  isCompileGroupCollapsed(section: string, role: string): boolean {
    const key = this.compileGroupKey(section, role);
    return (
      this.collapsedCompileGroups()[key] ?? (section === 'costi' || section === 'ammortamenti')
    );
  }

  toggleCompileGroup(section: string, role: string): void {
    const key = this.compileGroupKey(section, role);
    this.collapsedCompileGroups.update((state) => ({
      ...state,
      [key]: !this.isCompileGroupCollapsed(section, role),
    }));
  }

  isPublishedGroupCollapsed(balanceId: string, section: string, role: string): boolean {
    const key = this.publishedGroupKey(balanceId, section, role);
    return (
      this.collapsedPublishedGroups()[key] ?? (section === 'costi' || section === 'ammortamenti')
    );
  }

  togglePublishedGroup(balanceId: string, section: string, role: string): void {
    const key = this.publishedGroupKey(balanceId, section, role);
    this.collapsedPublishedGroups.update((state) => ({
      ...state,
      [key]: !this.isPublishedGroupCollapsed(balanceId, section, role),
    }));
  }

  fieldKey(field: BalanceGuidedField): string {
    return String(field.meta?.['kind'] ?? field.label);
  }

  syncCompileEntries() {
    const guidedEntries = this.guidedFields().map((field) => ({
      section: field.section,
      label: field.label,
      amount: field.amount,
      meta: field.meta ?? null,
    }));
    this.compileEntries.set([
      ...guidedEntries,
      ...this.extraManualEntries(),
      ...this.effectiveAutoEntries(),
    ]);
  }

  effectiveAutoEntries(): BalanceEntryDraft[] {
    const stadium = this.stadiumSelection();
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
    return [...this.autoEntries(), ...stadiumEntries];
  }

  saveCompileDraft() {
    const b = this.compileBalance();
    if (!b) return;
    this.compileSaving.set(true);
    this.compileError.set(null);
    this.compileMessage.set(null);
    const request = this.admin.isAdmin()
      ? this.api.updateAdminBalanceDraft(b.id, this.compileEntries())
      : this.api.updateBalanceDraft(b.id, this.compileEntries());
    request.subscribe({
      next: () => {
        this.compileMessage.set(this.admin.isAdmin() ? 'Bilancio aggiornato.' : 'Bozza salvata.');
        this.loadCompile(this.admin.isAdmin() ? b.id : undefined);
        this.refreshBalances();
        this.compileSaving.set(false);
      },
      error: (e) => {
        this.compileError.set(e?.error?.detail ?? 'Errore salvataggio');
        this.compileSaving.set(false);
      },
    });
  }
  submitCompile() {
    const b = this.compileBalance();
    if (!b || !this.canUploadAsTeam()) return;
    if (
      !confirm(
        'Inviare il bilancio in via definitiva? L\u2019operazione \u00e8 irreversibile (solo l\u2019admin pu\u00f2 riaprire).',
      )
    )
      return;
    this.compileSaving.set(true);
    this.api.updateBalanceDraft(b.id, this.compileEntries()).subscribe({
      next: () => {
        this.api.submitBalance(b.id).subscribe({
          next: () => {
            this.compileMessage.set('Bilancio inviato definitivamente.');
            this.compileSaving.set(false);
            this.refreshBalances();
            this.loadCompile();
          },
          error: (e) => {
            this.compileError.set(e?.error?.detail ?? 'Errore invio');
            this.compileSaving.set(false);
          },
        });
      },
      error: (e) => {
        this.compileError.set(e?.error?.detail ?? 'Errore salvataggio');
        this.compileSaving.set(false);
      },
    });
  }
  reopenCompile() {
    const b = this.compileBalance();
    if (!b || !this.admin.isAdmin()) return;
    this.api.reopenBalance(b.id).subscribe({
      next: (r) => {
        this.compileBalance.set(r);
        this.adminEditingBalanceId.set(r.id);
        this.compileMessage.set('Bilancio riaperto in modalit\u00e0 bozza.');
        this.loadCompile(r.id);
        this.refreshBalances();
      },
      error: (e) => this.compileError.set(e?.error?.detail ?? 'Errore reopen'),
    });
  }

  refreshBalances() {
    if (!this.hasBalanceAccess()) {
      this.authRequired.set(true);
      this.balances.set([]);
      this.selected.set(null);
      return;
    }

    const s = this.selectedSeason();
    const teamId = this.isTeamView() ? this.teamSession.team()?.id : undefined;
    this.api.listBalances(s || undefined, teamId).subscribe({
      next: (b) => {
        this.authRequired.set(false);
        this.balances.set(b);
      },
      error: (err) => {
        this.balances.set([]);
        this.selected.set(null);
        this.authRequired.set(err?.status === 401);
      },
    });
  }

  onSeasonChange(id: string) {
    this.selectedSeason.set(id);
    this.refreshBalances();
  }

  teamName(id: string): string {
    return this.teams().find((t) => t.id === id)?.name ?? '—';
  }

  seasonName(id: string): string {
    return this.seasons().find((s) => s.id === id)?.name ?? '—';
  }

  canUploadAsTeam(): boolean {
    return this.teamSession.isLoggedIn() && !this.admin.isAdmin();
  }

  view(b: BalanceSheet) {
    this.api.getBalance(b.id).subscribe((full) => this.selected.set(full));
  }

  openAdminBalanceEditor(balanceId: string) {
    if (!this.admin.isAdmin()) return;
    this.selected.set(null);
    this.closePlayerDetail();
    this.adminEditingBalanceId.set(balanceId);
    this.tab.set('compila');
    this.loadCompile(balanceId);
  }

  sectionEntries(s: BalanceSheet, section: string) {
    return s.entries.filter((e) => e.section === section);
  }

  publishedEntriesBySectionAndRole(
    balance: BalanceSheet,
    section: string,
  ): Array<{ role: string; entries: BalanceEntry[] }> {
    const entries = this.sectionEntries(balance, section);
    if (!['costi', 'ammortamenti'].includes(section)) {
      return [
        {
          role: 'Generale',
          entries: [...entries].sort((left, right) => right.amount - left.amount),
        },
      ];
    }

    const grouped = new Map<string, BalanceEntry[]>();
    for (const entry of entries) {
      const role = this.normalizeRoleToken(String(entry.meta?.['role'] ?? 'ALTRO'));
      grouped.set(role, [...(grouped.get(role) ?? []), entry]);
    }

    return [...grouped.entries()]
      .sort((left, right) => ROLE_ORDER.indexOf(left[0]) - ROLE_ORDER.indexOf(right[0]))
      .map(([role, roleEntries]) => ({
        role,
        entries: [...roleEntries].sort((left, right) => right.amount - left.amount),
      }));
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

  sectionLabel(s: string): string {
    return (
      (
        {
          ricavi: 'Ricavi',
          costi: 'Costi',
          ammortamenti: 'Ammortamenti',
          plus_minus: 'Plus / Minus valenze',
        } as Record<string, string>
      )[s] ?? s
    );
  }
}
