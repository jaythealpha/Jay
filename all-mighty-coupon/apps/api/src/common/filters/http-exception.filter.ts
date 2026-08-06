import {
  ArgumentsHost,
  Catch,
  ExceptionFilter,
  HttpException,
  HttpStatus,
  Logger,
} from '@nestjs/common';
import type { Request, Response } from 'express';
import type { ApiErrorBody } from '@amc/shared-types';

const STATUS_CODES: Record<number, string> = {
  400: 'BAD_REQUEST',
  401: 'UNAUTHORIZED',
  403: 'FORBIDDEN',
  404: 'NOT_FOUND',
  409: 'CONFLICT',
  422: 'UNPROCESSABLE',
  429: 'RATE_LIMITED',
};

/**
 * Single error envelope for every failure. User-facing messages never carry
 * stack traces or internal error details; those go to the server log only.
 */
@Catch()
export class GlobalExceptionFilter implements ExceptionFilter {
  private readonly logger = new Logger(GlobalExceptionFilter.name);

  catch(exception: unknown, host: ArgumentsHost): void {
    const ctx = host.switchToHttp();
    const response = ctx.getResponse<Response>();
    const request = ctx.getRequest<Request & { requestId?: string }>();
    const requestId = request.requestId;

    if (exception instanceof HttpException) {
      const status = exception.getStatus();
      const body: ApiErrorBody = {
        error: {
          code: STATUS_CODES[status] ?? 'HTTP_ERROR',
          message: this.safeMessage(exception),
          ...(requestId ? { requestId } : {}),
        },
      };
      response.status(status).json(body);
      return;
    }

    const stack = exception instanceof Error ? exception.stack : String(exception);
    this.logger.error(`Unhandled exception (requestId=${requestId ?? 'n/a'})`, stack);
    const body: ApiErrorBody = {
      error: {
        code: 'INTERNAL_ERROR',
        message: '일시적인 오류가 발생했습니다. 잠시 후 다시 시도해 주세요.',
        ...(requestId ? { requestId } : {}),
      },
    };
    response.status(HttpStatus.INTERNAL_SERVER_ERROR).json(body);
  }

  private safeMessage(exception: HttpException): string {
    const res = exception.getResponse();
    if (typeof res === 'string') return res;
    if (typeof res === 'object' && res !== null && 'message' in res) {
      const message = (res as { message: unknown }).message;
      if (typeof message === 'string') return message;
      if (Array.isArray(message)) return message.join(', ');
    }
    return exception.message;
  }
}
