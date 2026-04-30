import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LeagueApi } from '../../services/league.api';
import { AdminTokenService } from '../../services/admin-token.service';
import { TeamSessionService } from '../../services/team-session.service';
import {
  Player,
  Season,
  Team,
  TradeDirection,
  TradeKind,
  TradeProposal,
  TradeProposalCreate,
  Transfer,
} from '../../models/league.model';

type Tab = 'mine' | 'history' | 'new' | 'admin' | 'cestino';
type ProposalType =
  | 'buy'
  | 'sell'
  | 'swap'
  | 'loan_dry'
  | 'loan_with_right'
  | 'loan_with_obligation';
type WizardPage = 'type' | 'counterparty' | 'players' | 'conguaglio' | 'review';
type PaymentMode = 'immediato' | 'dilazionato';
type ContractDestination = 'keep_current' | 'new_contract';

interface DraftItem {
  player_id: string;
  player_name: string;
  player_role: string;
  direction: TradeDirection;
  acquisition_type_after?: string | null;
  contract_years_after?: number | null;
  salary_after?: number | null;
  market_value_after?: number | null;
}

interface WorkflowStep {
  code: string;
  title: string;
  summary: string;
}

interface InfoCard {
  title: string;
  body: string;
}

interface ConguaglioConfig {
  title: string;
  amountLabel: string;
  amountHint: string;
  summary: string;
  showPaymentMode?: boolean;
  showContractDestination?: boolean;
  showRedemptionPrice?: boolean;
  redemptionLabel?: string;
  redemptionHint?: string;
}

interface WizardPageDefinition {
  id: WizardPage;
  title: string;
  summary: string;
}

