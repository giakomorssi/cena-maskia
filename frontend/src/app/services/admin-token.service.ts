import { Injectable, signal, computed } from '@angular/core';

const STORAGE_KEY = 'fanta_admin_token';

@Injectable({ providedIn: 'root' })
export class AdminTokenService {
  private readonly _token = signal<string | null>(this.read());
  readonly token = this._token.asReadonly();
  readonly isAdmin = computed(() => !!this._token());

  set(token: string) {
    sessionStorage.setItem(STORAGE_KEY, token);
    this._token.set(token);
  }

  clear() {
    sessionStorage.removeItem(STORAGE_KEY);
    this._token.set(null);
  }

  private read(): string | null {
    try {
      return sessionStorage.getItem(STORAGE_KEY);
    } catch {
      return null;
    }
  }
}
