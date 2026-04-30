export interface Season {
  id: string;
  name: string;
  start_date?: string | null;
  end_date?: string | null;
  is_current: boolean;
  created_at: string;
}

export interface Team {
  id: string;
  name: string;
  manager_name?: string | null;
  logo_url?: string | null;
  founded_year?: number | null;
  created_at: string;
}

export interface TeamAccount extends Team {
  account_username: string;
  profile_bio?: string | null;
  home_city?: string | null;
  is_active: boolean;
  last_login?: string | null;
}

export interface BalanceEntry {
  id: string;
  section: 'ricavi' | 'costi' | 'ammortamenti' | 'plus_minus' | string;
  label: string;
  amount: number;
  meta?: Record<string, unknown> | null;
}

export interface BalanceEntryDraft {
  section: string;
  label: string;
  amount: number;
  meta?: Record<string, unknown> | null;
}

export interface BalanceIssue {
  code: string;
  label: string;
  detail: string;
  severity: 'info' | 'warning' | 'critical' | string;
}

export interface BalanceStadiumOption {
  id: string;
  name: string;
  city: string;
  revenue: number;
  cost: number;
  description: string;
}

export interface BalanceGuidedField {
  section: 'ricavi' | 'costi' | 'ammortamenti' | 'plus_minus' | string;
  label: string;
  amount: number;
  meta?: Record<string, unknown> | null;
  description: string;
}

export interface GuidedBalance {
  balance: BalanceSheet;
  selected_stadium_id?: string | null;
  stadiums: BalanceStadiumOption[];
  guided_fields: BalanceGuidedField[];
  auto_entries: BalanceEntryDraft[];
  extra_manual_entries: BalanceEntryDraft[];
  issues: BalanceIssue[];
}

export interface BalanceSheet {
  id: string;
  team_id: string;
  season_id: string;
  status: 'draft' | 'submitted' | string;
  file_url?: string | null;
  total_ricavi: number;
  total_costi: number;
  total_ammortamenti: number;
  total_plus_minus: number;
  utile: number;
  sanction_level: 'none' | 'light' | 'medium' | 'heavy' | string;
  sanction_points: number;
  sanction_notes?: string | null;
  submitted_at: string;
  entries: BalanceEntry[];
}

export interface Transfer {
  id: string;
  season_id: string;
  from_team_id?: string | null;
  to_team_id?: string | null;
  player_name: string;
  fee: number;
  type: string;
  transfer_date?: string | null;
  notes?: string | null;
}

export interface Fine {
  id: string;
  season_id: string;
  team_id: string;
  reason: string;
  amount: number;
  paid: boolean;
  fine_date?: string | null;
}

export interface Honor {
  id: string;
  season_id: string;
  team_id: string;
  trophy: string;
  position?: number | null;
  notes?: string | null;
}

export interface NewsPost {
  id: string;
  title: string;
  body_md: string;
  author?: string | null;
  pinned: boolean;
  published_at: string;
}

export interface LeagueStandingRow {
  position: number;
  team: string;
  played: number;
  wins: number;
  draws: number;
  losses: number;
  goals_for: number;
  goals_against: number;
  goal_diff: number;
  points: number;
  total_points: number;
}

export interface LeagueScheduleMatch {
  home_team: string;
  home_score?: number | null;
  away_score?: number | null;
  away_team: string;
  result?: string | null;
}

export interface LeagueScheduleRound {
  league_round: number;
  serie_a_round?: number | null;
  matches: LeagueScheduleMatch[];
}

export interface LeagueCalendar {
  title: string;
  source_url?: string | null;
  standings: LeagueStandingRow[];
  rounds: LeagueScheduleRound[];
}

export interface PollOption {
  id: string;
  label: string;
  votes_count: number;
}

export interface Poll {
  id: string;
  question: string;
  is_open: boolean;
  created_at: string;
  closes_at?: string | null;
  options: PollOption[];
}

export interface TeamLoginResponse {
  access_token: string;
  token_type: string;
  team: TeamAccount;
}

