import { API_BASE, ApiError, USER_ID, api } from './client';
import { t } from '../i18n/core';
import type { ChatResponse, ExecutionStep, HealthResponse } from './types';

export type ChatStreamEvent =
  | { type: 'start'; conversation_id: string }
  | { type: 'token'; text: string }
  | { type: 'token_clear' }
  | {
      type: 'step_start';
      node: string;
      kind: string;
      title: string;
      tool?: string;
      status?: string;
    }
  | {
      type: 'step_end';
      node: string;
      kind?: string;
      title?: string;
      tool?: string;
      elapsed_ms?: number;
      status?: string;
      execution_trace?: ExecutionStep[];
    }
  | (ChatResponse & { type: 'done' })
  | {
      type: 'error';
      code?: string;
      message: string;
      details?: Record<string, unknown>;
    };

export function sendMessage(
  message: string,
  conversationId?: string | null,
  files?: File[],
  modeId?: string | null,
  providerId?: string | null,
): Promise<ChatResponse> {
  if (files?.length) {
    const form = new FormData();
    form.append('message', message || '');
    if (conversationId) form.append('conversation_id', conversationId);
    if (!conversationId && modeId) form.append('mode_id', modeId);
    if (providerId) form.append('provider_id', providerId);
    for (const file of files) {
      form.append('files', file);
    }
    return api.postForm<ChatResponse>('/chat', form);
  }
  return api.post<ChatResponse>('/chat', {
    message,
    conversation_id: conversationId ?? null,
    ...(conversationId ? {} : { mode_id: modeId ?? null }),
    ...(providerId ? { provider_id: providerId } : {}),
  });
}

export function getHealth(): Promise<HealthResponse> {
  return api.get<HealthResponse>('/health');
}

export function applyLiveTrace(
  prev: ExecutionStep[],
  ev: ChatStreamEvent,
): ExecutionStep[] {
  if (ev.type === 'token' && ev.text) {
    for (let i = prev.length - 1; i >= 0; i -= 1) {
      const step = prev[i];
      if (step.status === 'running' && step.kind === 'think') {
        const next = prev.slice();
        next[i] = { ...step, detail: `${step.detail || ''}${ev.text}` };
        return next;
      }
    }
    return prev;
  }
  if (ev.type === 'step_start') {
    const rest = prev.filter((step) => step.status !== 'running');
    return [
      ...rest,
      {
        kind: ev.kind,
        title: ev.title,
        tool: ev.tool,
        status: 'running',
        started_at: Date.now(),
      },
    ];
  }
  if (ev.type === 'step_end' && Array.isArray(ev.execution_trace)) {
    return ev.execution_trace;
  }
  return prev;
}

export async function sendMessageStream(
  message: string,
  conversationId: string | null | undefined,
  files: File[] | undefined,
  onEvent: (event: ChatStreamEvent) => void,
  modeId?: string | null,
  providerId?: string | null,
): Promise<ChatResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/chat/stream`, {
      method: 'POST',
      credentials: 'include',
      headers: streamHeaders(files),
      body: streamBody(message, conversationId, files, modeId, providerId),
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

  const contentType = response.headers.get('content-type') || '';
  if (!response.ok) {
    throw await errorFromResponse(response);
  }
  if (!contentType.includes('text/event-stream') || !response.body) {
    throw new ApiError(
      response.status,
      'http_error',
      t('api.http', { status: response.status }),
    );
  }

  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';
  let donePayload: ChatResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) {
      const event = parseSseChunk(chunk);
      if (!event) continue;
      onEvent(event);
      if (event.type === 'done') {
        donePayload = event;
      }
      if (event.type === 'error') {
        throw new ApiError(
          502,
          event.code || 'http_error',
          event.message,
          undefined,
          event.details,
        );
      }
    }
  }

  if (!donePayload) {
    throw new ApiError(502, 'http_error', t('chat.sendFailed'));
  }
  return donePayload;
}

function streamHeaders(files?: File[]): HeadersInit {
  if (files?.length) {
    return { 'X-User-Id': USER_ID };
  }
  return {
    'Content-Type': 'application/json',
    'X-User-Id': USER_ID,
  };
}

function streamBody(
  message: string,
  conversationId: string | null | undefined,
  files?: File[],
  modeId?: string | null,
  providerId?: string | null,
): BodyInit {
  if (files?.length) {
    const form = new FormData();
    form.append('message', message || '');
    if (conversationId) form.append('conversation_id', conversationId);
    if (!conversationId && modeId) form.append('mode_id', modeId);
    if (providerId) form.append('provider_id', providerId);
    for (const file of files) {
      form.append('files', file);
    }
    return form;
  }
  return JSON.stringify({
    message,
    conversation_id: conversationId ?? null,
    ...(conversationId ? {} : { mode_id: modeId ?? null }),
    ...(providerId ? { provider_id: providerId } : {}),
  });
}

function parseSseChunk(chunk: string): ChatStreamEvent | null {
  const dataLines: string[] = [];
  for (const line of chunk.split('\n')) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) return null;
  try {
    const parsed = JSON.parse(dataLines.join('\n')) as ChatStreamEvent;
    return parsed?.type ? parsed : null;
  } catch {
    return null;
  }
}

async function errorFromResponse(response: Response): Promise<ApiError> {
  const text = await response.text();
  try {
    const body = JSON.parse(text) as {
      error?: { code?: string; message?: string; request_id?: string; details?: Record<string, unknown> };
    };
    const err = body?.error;
    return new ApiError(
      response.status,
      err?.code ?? 'http_error',
      err?.message ?? t('api.http', { status: response.status }),
      err?.request_id,
      err?.details,
    );
  } catch {
    return new ApiError(
      response.status,
      'http_error',
      t('api.http', { status: response.status }),
    );
  }
}
