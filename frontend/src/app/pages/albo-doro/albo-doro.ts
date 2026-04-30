import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
  computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { LeagueApi } from '../../services/league.api';
import { Honor, Season, Team } from '../../models/league.model';

@Component({
  selector: 'app-albo-doro',
  imports: [CommonModule],
  templateUrl: './albo-doro.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class AlboDoroComponent implements OnInit {
  private readonly api = inject(LeagueApi);

  honors = signal<Honor[]>([]);
  seasons = signal<Season[]>([]);
  teams = signal<Team[]>([]);

  groupedBySeason = computed(() => {
    const seasonsMap = new Map(this.seasons().map((s) => [s.id, s.name]));
    const groups = new Map<string, Honor[]>();
    for (const h of this.honors()) {
      const key = seasonsMap.get(h.season_id) ?? '—';
      if (!groups.has(key)) groups.set(key, []);
      groups.get(key)!.push(h);
    }
    return Array.from(groups.entries()).sort((a, b) => b[0].localeCompare(a[0]));
  });

  ngOnInit() {
    this.api.listSeasons().subscribe((s) => this.seasons.set(s));
    this.api.listTeams().subscribe((t) => this.teams.set(t));
    this.api.listHonors().subscribe((h) => this.honors.set(h));
  }

  teamName(id: string): string {
    return this.teams().find((t) => t.id === id)?.name ?? '—';
  }
}
