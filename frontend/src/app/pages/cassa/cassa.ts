import {
  Component,
  ChangeDetectionStrategy,
  inject,
  signal,
  OnInit,
  computed,
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink } from '@angular/router';
import { LeagueApi } from '../../services/league.api';
import { AdminTokenService } from '../../services/admin-token.service';
import { FineSummary, Season } from '../../models/league.model';

@Component({
  selector: 'app-cassa',
  standalone: true,
  imports: [CommonModule, RouterLink],
  templateUrl: './cassa.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class CassaComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  readonly admin = inject(AdminTokenService);

  readonly seasons = signal<Season[]>([]);
  readonly selectedSeason = signal<string>('');
  readonly summary = signal<FineSummary | null>(null);
  readonly loading = signal(false);
  readonly error = signal<string | null>(null);

  readonly maxMonth = computed(() => {
    const s = this.summary();
    if (!s) return 0;
    return s.by_month.reduce((m, r) => Math.max(m, r.total), 0) || 1;
  });

  ngOnInit() {
    if (!this.admin.isAdmin()) return;
    this.api.listSeasons().subscribe((s) => {
      this.seasons.set(s);
      const cur = s.find((x) => x.is_current) ?? s[0];
      if (cur) this.selectedSeason.set(cur.id);
      this.refresh();
    });
  }

  refresh() {
    if (!this.admin.isAdmin()) return;
    this.loading.set(true);
    this.error.set(null);
    this.api.getFineSummary(this.selectedSeason() || undefined).subscribe({
      next: (s) => {
        this.summary.set(s);
        this.loading.set(false);
      },
      error: (e) => {
        this.error.set(e?.error?.detail ?? 'Errore caricamento');
        this.loading.set(false);
      },
    });
  }

  onSeasonChange(id: string) {
    this.selectedSeason.set(id);
    this.refresh();
  }

  barWidth(value: number): number {
    const max = this.maxMonth();
    if (!max) return 0;
    return Math.max(2, Math.round((value / max) * 100));
  }
}
