import { Injectable, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Observable } from 'rxjs';
import { environment } from '../../environments/environment';
import {
  BalanceEntryDraft,
  GuidedBalance,
  BalanceSheet,
  Fine,
  FineSummary,
  Honor,
  LeagueCalendar,
  NewsPost,
  Player,
  PlayerCreate,
  Poll,
  Season,
  TeamAccount,
  TeamAdminStatus,
  TeamDashboard,
  TeamLoginResponse,
  Team,
  TradeProposal,
  TradeProposalCreate,
  Transfer,
} from '../models/league.model';

export type LeagueAssetUploadKind = 'rose' | 'calendar' | 'classifica';

@Injectable({ providedIn: 'root' })
export class LeagueApi {
  private readonly http = inject(HttpClient);
  private readonly base = environment.apiUrl;

  // Seasons
  listSeasons() {
    return this.http.get<Season[]>(`${this.base}seasons/`);
  }
  createSeason(body: Partial<Season>) {
    return this.http.post<Season>(`${this.base}seasons/`, body);
  }
  updateSeason(id: string, body: Partial<Season>) {
    return this.http.put<Season>(`${this.base}seasons/${id}`, body);
  }
  deleteSeason(id: string) {
    return this.http.delete<void>(`${this.base}seasons/${id}`);
  }

  // Teams
  listTeams() {
    return this.http.get<TeamAccount[]>(`${this.base}teams/`);
  }
  createTeam(body: Partial<Team>) {
    return this.http.post<Team>(`${this.base}teams/`, body);
  }
  updateTeam(id: string, body: Partial<Team>) {
    return this.http.put<Team>(`${this.base}teams/${id}`, body);
  }
  deleteTeam(id: string) {
    return this.http.delete<void>(`${this.base}teams/${id}`);
  }

  // Balances
  listBalances(seasonId?: string, teamId?: string) {
    const params: Record<string, string> = {};
    if (seasonId) params['season_id'] = seasonId;
    if (teamId) params['team_id'] = teamId;
    return this.http.get<BalanceSheet[]>(`${this.base}balances/`, { params });
  }
  getBalance(id: string) {
    return this.http.get<BalanceSheet>(`${this.base}balances/${id}`);
  }
  templateUrl(): string {
    return `${this.base}balances/template/excel`;
  }
  importBalance(teamId: string, seasonId: string, file: File): Observable<BalanceSheet> {
    const fd = new FormData();
    fd.append('team_id', teamId);
    fd.append('season_id', seasonId);
    fd.append('file', file);
    return this.http.post<BalanceSheet>(`${this.base}balances/import`, fd);
  }
  importMyBalance(seasonId: string, file: File): Observable<BalanceSheet> {
    const fd = new FormData();
    fd.append('season_id', seasonId);
    fd.append('file', file);
    return this.http.post<BalanceSheet>(`${this.base}balances/my/import`, fd);
  }
  deleteBalance(id: string) {
    return this.http.delete<void>(`${this.base}balances/${id}`);
  }

  // Transfers
  listTransfers(seasonId?: string) {
    const params: Record<string, string> = seasonId ? { season_id: seasonId } : {};
    return this.http.get<Transfer[]>(`${this.base}transfers/`, { params });
  }
  createTransfer(body: Partial<Transfer>) {
    return this.http.post<Transfer>(`${this.base}transfers/`, body);
  }
  deleteTransfer(id: string) {
    return this.http.delete<void>(`${this.base}transfers/${id}`);
  }

  // Fines
  listFines(seasonId?: string, teamId?: string) {
    const params: Record<string, string> = {};
    if (seasonId) params['season_id'] = seasonId;
    if (teamId) params['team_id'] = teamId;
    return this.http.get<Fine[]>(`${this.base}fines/`, { params });
  }
  createFine(body: Partial<Fine>) {
    return this.http.post<Fine>(`${this.base}fines/`, body);
  }
  updateFine(id: string, body: Partial<Fine>) {
    return this.http.put<Fine>(`${this.base}fines/${id}`, body);
  }
  deleteFine(id: string) {
    return this.http.delete<void>(`${this.base}fines/${id}`);
  }

  // Honors
  listHonors(seasonId?: string) {
    const params: Record<string, string> = seasonId ? { season_id: seasonId } : {};
    return this.http.get<Honor[]>(`${this.base}honors/`, { params });
  }
  createHonor(body: Partial<Honor>) {
    return this.http.post<Honor>(`${this.base}honors/`, body);
  }
  deleteHonor(id: string) {
    return this.http.delete<void>(`${this.base}honors/${id}`);
  }

  // News
  listNews(limit = 50) {
    return this.http.get<NewsPost[]>(`${this.base}news/`, { params: { limit } });
  }
  getLeagueCalendar() {
    return this.http.get<LeagueCalendar>(`${this.base}calendar/`);
  }
  createNews(body: Partial<NewsPost>) {
    return this.http.post<NewsPost>(`${this.base}news/`, body);
  }
  updateNews(id: string, body: Partial<NewsPost>) {
    return this.http.put<NewsPost>(`${this.base}news/${id}`, body);
  }
  deleteNews(id: string) {
    return this.http.delete<void>(`${this.base}news/${id}`);
  }

  // Polls
  listPolls() {
    return this.http.get<Poll[]>(`${this.base}polls/`);
  }
  createPoll(body: { question: string; options: { label: string }[]; closes_at?: string }) {
    return this.http.post<Poll>(`${this.base}polls/`, body);
  }
  vote(pollId: string, optionId: string) {
    return this.http.post<Poll>(`${this.base}polls/${pollId}/vote`, { option_id: optionId });
  }
  deletePoll(id: string) {
    return this.http.delete<void>(`${this.base}polls/${id}`);
  }

