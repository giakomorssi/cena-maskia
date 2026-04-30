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
import { LeagueCalendar } from '../../models/league.model';

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
  readonly latestRound = computed(() => this.rounds()[this.rounds().length - 1] ?? null);
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
        this.selectedRoundNumber.set(data.rounds[data.rounds.length - 1]?.league_round ?? null);
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

  private parseResult(result?: string | null): [number | null, number | null] {
    if (!result) {
      return [null, null];
    }
    const parts = result.split('-').map((value) => Number(value.trim()));
    if (parts.length !== 2 || Number.isNaN(parts[0]) || Number.isNaN(parts[1])) {
      return [null, null];
    }
    return [parts[0], parts[1]];
  }
}
