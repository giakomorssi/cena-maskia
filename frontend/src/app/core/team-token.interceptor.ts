import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { TeamSessionService } from '../services/team-session.service';

export const teamTokenInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(TeamSessionService).token();
  if (!token) return next(req);
  return next(req.clone({ setHeaders: { Authorization: `Bearer ${token}` } }));
};