  // Content (regolamento, guida)
  getContent(slug: string) {
    return this.http.get<{ slug: string; body_md: string }>(`${this.base}content/${slug}`);
  }

  // Admin verify
  verifyAdmin() {
    return this.http.post<{ ok: boolean }>(`${this.base}admin/verify`, {});
  }

  uploadLeagueAsset(kind: LeagueAssetUploadKind, file: File) {
    const fd = new FormData();
    fd.append('file', file);
    return this.http.post<{
      ok: boolean;
      kind: LeagueAssetUploadKind;
      filename: string;
      size: number;
    }>(`${this.base}admin/uploads/${kind}`, fd);
  }

  teamLogin(username: string, password: string) {
    return this.http.post<TeamLoginResponse>(`${this.base}team-auth/login`, { username, password });
  }

  getTeamMe() {
    return this.http.get<TeamAccount>(`${this.base}team-auth/me`);
  }

  updateTeamMe(body: Partial<TeamAccount>) {
    return this.http.put<TeamAccount>(`${this.base}team-auth/me`, body);
  }

  getTeamDashboard() {
    return this.http.get<TeamDashboard>(`${this.base}team-auth/dashboard`);
  }

  getAdminTeamStatuses() {
    return this.http.get<TeamAdminStatus[]>(`${this.base}admin/teams/status`);
  }

  // ----- Players (rose) -----
  listPlayers(params: { team_id?: string; season_id?: string; active_only?: boolean } = {}) {
    const q: Record<string, string> = {};
    if (params.team_id) q['team_id'] = params.team_id;
    if (params.season_id) q['season_id'] = params.season_id;
    if (params.active_only !== undefined) q['active_only'] = String(params.active_only);
    return this.http.get<Player[]>(`${this.base}players/`, { params: q });
  }
  getPlayer(id: string) {
    return this.http.get<Player>(`${this.base}players/${id}`);
  }
  createPlayer(body: PlayerCreate) {
    return this.http.post<Player>(`${this.base}players/`, body);
  }
  updatePlayer(id: string, body: Partial<Player>) {
    return this.http.put<Player>(`${this.base}players/${id}`, body);
  }
  deletePlayer(id: string) {
    return this.http.delete<void>(`${this.base}players/${id}`);
  }
  bulkCreatePlayers(
    team_id: string,
    season_id: string,
    players: Omit<PlayerCreate, 'team_id' | 'season_id'>[],
  ) {
    return this.http.post<Player[]>(`${this.base}players/bulk`, { team_id, season_id, players });
  }

  // ----- Trades (mercato) -----
  listTrades(params: { season_id?: string; status?: string } = {}) {
    const q: Record<string, string> = {};
    if (params.season_id) q['season_id'] = params.season_id;
    if (params.status) q['status_filter'] = params.status;
    return this.http.get<TradeProposal[]>(`${this.base}trades/`, { params: q });
  }
  getTrade(id: string) {
    return this.http.get<TradeProposal>(`${this.base}trades/${id}`);
  }
  createTrade(body: TradeProposalCreate) {
    return this.http.post<TradeProposal>(`${this.base}trades/`, body);
  }
  acceptTrade(id: string, notes?: string) {
    return this.http.post<TradeProposal>(`${this.base}trades/${id}/accept`, { notes });
  }
  rejectTrade(id: string, notes?: string) {
    return this.http.post<TradeProposal>(`${this.base}trades/${id}/reject`, { notes });
  }
  cancelTrade(id: string, notes?: string) {
    return this.http.post<TradeProposal>(`${this.base}trades/${id}/cancel`, { notes });
  }
  ratifyTrade(id: string, admin_notes?: string) {
    return this.http.post<TradeProposal>(`${this.base}trades/${id}/ratify`, { admin_notes });
  }
  deleteTradePermanently(id: string) {
    return this.http.delete<void>(`${this.base}trades/${id}`);
  }
  restoreTrade(id: string) {
    return this.http.post<TradeProposal>(`${this.base}trades/${id}/restore`, {});
  }

  // ----- Balance draft / submit / reopen -----
  getMyCurrentBalance(seasonId?: string) {
    const params: Record<string, string> = seasonId ? { season_id: seasonId } : {};
    return this.http.get<BalanceSheet>(`${this.base}balances/my/current`, { params });
  }
  getMyGuidedBalance(seasonId?: string) {
    const params: Record<string, string> = seasonId ? { season_id: seasonId } : {};
    return this.http.get<GuidedBalance>(`${this.base}balances/my/current/guided`, { params });
  }
  getAdminGuidedBalance(id: string) {
    return this.http.get<GuidedBalance>(`${this.base}balances/${id}/guided`);
  }
  updateBalanceDraft(id: string, entries: BalanceEntryDraft[]) {
    return this.http.put<BalanceSheet>(`${this.base}balances/${id}/draft`, { entries });
  }
  updateAdminBalanceDraft(id: string, entries: BalanceEntryDraft[]) {
    return this.http.put<BalanceSheet>(`${this.base}balances/${id}/admin/draft`, { entries });
  }
  submitBalance(id: string) {
    return this.http.post<BalanceSheet>(`${this.base}balances/${id}/submit`, {});
  }
  reopenBalance(id: string) {
    return this.http.post<BalanceSheet>(`${this.base}balances/${id}/reopen`, {});
  }

  // ----- Fines summary (admin only) -----
  getFineSummary(seasonId?: string) {
    const params: Record<string, string> = seasonId ? { season_id: seasonId } : {};
    return this.http.get<FineSummary>(`${this.base}fines/summary`, { params });
  }
}
