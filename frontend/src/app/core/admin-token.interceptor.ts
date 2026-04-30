import { HttpInterceptorFn } from '@angular/common/http';
import { inject } from '@angular/core';
import { AdminTokenService } from '../services/admin-token.service';

export const adminTokenInterceptor: HttpInterceptorFn = (req, next) => {
  const token = inject(AdminTokenService).token();
  if (!token) return next(req);
  return next(req.clone({ setHeaders: { 'X-Admin-Token': token } }));
};