const STATUS_LABEL: Record<string, string> = {
  proposed: 'Proposta',
  accepted: 'Accettata',
  rejected: 'Rifiutata',
  cancelled: 'Annullata',
  ratified: 'Ratificata',
};
const STATUS_BADGE: Record<string, string> = {
  proposed: 'badge badge-info',
  accepted: 'badge badge-warning',
  rejected: 'badge badge-danger',
  cancelled: 'badge badge-neutral',
  ratified: 'badge badge-success',
};
const KIND_LABEL: Record<string, string> = {
  trade: 'Scambio',
  swap: 'Scambio',
  buy: 'Acquisto',
  sell: 'Vendita',
  loan: 'Prestito',
};
const ACQ_LABEL: Record<string, string> = {
  owned: 'Di proprietà',
  loan_dry: 'Prestito secco',
  loan_with_right: 'Prestito con diritto',
  loan_with_obligation: 'Prestito con obbligo',
  sold_definitively: 'Venduto definitivamente',
};
const KIND_DESCRIPTION: Record<string, string> = {
  trade: 'Compatibilità retroattiva con vecchie proposte di scambio.',
  swap: 'Scambio tra due rose: il valore indicato in proposta alimenta acquisti, cessioni e plus/minus automatiche alla ratifica.',
  buy: 'Acquisto definitivo con trasferimento del giocatore e contabilizzazione automatica nel bilancio della ratifica.',
  sell: 'Vendita definitiva con effetto automatico su rose, ricavi e plus/minus alla ratifica.',
  loan: 'Prestito regolamentare: secco = niente ammortamento, diritto = 50% solo con corrispettivo esplicito, obbligo = 100%.',
};
const WORKFLOW_STEPS: WorkflowStep[] = [
  {
    code: 'proposed',
    title: '1. Proposta',
    summary:
      'Il proponente seleziona controparte, giocatori, eventuale conguaglio e condizioni economiche.',
  },
  {
    code: 'accepted',
    title: '2. Accettazione',
    summary:
      'La controparte conferma o rifiuta. Fin qui non cambia ancora nulla in rosa o nel bilancio.',
  },
  {
    code: 'ratified',
    title: '3. Ratifica',
    summary:
      'Solo la ratifica admin aggiorna rose, conguagli, ammortamenti e plus/minus automatiche a bilancio.',
  },
];
const ECONOMY_RULES: InfoCard[] = [
  {
    title: 'Conguaglio',
    body: "Il cash_amount e' sempre positivo: nel wizard indica il pagamento del proponente verso la controparte.",
  },
  {
    title: 'Scambi',
    body: "Negli scambi puri il valore impostato sui giocatori e' usato come base economica per acquisti, cessioni e plus/minus.",
  },
  {
    title: 'Prestiti',
    body: 'Prestito secco senza plus/minus, con diritto solo con corrispettivo esplicito, con obbligo con impatto pieno a bilancio.',
  },
];
const PROPOSAL_TYPE_LABEL: Record<ProposalType, string> = {
  buy: 'Acquisto',
  sell: 'Vendita',
  swap: 'Scambio',
  loan_dry: 'Prestito secco',
  loan_with_right: 'Prestito con diritto di riscatto',
  loan_with_obligation: 'Prestito con obbligo di riscatto',
};
const PROPOSAL_TYPE_DESCRIPTION: Record<ProposalType, string> = {
  buy: "Il proponente acquisisce uno o piu' calciatori dalla controparte e paga solo un corrispettivo economico.",
  sell: "Il proponente cede uno o piu' calciatori e riceve solo un corrispettivo economico dalla controparte.",
  swap: "Entrambe le squadre scambiano almeno un calciatore; il conguaglio e' facoltativo.",
  loan_dry:
    "Il proponente riceve uno o piu' calciatori in prestito secco: nessun riscatto finale previsto.",
  loan_with_right:
    "Il proponente riceve uno o piu' calciatori in prestito con diritto di riscatto facoltativo.",
  loan_with_obligation:
    "Il proponente riceve uno o piu' calciatori in prestito con riscatto obbligatorio gia' definito.",
};
const CONGUAGLIO_CONFIG: Record<ProposalType, ConguaglioConfig> = {
  buy: {
    title: 'Conguaglio acquisto',
    amountLabel: 'Corrispettivo economico totale',
    amountHint:
      'Importo che il proponente riconosce alla controparte per acquisire i giocatori selezionati.',
    summary: 'Operazione solo economica: nessun calciatore viene ceduto dal proponente.',
    showPaymentMode: true,
    showContractDestination: true,
  },
  sell: {
    title: 'Conguaglio vendita',
    amountLabel: 'Corrispettivo richiesto',
    amountHint: "Importo che la controparte dovra' riconoscere per chiudere la vendita.",
    summary: "Operazione inversa all'acquisto: il proponente cede solo calciatori e riceve denaro.",
    showPaymentMode: true,
  },
  swap: {
    title: 'Conguaglio scambio',
    amountLabel: 'Conguaglio opzionale',
    amountHint:
      'Usa questo campo solo se una delle due parti compensa economicamente la differenza tecnica.',
    summary: 'Nello scambio entrambe le squadre devono inserire almeno un calciatore.',
  },
  loan_dry: {
    title: 'Conguaglio prestito secco',
    amountLabel: 'Canone / contributo stipendio',
    amountHint:
      'Importo immediato legato al prestito secco: canone fisso, contributo stipendio o combinazione dei due.',
    summary: 'Nessun riscatto finale. A fine stagione il giocatore rientra automaticamente.',
    showPaymentMode: true,
  },
  loan_with_right: {
    title: 'Conguaglio prestito con diritto',
    amountLabel: 'Canone di prestito',
    amountHint: 'Importo immediato del prestito. Il riscatto eventuale viene definito a parte.',
    summary: 'Il diritto di riscatto resta facoltativo per la squadra ricevente.',
    showPaymentMode: true,
    showRedemptionPrice: true,
    redemptionLabel: 'Prezzo di riscatto facoltativo',
    redemptionHint:
      'Importo da indicare chiaramente se la squadra ricevente decide di riscattare il giocatore a fine periodo.',
  },
  loan_with_obligation: {
    title: 'Conguaglio prestito con obbligo',
    amountLabel: 'Canone iniziale',
    amountHint:
      'Eventuale importo immediato legato al prestito. Il prezzo finale obbligatorio va indicato qui sotto.',
    summary: "Il riscatto e' vincolante e va definito in modo esplicito nella proposta.",
    showPaymentMode: true,
    showRedemptionPrice: true,
    redemptionLabel: 'Prezzo di riscatto obbligatorio',
    redemptionHint: "Questo importo e' vincolante e diventera' la base dell'acquisto differito.",
  },
};
const TRANSFER_TYPE_LABEL: Record<string, string> = {
  cessione: 'Cessione',
  prestito_secco: 'Prestito secco',
  prestito_diritto: 'Prestito con diritto',
  prestito_obbligo: 'Prestito con obbligo',
};
const PROPOSAL_WIZARD_PAGES: WizardPageDefinition[] = [
  {
    id: 'type',
    title: '1. Formula',
    summary: 'Scegli il tipo di proposta e la struttura dell’operazione.',
  },
  {
    id: 'counterparty',
    title: '2. Controparte',
    summary: "Seleziona la societa' coinvolta e prepara il tavolo della trattativa.",
  },
  {
    id: 'players',
    title: '3. Giocatori',
    summary: 'Componi la proposta scegliendo i giocatori coinvolti per ciascun lato.',
  },
  {
    id: 'conguaglio',
    title: '4. Conguaglio',
    summary: "Definisci importi, modalita' di pagamento e condizioni accessorie.",
  },
  {
    id: 'review',
    title: '5. Review',
    summary: 'Rivedi tutti i dettagli prima di inviare la proposta alla controparte.',
  },
];

