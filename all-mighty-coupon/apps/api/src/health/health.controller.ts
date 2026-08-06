import { Controller, Get } from '@nestjs/common';
import { ApiOperation, ApiTags } from '@nestjs/swagger';
import type { HealthResponseDto } from '@amc/shared-types';
import { Public } from '../auth/public.decorator';
import { HealthService } from './health.service';

@ApiTags('health')
@Public()
@Controller('health')
export class HealthController {
  constructor(private readonly healthService: HealthService) {}

  @Get()
  @ApiOperation({ summary: 'Liveness + dependency health (database, redis)' })
  async check(): Promise<HealthResponseDto> {
    return this.healthService.check();
  }
}
