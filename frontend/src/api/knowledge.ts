import { API_BASE, ApiError, USER_ID, api } from './client';
import { t } from '../i18n/core';
import type { ExecutionStep } from './types';

export type SearchMode = 'keyword' | 'fulltext' | 'hybrid' | 'vector';
export type GraphNodeType = 'knowledge' | 'keyword' | 'category';

export interface Keyword {
  id: string;
  name: string;
  slug: string;
  usage_count: number;
}

export interface Attachment {
  id: string;
  knowledge_id: string;
  filename: string;
  extension: string;
  mime_type: string;
  size_bytes: number;
  created_time: string;
  updated_time: string;
}

export interface OutlineTocItem {
  level: number;
  text: string;
}

export interface KnowledgeOutline {
  toc?: OutlineTocItem[];
  code_languages?: string[];
  counts?: Record<string, number>;
}

export interface KnowledgeSummary {
  id: string;
  title: string;
  summary: string | null;
  category: string | null;
  is_favorite: boolean;
  is_important: boolean;
  is_archived: boolean;
  source_type: string;
  source_filename: string | null;
  word_count: number;
  reading_minutes: number;
  analysis_status: string;
  attachment_count: number;
  keywords: Keyword[];
  created_time: string;
  updated_time: string;
}

export interface KnowledgeDetail extends Omit<KnowledgeSummary, 'attachment_count'> {
  markdown_content: string;
  outline: KnowledgeOutline;
  analysis_error: string | null;
  analyzed_by_model: string | null;
  metadata: Record<string, unknown>;
  attachments: Attachment[];
}

export interface KnowledgePage<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface CategoryStat {
  name: string;
  count: number;
}

export interface KnowledgeImportResult {
  knowledge: KnowledgeDetail;
  imported_attachments: number;
  warnings: string[];
}

export interface KnowledgeCreatePayload {
  title: string;
  markdown_content?: string;
  summary?: string | null;
  category?: string | null;
  is_favorite?: boolean;
  is_important?: boolean;
}

export interface KnowledgeUpdatePayload {
  title?: string;
  markdown_content?: string;
  summary?: string | null;
  category?: string | null;
  is_favorite?: boolean;
  is_important?: boolean;
  is_archived?: boolean;
}

export interface DashboardStats {
  knowledge_total: number;
  keyword_total: number;
  attachment_total: number;
  favorite_total: number;
  important_total: number;
  category_total: number;
  model_config_total: number;
  pending_total?: number;
}

export interface SearchHit extends KnowledgeSummary {
  score: number;
  match_fields: string[];
  snippet: string | null;
  matched_keywords: string[];
}

export interface SearchResponse {
  query: string;
  mode: SearchMode;
  total: number;
  page: number;
  page_size: number;
  items: SearchHit[];
  note: string | null;
}

export interface KeywordStat {
  id: string;
  name: string;
  slug: string;
  usage_count: number;
  sample_title: string | null;
}

export interface Citation {
  id: string;
  title: string;
  summary: string | null;
  score: number;
  match_fields: string[];
}

export interface AssistantAskResponse {
  answer: string;
  citations: Citation[];
  source: 'ai' | 'local';
  model: string | null;
  latency_ms: number | null;
  execution_trace?: ExecutionStep[];
}

export type AssistantStreamEvent =
  | { type: 'token'; text: string }
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
      elapsed_ms?: number;
      status?: string;
      execution_trace?: ExecutionStep[];
    }
  | (AssistantAskResponse & { type: 'done' })
  | {
      type: 'error';
      code?: string;
      message: string;
      details?: Record<string, unknown>;
    };

export interface GraphNode {
  id: string;
  type: GraphNodeType;
  label: string;
  weight: number;
  meta: Record<string, unknown>;
}

export interface GraphEdge {
  id: string;
  source: string;
  target: string;
  type: 'has_keyword' | 'in_category' | 'co_occur';
  weight: number;
}

export interface GraphStats {
  knowledge: number;
  keyword: number;
  category: number;
  edges: number;
  knowledge_in_db: number;
}

export interface GraphResponse {
  nodes: GraphNode[];
  edges: GraphEdge[];
  stats: GraphStats;
}

export interface AnalysisResult {
  knowledge_id: string;
  analysis_status: string;
  summary: string | null;
  category: string | null;
  keywords: string[];
  analyzed_by_model: string | null;
  analysis_error: string | null;
  source: string;
}

export function listKnowledge(params: {
  page?: number;
  page_size?: number;
  q?: string;
  category?: string;
  is_favorite?: boolean;
  is_important?: boolean;
  include_archived?: boolean;
  pending_import?: boolean;
}) {
  return api.get<KnowledgePage<KnowledgeSummary>>('/knowledge', params);
}

export function listCategories() {
  return api.get<CategoryStat[]>('/knowledge/categories');
}

