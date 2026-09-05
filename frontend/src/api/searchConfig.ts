import { api } from './client';
import type {
  SearchConfigResponse,
  SearchConfigUpdate,
  SearchTestResponse,
} from './types';

export function getSearchConfig(): Promise<SearchConfigResponse> {
  return api.get<SearchConfigResponse>('/search/config');
}

export function updateSearchConfig(
  payload: SearchConfigUpdate,
): Promise<SearchConfigResponse> {
  return api.put<SearchConfigResponse>('/search/config', payload);
}

export function resetSearchConfig(): Promise<SearchConfigResponse> {
  return api.post<SearchConfigResponse>('/search/reset');
}

export function testSearch(query?: string): Promise<SearchTestResponse> {
  return api.post<SearchTestResponse>('/search/test', {
    query: query || 'OpenAI',
    max_results: 3,
  });
}
