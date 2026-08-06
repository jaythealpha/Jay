import { Body, Controller, Delete, HttpCode, Post } from '@nestjs/common';
import { ApiBearerAuth, ApiOperation, ApiTags } from '@nestjs/swagger';
import { z } from 'zod';
import { CurrentUser } from '../auth/current-user.decorator';
import type { AuthenticatedUser } from '../auth/jwt-auth.guard';
import { ZodValidationPipe } from '../common/pipes/zod-validation.pipe';
import { PrismaService } from '../prisma/prisma.service';

const registerSchema = z
  .object({
    token: z.string().min(10).max(4096),
    platform: z.enum(['ANDROID', 'IOS']),
  })
  .strict();

const unregisterSchema = z.object({ token: z.string().min(10).max(4096) }).strict();

type RegisterBody = z.infer<typeof registerSchema>;
type UnregisterBody = z.infer<typeof unregisterSchema>;

@ApiTags('devices')
@ApiBearerAuth()
@Controller('v1/devices')
export class DevicesController {
  constructor(private readonly prisma: PrismaService) {}

  @Post()
  @HttpCode(204)
  @ApiOperation({ summary: 'Register this device for expiration push notifications' })
  async register(
    @CurrentUser() user: AuthenticatedUser,
    @Body(new ZodValidationPipe(registerSchema)) body: RegisterBody,
  ): Promise<void> {
    // A token can move between accounts (re-login on the same phone) — the
    // last registration wins.
    await this.prisma.pushDevice.upsert({
      where: { token: body.token },
      update: { userId: user.id, platform: body.platform, lastSeenAt: new Date() },
      create: { userId: user.id, token: body.token, platform: body.platform },
    });
  }

  @Delete()
  @HttpCode(204)
  @ApiOperation({ summary: 'Unregister a device (logout / permission revoked)' })
  async unregister(
    @CurrentUser() user: AuthenticatedUser,
    @Body(new ZodValidationPipe(unregisterSchema)) body: UnregisterBody,
  ): Promise<void> {
    await this.prisma.pushDevice.deleteMany({ where: { token: body.token, userId: user.id } });
  }
}
