import { api } from './client';
import type { UserMemory } from './types';

export function getUserMemory(): Promise<UserMemory> {
  return api.get<UserMemory>('/memory');
}

export function clearUserMemory(
  lane: 'persona' | 'knowledge' | 'all',
): Promise<UserMemory> {
  return api.post<UserMemory>('/memory', { lane });
}
