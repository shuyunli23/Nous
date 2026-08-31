import { api } from './client';
import type {
  LLMConfigResponse,
  OkResponse,
  ProviderCreatePayload,
  ProviderPayload,
  ProviderTestResponse,
  LLMRoutes,
} from './types';

/**
 * Every mutation returns the whole configuration, so the page always renders
 * from one authoritative snapshot instead of patching local state by hand.
 */

export function getLLMConfig(): Promise<LLMConfigResponse> {
  return api.get<LLMConfigResponse>('/llm/config');
}

export function createProvider(
  payload: ProviderCreatePayload,
): Promise<LLMConfigResponse> {
  return api.post<LLMConfigResponse>('/llm/providers', payload);
}

/** Omitted keys keep their stored value; pass `''` to clear a credential. */
export function updateProvider(
  id: string,
  payload: ProviderPayload,
): Promise<LLMConfigResponse> {
  return api.put<LLMConfigResponse>(`/llm/providers/${id}`, payload);
}

export function deleteProvider(id: string): Promise<LLMConfigResponse> {
  return api.delete<LLMConfigResponse>(`/llm/providers/${id}`);
}

export function activateProvider(id: string): Promise<LLMConfigResponse> {
  return api.post<LLMConfigResponse>(`/llm/providers/${id}/activate`);
}

/** Drop the runtime override so the `.env` values take over again. */
export function deactivateProvider(): Promise<LLMConfigResponse> {
  return api.post<LLMConfigResponse>('/llm/deactivate');
}

export function updateRoutes(
  routes: Partial<LLMRoutes>,
): Promise<LLMConfigResponse> {
  return api.put<LLMConfigResponse>('/llm/routes', routes);
}

/** Probe a saved provider by id, or an unsaved draft, without saving it. */
export function testProvider(
  target: { providerId: string } | { draft: ProviderCreatePayload },
): Promise<ProviderTestResponse> {
  const body =
    'providerId' in target
      ? { provider_id: target.providerId }
      : { draft: target.draft };
  return api.post<ProviderTestResponse>('/llm/test', body);
}

/** Probe whatever is currently in effect, runtime provider or `.env`. */
export function testActiveProvider(): Promise<ProviderTestResponse> {
  return api.post<ProviderTestResponse>('/llm/test', {});
}

export function checkBedrockSdk(): Promise<OkResponse> {
  return api.post<OkResponse>('/llm/bedrock/check');
}
