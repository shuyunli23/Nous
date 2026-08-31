import { api } from './client';
import type {
  ConversationCloseResponse,
  ConversationDetail,
  ConversationStatus,
  ConversationSummary,
  ConversationCaptureResult,
  NoteExtractResult,
  Page,
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
