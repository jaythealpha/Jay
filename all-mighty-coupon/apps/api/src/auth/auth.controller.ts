import { Body, Controller, Get, HttpCode, Post } from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import { z } from 'zod';
import { ZodValidationPipe } from '../common/pipes/zod-validation.pipe';
import { AuthService, type AuthResult } from './auth.service';
import { CurrentUser } from './current-user.decorator';
import type { AuthenticatedUser } from './jwt-auth.guard';
import { Public } from './public.decorator';

const credentialsSchema = z
  .object({
    email: z.string().email('올바른 이메일 형식이 아닙니다'),
    password: z.string().min(8, '비밀번호는 8자 이상이어야 합니다').max(200),
  })
  .strict();

type Credentials = z.infer<typeof credentialsSchema>;

@ApiTags('auth')
@Controller('v1/auth')
export class AuthController {
  constructor(private readonly authService: AuthService) {}

  @Public()
  @Post('register')
  @ApiOperation({ summary: 'Register with email + password' })
  async register(
    @Body(new ZodValidationPipe(credentialsSchema)) body: Credentials,
  ): Promise<AuthResult> {
    return this.authService.register(body.email, body.password);
  }

  @Public()
  @Post('login')
  @HttpCode(200)
  @ApiOperation({ summary: 'Login, returns a bearer token' })
  async login(
    @Body(new ZodValidationPipe(credentialsSchema)) body: Credentials,
  ): Promise<AuthResult> {
    return this.authService.login(body.email, body.password);
  }

  @Get('me')
  @ApiOperation({ summary: 'Current authenticated user' })
  me(@CurrentUser() user: AuthenticatedUser): AuthenticatedUser {
    return user;
  }
}
