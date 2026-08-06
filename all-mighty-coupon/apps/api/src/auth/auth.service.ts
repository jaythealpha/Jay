import { ConflictException, Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import { PrismaService } from '../prisma/prisma.service';
import type { JwtPayload } from './jwt-auth.guard';
import { hashPassword, verifyPassword } from './password';

export interface AuthResult {
  accessToken: string;
  user: { id: string; email: string };
}

@Injectable()
export class AuthService {
  constructor(
    private readonly prisma: PrismaService,
    private readonly jwtService: JwtService,
  ) {}

  async register(email: string, password: string): Promise<AuthResult> {
    const normalized = email.trim().toLowerCase();
    const existing = await this.prisma.user.findUnique({ where: { email: normalized } });
    if (existing && existing.passwordHash !== null) {
      throw new ConflictException('이미 가입된 이메일입니다.');
    }
    // Legacy seed users (passwordHash null) claim their account on first
    // register instead of being blocked by the unique email constraint.
    const user = existing
      ? await this.prisma.user.update({
          where: { id: existing.id },
          data: { passwordHash: hashPassword(password) },
        })
      : await this.prisma.user.create({
          data: { email: normalized, passwordHash: hashPassword(password) },
        });
    return this.issueTokens(user.id, user.email);
  }

  async login(email: string, password: string): Promise<AuthResult> {
    const user = await this.prisma.user.findUnique({
      where: { email: email.trim().toLowerCase() },
    });
    // One generic message for unknown email / wrong password / legacy user —
    // no account-existence oracle.
    if (!user || user.passwordHash === null || !verifyPassword(password, user.passwordHash)) {
      throw new UnauthorizedException('이메일 또는 비밀번호가 올바르지 않습니다.');
    }
    return this.issueTokens(user.id, user.email);
  }

  private async issueTokens(id: string, email: string): Promise<AuthResult> {
    const payload: JwtPayload = { sub: id, email };
    return {
      accessToken: await this.jwtService.signAsync(payload),
      user: { id, email },
    };
  }
}
