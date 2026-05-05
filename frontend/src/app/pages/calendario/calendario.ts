import {
  ChangeDetectionStrategy,
  Component,
  OnInit,
  computed,
  inject,
  signal,
} from '@angular/core';
import { CommonModule, DecimalPipe } from '@angular/common';
import { LeagueApi } from '../../services/league.api';
import { LeagueCalendar, LeagueScheduleRound } from '../../models/league.model';

@Component({
  selector: 'app-calendario',
  imports: [CommonModule, DecimalPipe],
  templateUrl: './calendario.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CalendarioComponent implements OnInit {
  private readonly api = inject(LeagueApi);

  readonly data = signal<LeagueCalendar | null>(null);
  readonly loading = signal(true);
  readonly error = signal<string | null>(null);
  readonly selectedRoundNumber = signal<number | null>(null);

  readonly standings = computed(() => this.data()?.standings ?? []);
  readonly rounds = computed(() => this.data()?.rounds ?? []);
  readonly topThree = computed(() => this.standings().slice(0, 3));
  readonly leader = computed(() => this.standings()[0] ?? null);
  readonly latestCompletedRoundNumber = computed(() => {
    const completedRounds = this.rounds()
      .filter(
        (round) =>
          round.matches.length > 0 &&
          round.matches.every((match) => this.hasCompleteResult(match.result)),
      )
      .map((round) => round.league_round);
    return completedRounds.length ? Math.max(...completedRounds) : null;
  });
  readonly latestRound = computed(
    () =>
      this.rounds().find((round) => round.league_round === this.latestCompletedRoundNumber()) ??
      this.rounds()[this.rounds().length - 1] ??
      null,
  );
  readonly selectedRoundIndex = computed(() =>
    this.rounds().findIndex((round) => round.league_round === this.selectedRoundNumber()),
  );
  readonly selectedRound = computed(
    () =>
      this.rounds().find((round) => round.league_round === this.selectedRoundNumber()) ??
      this.latestRound(),
  );
  readonly canSelectPrevious = computed(() => this.selectedRoundIndex() > 0);
  readonly canSelectNext = computed(() => {
    const index = this.selectedRoundIndex();
    return index >= 0 && index < this.rounds().length - 1;
  });

  ngOnInit(): void {
    this.api.getLeagueCalendar().subscribe({
      next: (data) => {
        this.data.set(data);
        const completedRounds = data.rounds
          .filter(
            (round) =>
              round.matches.length > 0 &&
              round.matches.every((match) => this.hasCompleteResult(match.result)),
          )
          .map((round) => round.league_round);
        this.selectedRoundNumber.set(
          completedRounds.length
            ? Math.max(...completedRounds)
            : (data.rounds[data.rounds.length - 1]?.league_round ?? null),
        );
        this.loading.set(false);
      },
      error: () => {
        this.error.set('Impossibile caricare calendario e classifica.');
        this.loading.set(false);
      },
    });
  }

  selectRound(roundNumber: number): void {
    this.selectedRoundNumber.set(roundNumber);
  }

  isSelectedRound(roundNumber: number): boolean {
    return this.selectedRound()?.league_round === roundNumber;
  }

  isCompletedRound(round: LeagueScheduleRound): boolean {
    const latestCompletedRoundNumber = this.latestCompletedRoundNumber();
    return latestCompletedRoundNumber !== null && round.league_round <= latestCompletedRoundNumber;
  }

  roundCardClass(round: LeagueScheduleRound): string {
    const tone = this.isCompletedRound(round)
      ? 'border-success/30 bg-success-soft text-pitch-dark'
      : 'border-warning/30 bg-warning-soft text-warning';
    const selected = this.isSelectedRound(round.league_round)
      ? ' shadow-soft ring-2 ring-white/70'
      : '';
    return `${tone}${selected}`;
  }

  roundMetaClass(round: LeagueScheduleRound): string {
    return this.isCompletedRound(round) ? 'text-pitch-dark/70' : 'text-warning/80';
  }

  selectPreviousRound(): void {
    const index = this.selectedRoundIndex();
    if (index > 0) {
      this.selectedRoundNumber.set(this.rounds()[index - 1]?.league_round ?? null);
    }
  }

  selectNextRound(): void {
    const index = this.selectedRoundIndex();
    if (index >= 0 && index < this.rounds().length - 1) {
      this.selectedRoundNumber.set(this.rounds()[index + 1]?.league_round ?? null);
    }
  }

  homeGoals(result?: string | null): number | null {
    return this.parseResult(result)[0];
  }

  awayGoals(result?: string | null): number | null {
    return this.parseResult(result)[1];
  }

  resultLabel(result?: string | null): string {
    if (!result) {
      return 'Risultato non disponibile';
    }
    if (this.isDraw(result)) {
      return 'Pareggio';
    }
    if (this.hasHomeWon(result)) {
      return 'Vince la squadra di casa';
    }
    if (this.hasAwayWon(result)) {
      return 'Vince la squadra in trasferta';
    }
    return 'Risultato non disponibile';
  }

  hasHomeWon(result?: string | null): boolean {
    const [home, away] = this.parseResult(result);
    return home !== null && away !== null && home > away;
  }

  hasAwayWon(result?: string | null): boolean {
    const [home, away] = this.parseResult(result);
    return home !== null && away !== null && away > home;
  }

  isDraw(result?: string | null): boolean {
    const [home, away] = this.parseResult(result);
    return home !== null && away !== null && home === away;
  }

  private hasCompleteResult(result?: string | null): boolean {
    const [home, away] = this.parseResult(result);
    return home !== null && away !== null;
  }

  private parseResult(result?: string | null): [number | null, number | null] {
    if (!result) {
      return [null, null];
    }
    if (!/^\s*\d+\s*-\s*\d+\s*$/.test(result)) {
      return [null, null];
    }
    const parts = result.split('-').map((value) => Number(value.trim()));
    if (parts.length !== 2 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) {
      return [null, null];
    }
    return [parts[0], parts[1]];
  }
}
