import { SetMetadata } from '@nestjs/common';

export const IS_PUBLIC_KEY = 'amc:isPublic';

/** Marks a route as reachable without a JWT (health, auth, docs). */
export const Public = () => SetMetadata(IS_PUBLIC_KEY, true);
