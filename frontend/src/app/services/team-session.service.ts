import { Injectable, computed, signal } from '@angular/core';
import { TeamAccount } from '../models/league.model';

const TOKEN_KEY = 'fanta_team_token';
const TEAM_KEY = 'fanta_team_profile';

@Injectable({ providedIn: 'root' })
export class TeamSessionService {
  private readonly _token = signal<string | null>(this.readToken());
  private readonly _team = signal<TeamAccount | null>(this.readTeam());

  readonly token = this._token.asReadonly();
  readonly team = this._team.asReadonly();
  readonly isLoggedIn = computed(() => !!this._token() && !!this._team());

  setSession(token: string, team: TeamAccount) {
    sessionStorage.setItem(TOKEN_KEY, token);
    sessionStorage.setItem(TEAM_KEY, JSON.stringify(team));
    this._token.set(token);
    this._team.set(team);
  }

  updateTeam(team: TeamAccount) {
    sessionStorage.setItem(TEAM_KEY, JSON.stringify(team));
    this._team.set(team);
  }

  clear() {
    sessionStorage.removeItem(TOKEN_KEY);
    sessionStorage.removeItem(TEAM_KEY);
    this._token.set(null);
    this._team.set(null);
  }

  private readToken(): string | null {
    try {
      return sessionStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  }

  private readTeam(): TeamAccount | null {
    try {
      const raw = sessionStorage.getItem(TEAM_KEY);
      return raw ? (JSON.parse(raw) as TeamAccount) : null;
    } catch {
      return null;
    }
  }
}
