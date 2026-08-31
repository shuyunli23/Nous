import { api } from './client';
import type {
  ChatMode,
  ChatModeCreatePayload,
  ChatModeUpdatePayload,
  OkResponse,
} from './types';

export function listChatModes(): Promise<ChatMode[]> {
  return api.get<ChatMode[]>('/chat-modes');
}

export function createChatMode(
  payload: ChatModeCreatePayload,
): Promise<ChatMode> {
  return api.post<ChatMode>('/chat-modes', payload);
}

export function updateChatMode(
  id: string,
  payload: ChatModeUpdatePayload,
): Promise<ChatMode> {
  return api.patch<ChatMode>(`/chat-modes/${id}`, payload);
}

export function deleteChatMode(id: string): Promise<OkResponse> {
  return api.delete<OkResponse>(`/chat-modes/${id}`);
}
