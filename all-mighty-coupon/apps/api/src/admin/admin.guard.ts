import {
  CanActivate,
  ExecutionContext,
  Injectable,
  ServiceUnavailableException,
  UnauthorizedException,
} from '@nestjs/common';
import { timingSafeEqual } from 'node:crypto';
import type { Request } from 'express';
import { loadEnv } from '../config/env';

/**
 * Operator-console guard: a static ops token (ADMIN_API_TOKEN, ≥24 chars)
 * passed as `x-admin-token`. Deliberately separate from user JWTs — operators
 * are not users, and user tokens must never open admin surfaces. When the
 * env is unset the whole admin API is disabled (503), which is the default.
 */
@Injectable()
export class AdminGuard implements CanActivate {
  canActivate(context: ExecutionContext): boolean {
    const configured = loadEnv().ADMIN_API_TOKEN;
    if (!configured) {
      throw new ServiceUnavailableException('관리자 API가 비활성화되어 있습니다.');
    }
    const request = context.switchToHttp().getRequest<Request>();
    const provided = request.headers['x-admin-token'];
    if (typeof provided !== 'string' || !this.matches(provided, configured)) {
      throw new UnauthorizedException('관리자 인증에 실패했습니다.');
    }
    return true;
  }

  private matches(provided: string, configured: string): boolean {
    const a = Buffer.from(provided);
    const b = Buffer.from(configured);
    return a.length === b.length && timingSafeEqual(a, b);
  }
}
