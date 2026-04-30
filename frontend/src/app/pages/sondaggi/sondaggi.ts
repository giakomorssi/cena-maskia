import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { CommonModule } from '@angular/common';
import { LeagueApi } from '../../services/league.api';
import { Poll } from '../../models/league.model';

@Component({
  selector: 'app-sondaggi',
  imports: [CommonModule],
  templateUrl: './sondaggi.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class SondaggiComponent implements OnInit {
  private readonly api = inject(LeagueApi);

  polls = signal<Poll[]>([]);
  votedKey(p: Poll) {
    return `voted_${p.id}`;
  }
  voteError = signal<string | null>(null);

  ngOnInit() {
    this.api.listPolls().subscribe((p) => this.polls.set(p));
  }

  hasVoted(p: Poll): boolean {
    try {
      return !!localStorage.getItem(this.votedKey(p));
    } catch {
      return false;
    }
  }

  totalVotes(p: Poll): number {
    return p.options.reduce((s, o) => s + (o.votes_count || 0), 0);
  }

  pct(p: Poll, count: number): number {
    const total = this.totalVotes(p);
    return total === 0 ? 0 : Math.round((count / total) * 100);
  }

  vote(poll: Poll, optionId: string) {
    this.voteError.set(null);
    this.api.vote(poll.id, optionId).subscribe({
      next: (updated) => {
        try {
          localStorage.setItem(this.votedKey(poll), optionId);
        } catch {}
        this.polls.update((list) => list.map((p) => (p.id === updated.id ? updated : p)));
      },
      error: (err) => this.voteError.set(err?.error?.detail ?? 'Errore voto'),
    });
  }
}