export interface TeamDashboard {
  team: TeamAccount;
  current_season?: Season | null;
  latest_balance?: BalanceSheet | null;
  recent_balances: BalanceSheet[];
  fines: Fine[];
  transfers: Transfer[];
  honors: Honor[];
  unpaid_fines_total: number;
  has_uploaded_current_balance: boolean;
  current_balance_status?: string | null;
  roster_summary?: RosterSummary | null;
  pending_incoming_trades: number;
  pending_outgoing_trades: number;
}

export interface TeamAdminStatus {
  team_id: string;
  team_name: string;
  account_username: string;
  manager_name?: string | null;
  current_season_name?: string | null;
  profile_complete: boolean;
  has_uploaded_current_balance: boolean;
  current_balance_status?: string | null;
  latest_submitted_at?: string | null;
  latest_sanction_level?: string | null;
  latest_sanction_points?: number | null;
  unpaid_fines_total: number;
  roster_count: number;
  anomalies: BalanceIssue[];
  is_ok: boolean;
}

// ----- Players (rosters) -----

export type PlayerFascia =
  | '1_9'
  | '10_19'
  | '20_34'
  | '35_49'
  | '50_69'
  | '70_89'
  | '90_120'
  | '120_plus';
export type PlayerAcquisition =
  | 'owned'
  | 'loan_dry'
  | 'loan_with_right'
  | 'loan_with_obligation'
  | 'sold_definitively';

export interface Player {
  id: string;
  team_id: string;
  season_id: string;
  name: string;
  role: string;
  fascia: PlayerFascia | string;
  salary: number;
  market_value: number;
  contract_years_total: number;
  contract_years_remaining: number;
  acquisition_type: PlayerAcquisition | string;
  acquisition_season_id?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface PlayerCreate {
  team_id: string;
  season_id: string;
  name: string;
  role: string;
  fascia?: PlayerFascia | string;
  salary?: number;
  market_value?: number;
  contract_years_total?: number;
  contract_years_remaining?: number;
  acquisition_type?: PlayerAcquisition | string;
  acquisition_season_id?: string | null;
  notes?: string | null;
}

export interface RosterSummary {
  season_id?: string | null;
  count: number;
  total_salary: number;
  total_value: number;
  by_fascia: Record<string, number>;
  by_acquisition: Record<string, number>;
}

// ----- Trade proposals (mercato) -----

export type TradeStatus = 'proposed' | 'accepted' | 'rejected' | 'cancelled' | 'ratified';
export type TradeKind = 'trade' | 'buy' | 'sell' | 'swap' | 'loan';
export type TradeDirection = 'from_proposer' | 'from_counterparty';

export interface TradeProposalItem {
  id: string;
  player_id: string;
  player_name?: string | null;
  player_role?: string | null;
  direction: TradeDirection;
  acquisition_type_after?: string | null;
  contract_years_after?: number | null;
  salary_after?: number | null;
  market_value_after?: number | null;
}

export interface TradeProposal {
  id: string;
  season_id: string;
  from_team_id: string;
  from_team_name?: string | null;
  to_team_id: string;
  to_team_name?: string | null;
  kind: TradeKind | string;
  status: TradeStatus | string;
  cash_amount: number;
  notes?: string | null;
  admin_notes?: string | null;
  created_at: string;
  updated_at: string;
  accepted_at?: string | null;
  ratified_at?: string | null;
  items: TradeProposalItem[];
}

export interface TradeProposalCreate {
  season_id: string;
  from_team_id: string;
  to_team_id: string;
  kind?: TradeKind | string;
  cash_amount?: number;
  notes?: string | null;
  items: {
    player_id: string;
    direction: TradeDirection;
    acquisition_type_after?: string | null;
    contract_years_after?: number | null;
    salary_after?: number | null;
    market_value_after?: number | null;
  }[];
}

// ----- Fine summary (cassa admin) -----

export interface FineSummaryRow {
  team_id: string;
  team_name: string;
  count: number;
  total: number;
  paid: number;
  unpaid: number;
}

export interface FineSummaryMonth {
  month: string;
  total: number;
  count: number;
}

export interface FineSummary {
  season_id?: string | null;
  total: number;
  paid: number;
  unpaid: number;
  count: number;
  rows: FineSummaryRow[];
  by_month: FineSummaryMonth[];
}
