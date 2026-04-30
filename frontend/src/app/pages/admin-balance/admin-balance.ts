import {
  ChangeDetectionStrategy,
  Component,
  computed,
  inject,
  OnInit,
  signal,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { ActivatedRoute, Router } from '@angular/router';
import { LeagueApi } from '../../services/league.api';
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
} from '../../models/league.model';

const ROLE_ORDER = ['P', 'D', 'C', 'A', 'ALTRO'];

@Component({
  selector: 'app-admin-balance',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './admin-balance.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AdminBalanceComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  private readonly route = inject(ActivatedRoute);
  private readonly router = inject(Router);
  readonly admin = inject(AdminTokenService);

  readonly teams = signal<Team[]>([]);
  readonly seasons = signal<Season[]>([]);
  readonly balanceId = signal<string | null>(null);
  readonly loading = signal(false);
  readonly saving = signal(false);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);

  readonly compileBalance = signal<BalanceSheet | null>(null);
  readonly compileEntries = signal<BalanceEntryDraft[]>([]);
  readonly guidedFields = signal<BalanceGuidedField[]>([]);
  readonly autoEntries = signal<BalanceEntryDraft[]>([]);
  readonly extraManualEntries = signal<BalanceEntryDraft[]>([]);
  readonly stadiums = signal<BalanceStadiumOption[]>([]);
  readonly selectedStadiumId = signal('');
  readonly serverCompileIssues = signal<BalanceIssue[]>([]);
  readonly collapsedCompileGroups = signal<Record<string, boolean>>({});

  readonly compileTotals = computed(() => {
    let r = 0,
      c = 0,
      a = 0,
      p = 0;
    for (const entry of this.compileEntries()) {
      const amount = Number(entry.amount ?? 0);
      if (entry.section === 'ricavi') r += amount;
      else if (entry.section === 'costi') c += amount;
      else if (entry.section === 'ammortamenti') a += amount;
      else if (entry.section === 'plus_minus') p += amount;
    }
    return { ricavi: r, costi: c, ammortamenti: a, plus_minus: p, utile: r - c - a + p };
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
      if (!grouped[entry.section]) grouped[entry.section] = [];
      grouped[entry.section].push(entry);
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
    if (!this.admin.isAdmin()) return;
    this.api.listTeams().subscribe((teams) => this.teams.set(teams));
    this.api.listSeasons().subscribe((seasons) => this.seasons.set(seasons));
    this.route.paramMap.subscribe((params) => {
      const balanceId = params.get('balanceId');
      this.balanceId.set(balanceId);
      if (balanceId) {
        this.loadBalance(balanceId);
      }
    });
  }

  loadBalance(balanceId: string) {
    this.loading.set(true);
    this.error.set(null);
    this.message.set(null);
    this.api.getAdminGuidedBalance(balanceId).subscribe({
      next: (payload) => {
        this.applyGuidedPayload(payload);
        this.loading.set(false);
      },
      error: (error) => {
        this.error.set(error?.error?.detail ?? 'Errore caricamento bilancio');
        this.loading.set(false);
      },
    });
  }

  backToAdmin() {
    void this.router.navigate(['/admin']);
  }

  applyGuidedPayload(payload: GuidedBalance) {
    this.compileBalance.set(payload.balance);
    this.guidedFields.set(
      payload.guided_fields.map((field) => ({ ...field, meta: field.meta ?? null })),
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

  reloadBalance() {
    const balanceId = this.balanceId();
    if (balanceId) this.loadBalance(balanceId);
  }

  saveBalanceChanges() {
    const balance = this.compileBalance();
    if (!balance) return;
    this.saving.set(true);
    this.error.set(null);
    this.message.set(null);
    this.api.updateAdminBalanceDraft(balance.id, this.compileEntries()).subscribe({
      next: () => {
        this.message.set('Bilancio aggiornato.');
        this.saving.set(false);
        this.reloadBalance();
      },
      error: (error) => {
        this.error.set(error?.error?.detail ?? 'Errore salvataggio bilancio');
        this.saving.set(false);
      },
    });
  }

  reopenBalanceEditor() {
    const balance = this.compileBalance();
    if (!balance) return;
    this.api.reopenBalance(balance.id).subscribe({
      next: () => {
        this.message.set('Bilancio riaperto in bozza.');
        this.reloadBalance();
      },
      error: (error) => {
        this.error.set(error?.error?.detail ?? 'Errore riapertura bilancio');
      },
    });
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
    this.extraManualEntries.update((entries) => entries.filter((_, current) => current !== index));
    this.syncCompileEntries();
  }

  updateExtraManualEntry(index: number, patch: Partial<BalanceEntryDraft>) {
    this.extraManualEntries.update((entries) =>
      entries.map((entry, current) => (current === index ? { ...entry, ...patch } : entry)),
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

  teamName(id: string): string {
    return this.teams().find((team) => team.id === id)?.name ?? '—';
  }

  seasonName(id: string): string {
    return this.seasons().find((season) => season.id === id)?.name ?? '—';
  }

  sectionLabel(section: string): string {
    return (
      (
        {
          ricavi: 'Ricavi',
          costi: 'Costi',
          ammortamenti: 'Ammortamenti',
          plus_minus: 'Plus / Minus valenze',
        } as Record<string, string>
      )[section] ?? section
    );
  }

  issueClass(issue: BalanceIssue): string {
    return issue.severity === 'critical'
      ? 'badge badge-danger'
      : issue.severity === 'info'
        ? 'badge badge-info'
        : 'badge badge-warning';
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

  autoEntryKey(entry: BalanceEntryDraft): string {
    return String(entry.meta?.['kind'] ?? entry.label);
  }

  groupTotal(
    entries: Array<Pick<BalanceEntryDraft, 'amount'> | Pick<BalanceEntry, 'amount'>>,
  ): number {
    return entries.reduce((total, entry) => total + Number(entry.amount ?? 0), 0);
  }

  compileGroupKey(section: string, role: string): string {
    return `${section}:${role}`;
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

  sanctionLabel(level: string): string {
    return (
      ({ none: 'OK', light: 'Lieve', medium: 'Media', heavy: 'Grave' } as Record<string, string>)[
        level
      ] ?? level
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
}
