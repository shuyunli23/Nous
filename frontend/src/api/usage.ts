import { api } from './client';
import type { UsageSummary } from './types';

export function getUsageSummary(): Promise<UsageSummary> {
  return api.get<UsageSummary>('/usage');
}