export function getKnowledge(id: string) {
  return api.get<KnowledgeDetail>(`/knowledge/${id}`);
}

export function createKnowledge(payload: KnowledgeCreatePayload) {
  return api.post<KnowledgeDetail>('/knowledge', payload);
}

export function updateKnowledge(id: string, payload: KnowledgeUpdatePayload) {
  return api.patch<KnowledgeDetail>(`/knowledge/${id}`, payload);
}

export function deleteKnowledge(id: string) {
  return api.delete<void>(`/knowledge/${id}`);
}

export function toggleFavorite(id: string) {
  return api.post<KnowledgeDetail>(`/knowledge/${id}/favorite`);
}

export function toggleImportant(id: string) {
  return api.post<KnowledgeDetail>(`/knowledge/${id}/important`);
}

export function toggleArchive(id: string) {
  return api.post<KnowledgeDetail>(`/knowledge/${id}/archive`);
}

export function importMarkdown(form: FormData) {
  return api.postForm<KnowledgeImportResult>('/knowledge/import', form);
}

export function confirmKnowledgeImport(id: string) {
  return api.post<KnowledgeDetail>(`/knowledge/${id}/confirm-import`);
}

export function analyzeKnowledge(id: string, forceLocal = false) {
  return api.post<AnalysisResult>(
    `/knowledge/${id}/analyze`,
    undefined,
    { force_local: forceLocal || undefined },
  );
}

export function listAttachments(knowledgeId: string) {
  return api.get<Attachment[]>(`/knowledge/${knowledgeId}/attachments`);
}

export function uploadAttachment(knowledgeId: string, file: File) {
  const form = new FormData();
  form.append('file', file);
  return api.postForm<Attachment>(`/knowledge/${knowledgeId}/attachments`, form);
}

export function deleteAttachment(attachmentId: string) {
  return api.delete<void>(`/attachments/${attachmentId}`);
}

export function attachmentDownloadUrl(attachmentId: string) {
  return `/api/v1/attachments/${attachmentId}/download`;
}

export function searchKnowledge(params: {
  q: string;
  mode?: SearchMode;
  page?: number;
  page_size?: number;
  category?: string;
}) {
  return api.get<SearchResponse>('/search', params);
}

export function fetchHotKeywords(limit = 24) {
  return api.get<KeywordStat[]>('/search/keywords/hot', { limit });
}

export function rebuildEmbeddings() {
  return api.post<{ success: boolean; message: string }>(
    '/search/embeddings/rebuild',
  );
}

export function fetchKnowledgeGraph(params?: {
  max_keywords?: number;
  max_knowledge?: number;
  min_keyword_usage?: number;
}) {
  return api.get<GraphResponse>('/graph', params);
}

export function askAssistant(payload: {
  message: string;
  history?: { role: 'user' | 'assistant'; content: string }[];
  top_k?: number;
}) {
  return api.post<AssistantAskResponse>('/assistant/ask', payload);
}

export async function askAssistantStream(
  payload: {
    message: string;
    history?: { role: 'user' | 'assistant'; content: string }[];
    top_k?: number;
  },
  onEvent: (event: AssistantStreamEvent) => void,
): Promise<AssistantAskResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE}/assistant/ask/stream`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
        'X-User-Id': USER_ID,
      },
      body: JSON.stringify(payload),
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
    const text = await response.text();
    try {
      const body = JSON.parse(text) as {
        error?: { code?: string; message?: string; details?: Record<string, unknown> };
      };
      throw new ApiError(
        response.status,
        body.error?.code ?? 'http_error',
        body.error?.message ?? t('api.http', { status: response.status }),
        undefined,
        body.error?.details,
      );
    } catch (err) {
      if (err instanceof ApiError) throw err;
      throw new ApiError(
        response.status,
        'http_error',
        t('api.http', { status: response.status }),
      );
    }
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
  let donePayload: AssistantAskResponse | null = null;

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    const chunks = buffer.split('\n\n');
    buffer = chunks.pop() ?? '';
    for (const chunk of chunks) {
      const event = parseAssistantSse(chunk);
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
    throw new ApiError(502, 'http_error', t('km.askFailed'));
  }
  return donePayload;
}

function parseAssistantSse(chunk: string): AssistantStreamEvent | null {
  const dataLines: string[] = [];
  for (const line of chunk.split('\n')) {
    if (line.startsWith('data:')) {
      dataLines.push(line.slice(5).trimStart());
    }
  }
  if (!dataLines.length) return null;
  try {
    const parsed = JSON.parse(dataLines.join('\n')) as AssistantStreamEvent;
    return parsed?.type ? parsed : null;
  } catch {
    return null;
  }
}

export function fetchKnowledgeStats() {
  return api.get<DashboardStats>('/system/stats');
}
