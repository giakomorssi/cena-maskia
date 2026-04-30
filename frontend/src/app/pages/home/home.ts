import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  computed,
  OnInit,
} from '@angular/core';
import { DatePipe, DecimalPipe } from '@angular/common';
import { Router, RouterLink } from '@angular/router';
import { AdminTokenService } from '../../services/admin-token.service';
import { LeagueApi } from '../../services/league.api';
import { TeamSessionService } from '../../services/team-session.service';
import {
  BalanceSheet,
  NewsPost,
  Season,
  Team,
  TeamAdminStatus,
  TeamDashboard,
} from '../../models/league.model';

@Component({
  selector: 'app-home',
  imports: [RouterLink, DatePipe, DecimalPipe],
  templateUrl: './home.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class HomeComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  private readonly router = inject(Router);
  readonly admin = inject(AdminTokenService);
  readonly teamSession = inject(TeamSessionService);

  news = signal<NewsPost[]>([]);
  currentSeason = signal<Season | null>(null);
  teams = signal<Team[]>([]);
  balances = signal<BalanceSheet[]>([]);
  dashboard = signal<TeamDashboard | null>(null);
  adminStatuses = signal<TeamAdminStatus[]>([]);
  username = signal('');
  password = signal('utente');
  loginError = signal<string | null>(null);

  readonly isAdminView = computed(() => this.admin.isAdmin());
  readonly isTeamView = computed(() => this.teamSession.isLoggedIn() && !this.admin.isAdmin());
  readonly canSeeBalances = computed(() => this.admin.isAdmin() || this.teamSession.isLoggedIn());
  teamsCount = computed(() => this.teams().length);
  balancesCount = computed(() => this.balances().length);
  sanctionsCount = computed(
    () => this.balances().filter((b) => b.sanction_level && b.sanction_level !== 'none').length,
  );

  ngOnInit() {
    this.api.listNews(5).subscribe((n) => this.news.set(n));
    this.api.listTeams().subscribe((t) => this.teams.set(t));
    this.api.listSeasons().subscribe((s) => {
      const cur = s.find((x) => x.is_current) ?? s[0] ?? null;
      this.currentSeason.set(cur);
      if (cur && this.canSeeBalances()) {
        const teamId = this.isTeamView() ? this.teamSession.team()?.id : undefined;
        this.api.listBalances(cur.id, teamId).subscribe({
          next: (b) => this.balances.set(b),
          error: () => this.balances.set([]),
        });
      }
    });
    if (this.isTeamView()) {
      this.api.getTeamDashboard().subscribe({
        next: (d) => this.dashboard.set(d),
        error: () => this.dashboard.set(null),
      });
    }
    if (this.isAdminView()) {
      this.api.getAdminTeamStatuses().subscribe({
        next: (a) => this.adminStatuses.set(a),
        error: () => this.adminStatuses.set([]),
      });
    }
  }

  readonly missingBalanceTeams = computed(() =>
    this.adminStatuses().filter((t) => !t.has_uploaded_current_balance),
  );
  readonly draftBalanceTeams = computed(() =>
    this.adminStatuses().filter((t) => t.current_balance_status === 'draft'),
  );
  readonly teamsWithUnpaidFines = computed(() =>
    this.adminStatuses().filter((t) => t.unpaid_fines_total > 0),
  );

  login() {
    const username = this.username().trim();
    const password = this.password().trim();
    if (!username || !password) {
      this.loginError.set('Inserisci username e password');
      return;
    }

    this.api.teamLogin(username, password).subscribe({
      next: (response) => {
        this.teamSession.setSession(response.access_token, response.team);
        this.loginError.set(null);
        this.username.set('');
        this.router.navigateByUrl('/profilo-squadra');
      },
      error: () => this.loginError.set('Credenziali non valide'),
    });
  }
}