@Component({
  selector: 'app-mercato',
  standalone: true,
  imports: [CommonModule, DatePipe, FormsModule],
  templateUrl: './mercato.html',
  styleUrls: ['./mercato.css'],
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class MercatoComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  readonly admin = inject(AdminTokenService);
  readonly teamSession = inject(TeamSessionService);

  readonly tab = signal<Tab>('mine');
  readonly seasons = signal<Season[]>([]);
  readonly teams = signal<Team[]>([]);
  readonly seasonId = signal<string>('');
  readonly trades = signal<TradeProposal[]>([]);
  readonly transfers = signal<Transfer[]>([]);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);
  readonly message = signal<string | null>(null);

  readonly STATUS_LABEL = STATUS_LABEL;
  readonly STATUS_BADGE = STATUS_BADGE;
  readonly KIND_LABEL = KIND_LABEL;
  readonly ACQ_LABEL = ACQ_LABEL;
  readonly WORKFLOW_STEPS = WORKFLOW_STEPS;
  readonly ECONOMY_RULES = ECONOMY_RULES;

  readonly currentTeamId = computed(() => this.teamSession.team()?.id ?? null);
  readonly isAdmin = computed(() => this.admin.isAdmin());
  readonly isTeam = computed(() => this.teamSession.isLoggedIn() && !this.admin.isAdmin());

  readonly activeTrades = computed(() =>
    this.trades().filter((t) => !['rejected', 'cancelled'].includes(t.status)),
  );
  readonly trashedTrades = computed(() =>
    this.trades().filter((t) => ['rejected', 'cancelled'].includes(t.status)),
  );

  // Wizard state
  readonly wizard = signal<{
    counterpartyId: string;
    proposalType: ProposalType;
    cash: number;
    redemptionPrice: number;
    paymentMode: PaymentMode;
    contractDestination: ContractDestination;
    notes: string;
    items: DraftItem[];
  }>({
    counterpartyId: '',
    proposalType: 'swap',
    cash: 0,
    redemptionPrice: 0,
    paymentMode: 'immediato',
    contractDestination: 'keep_current',
    notes: '',
    items: [],
  });
  readonly myRoster = signal<Player[]>([]);
  readonly counterpartyRoster = signal<Player[]>([]);
  readonly wizardSubmitting = signal(false);
  readonly wizardPage = signal<WizardPage>('type');
  readonly wizardKindDescription = computed(
    () => PROPOSAL_TYPE_DESCRIPTION[this.wizard().proposalType],
  );
  readonly isLoanWizard = computed(() => this.isLoanProposalType(this.wizard().proposalType));
  readonly proposalCountLabel = computed(
    () => `${this.wizard().items.length} giocatori inclusi nella proposta`,
  );
  readonly conguaglioConfig = computed(() => CONGUAGLIO_CONFIG[this.wizard().proposalType]);
  readonly PROPOSAL_WIZARD_PAGES = PROPOSAL_WIZARD_PAGES;
  readonly wizardPageIndex = computed(() =>
    PROPOSAL_WIZARD_PAGES.findIndex((page) => page.id === this.wizardPage()),
  );
  readonly wizardPageProgress = computed(() => this.wizardPageIndex() + 1);
  readonly selectedCounterparty = computed(
    () => this.teams().find((team) => team.id === this.wizard().counterpartyId) ?? null,
  );
  readonly proposerItemsCount = computed(
    () => this.wizard().items.filter((item) => item.direction === 'from_proposer').length,
  );
  readonly counterpartyItemsCount = computed(
    () => this.wizard().items.filter((item) => item.direction === 'from_counterparty').length,
  );
  readonly canSubmitProposal = computed(
    () => !this.validateProposalDraft() && !this.wizardSubmitting(),
  );

  ngOnInit() {
    this.api.listTeams().subscribe((t) => this.teams.set(t));
    this.api.listSeasons().subscribe((s) => {
      this.seasons.set(s);
      const cur = s.find((x) => x.is_current) ?? s[0];
      if (cur) this.seasonId.set(cur.id);
      this.refresh();
    });
  }

  setTab(t: Tab) {
    this.tab.set(t);
    this.error.set(null);
    this.message.set(null);
    if (t === 'new' && this.isTeam()) {
      this.wizardPage.set('type');
      this.loadMyRoster();
    }
    if (t === 'history') this.loadTransfers();
    else this.refresh();
  }

  refresh() {
    if (!this.seasonId()) return;
    if (this.tab() === 'history') return;
    if (!this.isAdmin() && !this.isTeam()) {
      this.trades.set([]);
      return;
    }
    this.loading.set(true);
    const status = this.tab() === 'admin' ? 'accepted' : undefined;
    this.api.listTrades({ season_id: this.seasonId(), status }).subscribe({
      next: (list) => {
        this.trades.set(list);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.detail ?? 'Errore caricamento proposte');
        this.loading.set(false);
      },
    });
  }

  loadTransfers() {
    this.api.listTransfers(this.seasonId() || undefined).subscribe({
      next: (t) => this.transfers.set(t),
    });
  }

  onSeasonChange(id: string) {
    this.seasonId.set(id);
    this.refresh();
    if (this.tab() === 'new') this.loadMyRoster();
  }

  teamName(id: string | null | undefined): string {
    if (!id) return '—';
    return this.teams().find((t) => t.id === id)?.name ?? '—';
  }

  accept(t: TradeProposal) {
    this.api.acceptTrade(t.id).subscribe({
      next: () => {
        this.message.set('Proposta accettata. In attesa di ratifica admin.');
        this.refresh();
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore'),
    });
  }
  reject(t: TradeProposal) {
    if (!confirm('Rifiutare la proposta?')) return;
    this.api.rejectTrade(t.id).subscribe({
      next: () => {
        this.message.set('Proposta rifiutata.');
        this.refresh();
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore'),
    });
  }
  cancel(t: TradeProposal) {
    if (!confirm('Annullare la proposta?')) return;
    this.api.cancelTrade(t.id).subscribe({
      next: () => {
        this.message.set('Proposta annullata.');
        this.refresh();
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore'),
    });
  }
  ratify(t: TradeProposal) {
    if (
      !confirm(
        'Ratificare e applicare la proposta? Rose e bilancio verranno aggiornati automaticamente.',
      )
    )
      return;
    this.api.ratifyTrade(t.id).subscribe({
      next: () => {
        this.message.set('Proposta ratificata e applicata.');
        this.refresh();
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore ratifica'),
    });
  }

  permanentDelete(t: TradeProposal) {
    if (!confirm("Eliminare definitivamente questa proposta? L'operazione non è reversibile."))
      return;
    this.api.deleteTradePermanently(t.id).subscribe({
      next: () => {
        this.message.set('Proposta eliminata definitivamente.');
        this.refresh();
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore eliminazione'),
    });
  }

  restore(t: TradeProposal) {
    if (!confirm('Ripristinare la proposta allo stato "in attesa di risposta"?')) return;
    this.api.restoreTrade(t.id).subscribe({
      next: () => {
        this.message.set('Proposta ripristinata.');
        this.setTab('mine');
      },
      error: (e) => this.error.set(e?.error?.detail ?? 'Errore ripristino'),
    });
  }

  loadMyRoster() {
    const tid = this.currentTeamId();
    if (!tid || !this.seasonId()) return;
    this.api
      .listPlayers({ team_id: tid, season_id: this.seasonId() })
      .subscribe({ next: (p) => this.myRoster.set(p.filter((x) => x.is_active)) });
  }
  onCounterpartyChange(id: string) {
    this.wizard.update((w) => ({
      ...w,
      counterpartyId: id,
      items: w.items.filter((it) => it.direction === 'from_proposer'),
    }));
    if (id && this.seasonId()) {
      this.api
        .listPlayers({ team_id: id, season_id: this.seasonId() })
        .subscribe({ next: (p) => this.counterpartyRoster.set(p.filter((x) => x.is_active)) });
    } else {
      this.counterpartyRoster.set([]);
    }
    if (id && this.wizardPage() === 'counterparty') {
      this.error.set(null);
    }
  }
  toggleWizardItem(p: Player, direction: TradeDirection) {
    this.wizard.update((w) => {
      if (w.items.some((it) => it.player_id === p.id)) {
        return { ...w, items: w.items.filter((it) => it.player_id !== p.id) };
      }
      const item: DraftItem = {
        player_id: p.id,
        player_name: p.name,
        player_role: p.role,
        direction,
        acquisition_type_after: this.defaultAcquisitionType(w.proposalType),
        contract_years_after: p.contract_years_remaining,
        salary_after: p.salary,
        market_value_after: p.market_value,
      };
      return { ...w, items: [...w.items, item] };
    });
  }
  isInWizard(playerId: string): boolean {
    return this.wizard().items.some((it) => it.player_id === playerId);
  }
  updateWizardItem(playerId: string, patch: Partial<DraftItem>) {
    this.wizard.update((w) => ({
      ...w,
      items: w.items.map((it) => (it.player_id === playerId ? { ...it, ...patch } : it)),
    }));
  }
  resetWizard() {
    this.wizard.set({
      counterpartyId: '',
      proposalType: 'swap',
      cash: 0,
      redemptionPrice: 0,
      paymentMode: 'immediato',
      contractDestination: 'keep_current',
      notes: '',
      items: [],
    });
    this.wizardPage.set('type');
    this.counterpartyRoster.set([]);
  }
  setProposalType(proposalType: ProposalType) {
    this.wizard.update((w) => ({
      ...w,
      proposalType,
      cash: 0,
      redemptionPrice: 0,
      items: w.items
        .map((item) => ({
          ...item,
          acquisition_type_after: this.normalizeAcquisitionForProposalType(proposalType),
        }))
        .filter((item) => this.isDirectionAllowed(proposalType, item.direction)),
    }));
    if (this.wizardPage() === 'type') {
      this.error.set(null);
    }
  }
  setWizardCash(v: number | string) {
    this.wizard.update((w) => ({ ...w, cash: +v || 0 }));
  }
  setRedemptionPrice(v: number | string) {
    this.wizard.update((w) => ({ ...w, redemptionPrice: +v || 0 }));
  }
  setPaymentMode(v: PaymentMode) {
    this.wizard.update((w) => ({ ...w, paymentMode: v }));
  }
  setContractDestination(v: ContractDestination) {
    this.wizard.update((w) => ({ ...w, contractDestination: v }));
  }
  setWizardNotes(v: string) {
    this.wizard.update((w) => ({ ...w, notes: v ?? '' }));
  }
  submitWizard() {
    const w = this.wizard();
    const tid = this.currentTeamId();
    if (!tid) {
      this.error.set('Devi essere loggato come squadra.');
      return;
    }
    const draftError = this.validateProposalDraft();
    if (draftError) {
      this.error.set(draftError);
      this.focusFirstInvalidWizardPage();
      return;
    }
    const body: TradeProposalCreate = {
      season_id: this.seasonId(),
      from_team_id: tid,
      to_team_id: w.counterpartyId,
      kind: this.backendKindForProposalType(w.proposalType),
      cash_amount: +w.cash || 0,
      notes: this.composeNotes(w),
      items: w.items.map((it) => ({
        player_id: it.player_id,
        direction: it.direction,
        acquisition_type_after: it.acquisition_type_after ?? null,
        contract_years_after: it.contract_years_after ?? null,
        salary_after: it.salary_after ?? null,
        market_value_after: it.market_value_after ?? null,
      })),
    };
    this.wizardSubmitting.set(true);
    this.error.set(null);
    this.api.createTrade(body).subscribe({
      next: () => {
        this.message.set('Proposta inviata.');
        this.resetWizard();
        this.wizardSubmitting.set(false);
        this.setTab('mine');
      },
      error: (e) => {
        this.error.set(e?.error?.detail ?? 'Errore creazione proposta');
        this.wizardSubmitting.set(false);
      },
    });
  }

  backendKindForProposalType(proposalType: ProposalType): TradeKind {
    if (this.isLoanProposalType(proposalType)) {
      return 'loan';
    }
    return proposalType as Extract<ProposalType, 'buy' | 'sell' | 'swap'>;
  }

  defaultAcquisitionType(proposalType: ProposalType): string {
    return this.normalizeAcquisitionForProposalType(proposalType);
  }

  normalizeAcquisitionForProposalType(proposalType: ProposalType): string {
    if (proposalType === 'loan_dry') {
      return 'loan_dry';
    }
    if (proposalType === 'loan_with_right') {
      return 'loan_with_right';
    }
    if (proposalType === 'loan_with_obligation') {
      return 'loan_with_obligation';
    }
    return 'owned';
  }

  isLoanProposalType(proposalType: ProposalType): boolean {
    return ['loan_dry', 'loan_with_right', 'loan_with_obligation'].includes(proposalType);
  }

  isDirectionAllowed(proposalType: ProposalType, direction: TradeDirection): boolean {
    if (proposalType === 'swap') {
      return true;
    }
    if (proposalType === 'sell') {
      return direction === 'from_proposer';
    }
    return direction === 'from_counterparty';
  }

  validateProposalStructure(proposalType: ProposalType, items: DraftItem[]): string | null {
    const proposerItems = items.filter((item) => item.direction === 'from_proposer');
    const counterpartyItems = items.filter((item) => item.direction === 'from_counterparty');

    if (proposalType === 'swap') {
      if (proposerItems.length === 0 || counterpartyItems.length === 0) {
        return 'Per uno scambio devi inserire almeno un giocatore per lato.';
      }
      return null;
    }
    if (proposalType === 'sell') {
      if (proposerItems.length === 0) {
        return 'Per una vendita devi selezionare almeno un tuo giocatore.';
      }
      if (counterpartyItems.length > 0) {
        return 'Nella vendita non puoi inserire giocatori dalla controparte.';
      }
      return null;
    }
    if (counterpartyItems.length === 0) {
      return 'Per questa proposta devi selezionare almeno un giocatore dalla rosa della controparte.';
    }
    if (proposerItems.length > 0) {
      return 'In questa tipologia non puoi aggiungere giocatori del proponente alla proposta.';
    }
    return null;
  }

  validateWizardPage(page: WizardPage): string | null {
    const wizard = this.wizard();
    if (page === 'type') {
      return null;
    }
    if (page === 'counterparty') {
      return wizard.counterpartyId ? null : 'Seleziona la squadra controparte.';
    }
    if (page === 'players') {
      if (wizard.items.length === 0) {
        return 'Aggiungi almeno un giocatore alla proposta.';
      }
      return this.validateProposalStructure(wizard.proposalType, wizard.items);
    }
    if (page === 'conguaglio') {
      if (wizard.proposalType === 'loan_with_obligation' && wizard.redemptionPrice <= 0) {
        return 'Per il prestito con obbligo devi indicare un prezzo di riscatto obbligatorio.';
      }
      return null;
    }
    return null;
  }

  validateProposalDraft(): string | null {
    for (const page of PROPOSAL_WIZARD_PAGES) {
      const error = this.validateWizardPage(page.id);
      if (error) {
        return error;
      }
    }
    return null;
  }

  canAccessWizardPage(page: WizardPage): boolean {
    const targetIndex = PROPOSAL_WIZARD_PAGES.findIndex((item) => item.id === page);
    if (targetIndex <= 0) {
      return true;
    }
    for (const previousPage of PROPOSAL_WIZARD_PAGES.slice(0, targetIndex)) {
      if (this.validateWizardPage(previousPage.id)) {
        return false;
      }
    }
    return true;
  }

  setWizardPage(page: WizardPage): void {
    if (!this.canAccessWizardPage(page)) {
      const error = this.validateProposalDraft();
      if (error) {
        this.error.set(error);
      }
      return;
    }
    this.error.set(null);
    this.wizardPage.set(page);
  }

  nextWizardPage(): void {
    const currentIndex = this.wizardPageIndex();
    const currentPage = PROPOSAL_WIZARD_PAGES[currentIndex];
    const error = this.validateWizardPage(currentPage.id);
    if (error) {
      this.error.set(error);
      return;
    }
    const nextPage = PROPOSAL_WIZARD_PAGES[currentIndex + 1];
    if (nextPage) {
      this.error.set(null);
      this.wizardPage.set(nextPage.id);
    }
  }

  previousWizardPage(): void {
    const previousPage = PROPOSAL_WIZARD_PAGES[this.wizardPageIndex() - 1];
    if (previousPage) {
      this.error.set(null);
      this.wizardPage.set(previousPage.id);
    }
  }

  hasPreviousWizardPage(): boolean {
    return this.wizardPageIndex() > 0;
  }

  hasNextWizardPage(): boolean {
    return this.wizardPageIndex() < PROPOSAL_WIZARD_PAGES.length - 1;
  }

  focusFirstInvalidWizardPage(): void {
    const invalidPage = PROPOSAL_WIZARD_PAGES.find((page) => this.validateWizardPage(page.id));
    if (invalidPage) {
      this.wizardPage.set(invalidPage.id);
    }
  }

  isWizardPageActive(page: WizardPage): boolean {
    return this.wizardPage() === page;
  }

  isWizardPageCompleted(page: WizardPage): boolean {
    return !this.validateWizardPage(page);
  }

  composeNotes(w: {
    proposalType: ProposalType;
    paymentMode: PaymentMode;
    contractDestination: ContractDestination;
    redemptionPrice: number;
    notes: string;
  }): string | null {
    const details = [
      `Tipologia proposta: ${PROPOSAL_TYPE_LABEL[w.proposalType]}`,
      `Modalita' pagamento: ${w.paymentMode}`,
    ];
    if (CONGUAGLIO_CONFIG[w.proposalType].showContractDestination) {
      details.push(
        `Destinazione contrattuale: ${
          w.contractDestination === 'keep_current'
            ? 'Mantenimento contratto attuale'
            : 'Nuovo contratto'
        }`,
      );
    }
    if (CONGUAGLIO_CONFIG[w.proposalType].showRedemptionPrice) {
      details.push(`Prezzo riscatto: ${w.redemptionPrice || 0}`);
    }
    if (w.notes.trim()) {
      details.push(`Note: ${w.notes.trim()}`);
    }
    return details.join('\n');
  }

  flowHint(status: string): string {
    switch (status) {
      case 'proposed':
        return "La proposta e' ancora in negoziazione: nessun effetto su rose o bilancio.";
      case 'accepted':
        return 'La controparte ha accettato. Si attende la ratifica admin per applicare operazione e automatismi contabili.';
      case 'ratified':
        return 'Operazione ratificata: rose, conguagli, ammortamenti e plus/minus sono stati aggiornati.';
      case 'rejected':
        return "La proposta e' stata rifiutata e non produce alcun effetto economico.";
      case 'cancelled':
        return "La proposta e' stata annullata dal proponente prima della chiusura del workflow.";
      default:
        return 'Workflow mercato in corso.';
    }
  }

  transferTypeLabel(type: string | null | undefined): string {
    if (!type) return '—';
    return TRANSFER_TYPE_LABEL[type] || type;
  }

  rosterColumnTitle(direction: TradeDirection): string {
    if (direction === 'from_proposer') {
      return this.wizard().proposalType === 'sell'
        ? 'Giocatori in vendita del proponente'
        : 'Giocatori del proponente';
    }
    return 'Giocatori della controparte';
  }

  rosterColumnHint(direction: TradeDirection): string {
    if (direction === 'from_proposer') {
      if (this.wizard().proposalType === 'sell') {
        return 'Seleziona i giocatori che vuoi vendere alla controparte.';
      }
      if (this.wizard().proposalType === 'swap') {
        return 'Seleziona i giocatori che il proponente mette nello scambio.';
      }
      return 'Questa tipologia non prevede giocatori in uscita dal proponente.';
    }
    if (this.isLoanProposalType(this.wizard().proposalType)) {
      return 'Dopo aver scelto la controparte puoi vedere stipendio, anni di contratto, residuo e stato dei giocatori selezionabili.';
    }
    if (this.wizard().proposalType === 'buy') {
      return 'Seleziona i giocatori che vuoi acquistare dalla controparte.';
    }
    if (this.wizard().proposalType === 'swap') {
      return 'Seleziona i giocatori che la controparte mette nello scambio.';
    }
    return 'Seleziona i giocatori che vuoi ricevere in prestito dalla controparte.';
  }

  directionLabel(direction: TradeDirection): string {
    return direction === 'from_proposer' ? 'Dal proponente' : 'Dalla controparte';
  }

  proposalTypeLabel(type: ProposalType): string {
    return PROPOSAL_TYPE_LABEL[type];
  }

  paymentModeLabel(mode: PaymentMode): string {
    return mode === 'immediato' ? 'Immediato' : 'Dilazionato';
  }

  contractDestinationLabel(destination: ContractDestination): string {
    return destination === 'keep_current' ? 'Mantenimento contratto attuale' : 'Nuovo contratto';
  }

  proposalDisplayLabel(proposal: TradeProposal): string {
    if (proposal.kind !== 'loan') {
      return KIND_LABEL[proposal.kind] || proposal.kind;
    }
    const first = proposal.items[0]?.acquisition_type_after;
    if (first === 'loan_dry') return PROPOSAL_TYPE_LABEL.loan_dry;
    if (first === 'loan_with_right') return PROPOSAL_TYPE_LABEL.loan_with_right;
    if (first === 'loan_with_obligation') return PROPOSAL_TYPE_LABEL.loan_with_obligation;
    return KIND_LABEL['loan'];
  }

  playerContractStatus(player: Player): string {
    return player.contract_years_remaining <= 1 ? 'In scadenza' : 'Attivo';
  }

  directionActionLabel(direction: TradeDirection): string {
    const proposalType = this.wizard().proposalType;
    if (proposalType === 'swap') {
      return direction === 'from_proposer' ? '+ Cedi' : '+ Ricevi';
    }
    if (proposalType === 'sell') {
      return '+ Vendi';
    }
    if (proposalType === 'buy') {
      return '+ Acquista';
    }
    return '+ Richiedi';
  }

  isDirectionSelectionEnabled(direction: TradeDirection): boolean {
    return this.isDirectionAllowed(this.wizard().proposalType, direction);
  }

  shouldShowDirectionSection(direction: TradeDirection): boolean {
    if (direction === 'from_counterparty') {
      return true;
    }
    return this.isDirectionSelectionEnabled(direction);
  }

  isCounterpartySelected(): boolean {
    return !!this.wizard().counterpartyId;
  }

  formulaLabel(item: DraftItem): string {
    return ACQ_LABEL[item.acquisition_type_after || 'owned'] || "Di proprieta'";
  }

  itemsByDirection(t: TradeProposal, dir: TradeDirection) {
    return t.items.filter((i) => i.direction === dir);
  }

  /** Parses the structured notes written by composeNotes() into a key-value map. */
  parseTradeNotes(notes: string | null | undefined): Record<string, string> {
    const result: Record<string, string> = {};
    if (!notes) return result;
    for (const line of notes.split('\n')) {
      const idx = line.indexOf(':');
      if (idx > 0) {
        const key = line.slice(0, idx).trim();
        const val = line.slice(idx + 1).trim();
        result[key] = val;
      }
    }
    return result;
  }

  /** CSS class for the formula badge based on trade kind/acquisition type. */
  formulaBadgeClass(t: TradeProposal): string {
    const first = t.items[0]?.acquisition_type_after;
    if (t.kind === 'swap') return 'badge badge-warning';
    if (t.kind === 'buy') return 'badge badge-success';
    if (t.kind === 'sell') return 'badge badge-danger';
    if (first === 'loan_with_obligation') return 'badge badge-danger';
    if (first === 'loan_with_right') return 'badge badge-warning';
    return 'badge badge-info';
  }
  selectableCounterparties = computed(() =>
    this.teams().filter((t) => t.id !== this.currentTeamId()),
  );
}
