import { CallHandler, ExecutionContext, Injectable, Logger, NestInterceptor } from '@nestjs/common';
import { randomUUID } from 'node:crypto';
import type { Request, Response } from 'express';
import { Observable, tap } from 'rxjs';

/**
 * Request logging: method, path, status, duration, requestId — never bodies,
 * never query values (they could contain search text or coupon numbers).
 */
@Injectable()
export class LoggingInterceptor implements NestInterceptor {
  private readonly logger = new Logger('HTTP');

  intercept(context: ExecutionContext, next: CallHandler): Observable<unknown> {
    const http = context.switchToHttp();
    const request = http.getRequest<Request & { requestId?: string }>();
    const response = http.getResponse<Response>();
    const requestId = randomUUID();
    request.requestId = requestId;
    response.setHeader('x-request-id', requestId);

    const started = Date.now();
    return next.handle().pipe(
      tap({
        next: () => this.log(request, response.statusCode, started, requestId),
        error: () => this.log(request, response.statusCode || 500, started, requestId),
      }),
    );
  }

  private log(request: Request, status: number, started: number, requestId: string): void {
    const duration = Date.now() - started;
    this.logger.log(`${request.method} ${request.path} ${status} ${duration}ms [${requestId}]`);
  }
}
