import { api } from './client';
import type { ShellConfigResponse, ShellConfigUpdate } from './types';

export function getShellConfig(): Promise<ShellConfigResponse> {
  return api.get<ShellConfigResponse>('/shell/config');
}

export function updateShellConfig(
  payload: ShellConfigUpdate,
): Promise<ShellConfigResponse> {
  return api.put<ShellConfigResponse>('/shell/config', payload);
}

export function resetShellConfig(): Promise<ShellConfigResponse> {
  return api.post<ShellConfigResponse>('/shell/reset');
}
