import { t } from '../i18n/core';
import type { ApiErrorBody } from './types';

export const API_BASE = '/api/v1';

/** Local dev identity. Swap for a real token once auth exists. */
export const USER_ID = 'local-dev';

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly requestId?: string;
  readonly details?: Record<string, unknown>;

  constructor(
    status: number,
    code: string,
    message: string,
    requestId?: string,
    details?: Record<string, unknown>,
  ) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.requestId = requestId;
    this.details = details;
  }
}

async function request<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}${path}`, {
      ...init,
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': USER_ID,
        ...(init.headers ?? {}),
      },
    });
  } catch (cause) {
    // Network-level failure: the backend is unreachable.
    throw new ApiError(
      0,
      'network_error',
      t('api.network'),
      undefined,
      { cause: String(cause) },
    );
  }

  if (response.status === 204) {
    return undefined as T;
  }

  const text = await response.text();
  const payload: unknown = text ? safeJsonParse(text) : null;

  if (!response.ok) {
    const body = payload as ApiErrorBody | null;
    const err = body?.error;
    throw new ApiError(
      response.status,
      err?.code ?? 'http_error',
      err?.message ?? t('api.http', { status: response.status }),
      err?.request_id,
      err?.details,
    );
  }

  return payload as T;
}

function safeJsonParse(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return null;
  }
}

function query(params: Record<string, unknown>): string {
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== '') {
      search.set(key, String(value));
    }
  }
  const encoded = search.toString();
  return encoded ? `?${encoded}` : '';
}

export const api = {
  get: <T>(path: string, params?: Record<string, unknown>) =>
    request<T>(`${path}${params ? query(params) : ''}`, {
      method: 'GET',
      signal: AbortSignal.timeout(12_000),
    }),

  post: <T>(path: string, body?: unknown, params?: Record<string, unknown>) =>
    request<T>(`${path}${params ? query(params) : ''}`, {
      method: 'POST',
      body: body === undefined ? undefined : JSON.stringify(body),
    }),

  /** Multipart upload — do not set Content-Type (browser sets boundary). */
  postForm: async <T>(path: string, form: FormData): Promise<T> => {
    let response: Response;
    try {
      response = await fetch(`${API_BASE}${path}`, {
        method: 'POST',
        credentials: 'include',
        headers: { 'X-User-Id': USER_ID },
        body: form,
      });
    } catch (cause) {
      throw new ApiError(
        0,
        'network_error',
        t('api.network'),
        undefined,
        { cause: String(cause) },
      );
    }
    if (response.status === 204) {
      return undefined as T;
    }
    const text = await response.text();
    const payload: unknown = text ? safeJsonParse(text) : null;
    if (!response.ok) {
      const body = payload as ApiErrorBody | null;
      const err = body?.error;
      throw new ApiError(
        response.status,
        err?.code ?? 'http_error',
        err?.message ?? t('api.http', { status: response.status }),
        err?.request_id,
        err?.details,
      );
    }
    return payload as T;
  },

  put: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PUT', body: JSON.stringify(body) }),

  patch: <T>(path: string, body: unknown) =>
    request<T>(path, { method: 'PATCH', body: JSON.stringify(body) }),

  delete: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
};
