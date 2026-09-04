import { api } from './client';
import type {
  GenerateSkillResponse,
  Page,
  ReindexResponse,
  SkillCreatePayload,
  SkillDetail,
  SkillSearchResponse,
  SkillStatus,
  SkillSummary,
  SkillUpdatePayload,
} from './types';

export interface ListSkillsParams {
  limit?: number;
  offset?: number;
  status?: SkillStatus;
  search?: string;
}

export function listSkills(
  params: ListSkillsParams = {},
): Promise<Page<SkillSummary>> {
  return api.get<Page<SkillSummary>>('/skills', {
    limit: params.limit ?? 20,
    offset: params.offset ?? 0,
    status: params.status,
    search: params.search,
  });
}

export function getSkill(id: string): Promise<SkillDetail> {
  return api.get<SkillDetail>(`/skills/${id}`);
}

export function createSkill(
  payload: SkillCreatePayload,
): Promise<SkillDetail> {
  return api.post<SkillDetail>('/skills', payload);
}

export function updateSkill(
  id: string,
  payload: SkillUpdatePayload,
): Promise<SkillDetail> {
  return api.put<SkillDetail>(`/skills/${id}`, payload);
}

export function setSkillStatus(
  id: string,
  status: SkillStatus,
): Promise<SkillDetail> {
  return api.patch<SkillDetail>(`/skills/${id}/status`, { status });
}

export function deleteSkill(id: string): Promise<void> {
  return api.delete<void>(`/skills/${id}`);
}

export function generateSkill(
  conversationId: string,
  force = false,
): Promise<GenerateSkillResponse> {
  return api.post<GenerateSkillResponse>('/skills/generate', {
    conversation_id: conversationId,
    force,
  });
}

export function searchSkills(
  query: string,
  limit = 5,
): Promise<SkillSearchResponse> {
  return api.post<SkillSearchResponse>('/skills/search', { query, limit });
}

export function reindexSkills(force = false): Promise<ReindexResponse> {
  return api.post<ReindexResponse>(`/skills/reindex?force=${force}`);
}

export interface SkillPackSummary {
  id: string;
  name: string;
  description: string;
  tags: string[];
  skill_count: number;
}

export interface SkillImportResult {
  pack_id?: string | null;
  pack_name?: string | null;
  created: SkillSummary[];
  skipped: string[];
  total_created: number;
  total_skipped: number;
}

export function listSkillPacks(): Promise<{
  items: SkillPackSummary[];
  total: number;
}> {
  return api.get('/skills/packs');
}

export function importSkillPack(payload: {
  pack_id?: string;
  skills?: SkillCreatePayload[];
  activate?: boolean;
  skip_duplicates?: boolean;
}): Promise<SkillImportResult> {
  return api.post<SkillImportResult>('/skills/import', payload);
}

export interface PackArchivePreview {
  format: string;
  pack_id: string;
  version: string;
  name: string;
  description: string;
  origin?: string | null;
  source_url?: string | null;
  permissions_requested: string[];
  tags: string[];
  skills: Array<{
    key: string;
    name: string;
    description: string;
    tools_local: string[];
    tools_local_exposed: string[];
    tools_builtin: string[];
  }>;
  warnings: string[];
  errors: string[];
}

export interface InstalledPackSummary {
  id: string;
  pack_id: string;
  version: string;
  name: string;
  description: string;
  format?: string;
  status: string;
  permissions: string[];
  permissions_requested: string[];
  tags: string[];
  content_hash: string;
  created_at: string;
  updated_at: string;
  tool_count: number;
  skill_count: number;
}

export interface PackArchiveImportResult {
  pack: InstalledPackSummary & {
    tools?: Array<{
      id: string;
      name: string;
      exposed_name: string;
      description: string;
      enabled: boolean;
    }>;
  };
  created_skills: SkillSummary[];
  replaced_pack_id?: string | null;
  warnings: string[];
}

export function previewPackArchive(file: File): Promise<PackArchivePreview> {
  const form = new FormData();
  form.append('file', file);
  return api.postForm<PackArchivePreview>('/pack-archives/preview', form);
}

export function importPackArchive(
  file: File,
  opts: {
    grant_permissions: string[];
    activate?: boolean;
    replace_existing?: boolean;
  },
): Promise<PackArchiveImportResult> {
  const form = new FormData();
  form.append('file', file);
  form.append('grant_permissions', JSON.stringify(opts.grant_permissions));
  form.append('activate', String(opts.activate ?? true));
  form.append('replace_existing', String(opts.replace_existing ?? true));
  return api.postForm<PackArchiveImportResult>('/pack-archives', form);
}

export function listInstalledPacks(): Promise<InstalledPackSummary[]> {
  return api.get<InstalledPackSummary[]>('/pack-archives');
}

export function setInstalledPackStatus(
  id: string,
  status: 'active' | 'disabled',
): Promise<InstalledPackSummary> {
  return api.patch(`/pack-archives/${id}`, { status });
}

export function uninstallPack(id: string): Promise<{ ok: boolean }> {
  return api.delete(`/pack-archives/${id}`);
}

export function previewPluginUrl(url: string): Promise<PackArchivePreview> {
  return api.post<PackArchivePreview>('/plugins/preview-url', { url });
}

export function importPluginUrl(
  url: string,
  opts: {
    grant_permissions?: string[];
    activate?: boolean;
    replace_existing?: boolean;
  } = {},
): Promise<PackArchiveImportResult> {
  return api.post<PackArchiveImportResult>('/plugins/from-url', {
    url,
    grant_permissions: opts.grant_permissions ?? null,
    activate: opts.activate ?? true,
    replace_existing: opts.replace_existing ?? true,
  });
}

export function sendSkillFeedback(
  id: string,
  feedback: 'positive' | 'negative',
  messageId?: string,
): Promise<{ ok: boolean; message?: string }> {
  return api.post(`/skills/${id}/feedback`, {
    feedback,
    message_id: messageId ?? null,
  });
}
