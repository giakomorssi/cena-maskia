import { Component, ChangeDetectionStrategy, inject, signal, OnInit } from '@angular/core';
import { CommonModule, DatePipe } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { LeagueApi } from '../../services/league.api';
import { NewsPost } from '../../models/league.model';
import { MarkdownPipe } from '../../shared/markdown.pipe';
import { TeamSessionService } from '../../services/team-session.service';

@Component({
  selector: 'app-bacheca',
  imports: [CommonModule, DatePipe, FormsModule, MarkdownPipe],
  templateUrl: './bacheca.html',
  changeDetection: ChangeDetectionStrategy.OnPush,
})
export class BachecaComponent implements OnInit {
  private readonly api = inject(LeagueApi);
  readonly teamSession = inject(TeamSessionService);

  posts = signal<NewsPost[]>([]);
  newPost = signal({ title: '', body_md: '' });
  posting = signal(false);
  error = signal<string | null>(null);
  success = signal<string | null>(null);

  ngOnInit() {
    this.loadPosts();
  }

  loadPosts() {
    this.api.listNews(50).subscribe((p) => this.posts.set(p));
  }

  setTitle(value: string) {
    this.newPost.update((current) => ({ ...current, title: value }));
  }

  setBody(value: string) {
    this.newPost.update((current) => ({ ...current, body_md: value }));
  }

  publish() {
    const payload = this.newPost();
    if (!payload.title.trim() || !payload.body_md.trim()) {
      this.error.set('Inserisci titolo e messaggio');
      return;
    }

    this.posting.set(true);
    this.error.set(null);
    this.success.set(null);
    this.api
      .createNews({ title: payload.title.trim(), body_md: payload.body_md.trim() })
      .subscribe({
        next: (post) => {
          this.posts.update((current) => [post, ...current]);
          this.newPost.set({ title: '', body_md: '' });
          this.success.set('Messaggio pubblicato in bacheca');
          this.posting.set(false);
        },
        error: (err) => {
          this.error.set(err?.error?.detail ?? 'Pubblicazione non riuscita');
          this.posting.set(false);
        },
      });
  }
}
