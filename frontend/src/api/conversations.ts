import { API_BASE, ApiError, USER_ID, api } from './client';
import { t } from '../i18n/core';
import type {
  ConversationCloseResponse,
  ConversationDetail,
  ConversationStatus,
  ConversationSummary,
  ConversationCaptureResult,
  ExecutionStep,
  NoteExtractResult,
  Page,
  SettleKind,
  SettleProposal,
  SettleRunResult,
} from './types';

export interface ListConversationsParams {
  limit?: number;
  offset?: number;
  status?: ConversationStatus;
  search?: string;
}

export function listConversations(
  params: ListConversationsParams = {},
): Promise<Page<ConversationSummary>> {
  return api.get<Page<ConversationSummary>>('/conversations', {
    limit: params.limit ?? 20,
    offset: params.offset ?? 0,
    status: params.status,
    search: params.search,
  });
}

export function getConversation(id: string): Promise<ConversationDetail> {
  return api.get<ConversationDetail>(`/conversations/${id}`);
}

export function createConversation(
  title?: string,
): Promise<ConversationSummary> {
  return api.post<ConversationSummary>('/conversations', {
    title: title ?? null,
  });
}

export function renameConversation(
  id: string,
  title: string,
): Promise<ConversationSummary> {
  return api.patch<ConversationSummary>(`/conversations/${id}`, { title });
}

export function deleteConversation(id: string): Promise<void> {
  return api.delete<void>(`/conversations/${id}`);
}

export function closeConversation(
  id: string,
): Promise<ConversationCloseResponse> {
  return api.post<ConversationCloseResponse>(`/conversations/${id}/close`);
}

export function extractTutorNotes(
  id: string,
  force = false,
): Promise<NoteExtractResult> {
  return api.post<NoteExtractResult>(
    `/conversations/${id}/extract-notes`,
    undefined,
    { force: force || undefined },
  );
}

export function captureConversation(
  id: string,
  force = false,
): Promise<ConversationCaptureResult> {
  return api.post<ConversationCaptureResult>(
    `/conversations/${id}/capture`,
    undefined,
    { force: force || undefined },
  );
}

export function proposeSettle(id: string): Promise<SettleProposal> {
  return api.post<SettleProposal>(`/conversations/${id}/settle/propose`);
}

export type SettleStreamEvent =
  | {
      type: 'step_start';
      node: string;
      kind: string;
      title: string;
      status?: string;
    }
  | {
      type: 'step_end';
      node: string;
      kind?: string;
      title?: string;
      status?: string;
      detail?: string;
      elapsed_ms?: number;
      execution_trace?: ExecutionStep[];
    }
  | (SettleRunResult & { type: 'done'; execution_trace?: ExecutionStep[] })
  | {
      type: 'error';
      code?: string;
      message: string;
      details?: Record<string, unknown>;
    };

export function applySettleTrace(
  prev: ExecutionStep[],
  ev: SettleStreamEvent,
): ExecutionStep[] {
  if (ev.type === 'step_start') {
    const rest = prev.filter((step) => step.status !== 'running');
    return [
      ...rest,
      {
        kind: ev.kind,
        title: ev.title,
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

export async function runSettleStream(
  id: string,
  kinds: SettleKind[],
  onEvent: (event: SettleStreamEvent) => void,
): Promise<SettleRunResult> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/conversations/${id}/settle/run`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': USER_ID,
      },
      body: JSON.stringify({ kinds }),
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
    throw await settleErrorFromResponse(response);
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
  let donePayload: SettleRunResult | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) {
      const event = parseSettleSseChunk(chunk);
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
    throw new ApiError(502, 'http_error', t('settle.runFailed'));
  }
  return donePayload;
}

function parseSettleSseChunk(chunk: string): SettleStreamEvent | null {
  const dataLines: string[] = [];
  for (const line of chunk.split('\n')) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) return null;
  try {
    const parsed = JSON.parse(dataLines.join('\n')) as SettleStreamEvent;
    return parsed?.type ? parsed : null;
  } catch {
    return null;
  }
}

async function settleErrorFromResponse(response: Response): Promise<ApiError> {
  const text = await response.text();
  try {
    const body = JSON.parse(text) as {
      error?: {
        code?: string;
        message?: string;
        request_id?: string;
        details?: Record<string, unknown>;
      };
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
