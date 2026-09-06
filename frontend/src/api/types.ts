/** API types mirroring the backend Pydantic schemas. */

export type ConversationStatus = 'active' | 'closed' | 'archived';
export type ExtractionStatus =
  | 'pending'
  | 'running'
  | 'done'
  | 'skipped'
  | 'failed';
export type SkillStatus = 'draft' | 'active' | 'disabled' | 'deprecated';
export type SkillSource = 'auto' | 'manual' | 'imported';
export type MessageRole = 'system' | 'user' | 'assistant' | 'tool';

export interface Page<T> {
  items: T[];
  total: number;
  limit: number;
  offset: number;
}

export interface ApiErrorBody {
  error: {
    code: string;
    message: string;
    details?: Record<string, unknown>;
    request_id?: string;
  };
}

// ── conversations ─────────────────────────────────────────────────────────

export interface TokenUsage {
  prompt_tokens?: number;
  completion_tokens?: number;
  total_tokens?: number;
}

export interface TodoItem {
  content: string;
  status: 'pending' | 'in_progress' | 'completed' | string;
}

export interface ExecutionStep {
  kind: 'skill_retrieve' | 'plan' | 'tool' | 'verify' | 'answer' | 'think' | string;
  title: string;
  detail?: string;
  status?: 'ok' | 'error' | 'info' | 'running' | string;
  tool?: string;
  call_id?: string | null;
  args?: Record<string, string>;
  count?: number;
  elapsed_ms?: number;
  /** Standing plan from todo_write / the plan node. */
  todos?: TodoItem[];
  /** Frontend-only: when the running step started (Date.now()). */
  started_at?: number;
}

export interface Message {
  id: string;
  seq: number;
  role: MessageRole;
  content: string;
  tool_calls?: Record<string, unknown>[] | null;
  token_usage?: TokenUsage | null;
  used_skill_ids?: string[] | null;
  execution_trace?: ExecutionStep[] | null;
  created_at: string;
}

export interface ConversationSummary {
  id: string;
  user_id: string;
  title: string;
  status: ConversationStatus;
  summary?: string | null;
  extraction_status: ExtractionStatus;
  message_count: number;
  mode_id?: string | null;
  mode_key?: string | null;
  mode_name?: string | null;
  token_total?: number;
  created_time: string;
  updated_time: string;
}

export interface ConversationDetail extends ConversationSummary {
  messages: Message[];
  extraction_error?: string | null;
}

export interface ConversationCloseResponse {
  conversation_id: string;
  status: ConversationStatus;
  extraction_status: ExtractionStatus;
  extraction_triggered: boolean;
  notes_triggered?: boolean;
  memory_triggered?: boolean;
  detail?: string | null;
}

export interface NoteRef {
  id: string;
  title: string;
}

export interface NoteExtractResult {
  conversation_id: string;
  skipped: boolean;
  reason?: string | null;
  notes: NoteRef[];
  memory_updated?: boolean;
}

export interface ConversationCaptureResult {
  kind: 'skill' | 'knowledge' | 'persona';
  conversation_id: string;
  skill_id?: string | null;
  merged_into?: string | null;
  skipped: boolean;
  reason?: string | null;
  notes: NoteRef[];
  notes_skipped: boolean;
  memory_updated: boolean;
  detail?: string | null;
}

export type SettleKind = 'skill' | 'knowledge' | 'persona';

export interface SettleProposalItem {
  kind: SettleKind;
  recommended: boolean;
  confidence: number;
  reason: string;
}

export interface SettleProposal {
  conversation_id: string;
  title: string;
  mode_key?: string | null;
  mode_name?: string | null;
  summary: string;
  too_few: boolean;
  items: SettleProposalItem[];
}

export interface SettleKindResult {
  kind: SettleKind;
  ok: boolean;
  skipped: boolean;
  reason?: string | null;
  skill_id?: string | null;
  merged_into?: string | null;
  notes: NoteRef[];
  notes_skipped: boolean;
  memory_updated: boolean;
  error?: string | null;
  detail?: string | null;
}

export interface SettleRunResult {
  conversation_id: string;
  results: SettleKindResult[];
}

// ── chat ──────────────────────────────────────────────────────────────────

export interface SkillUsedInfo {
  id: string;
  name: string;
  similarity?: number | null;
}

export interface ChatResponse {
  conversation_id: string;
  message_id: string;
  answer: string;
  used_skills: SkillUsedInfo[];
  token_usage?: TokenUsage | null;
  title?: string | null;
  execution_trace?: ExecutionStep[] | null;
  mode?: ChatModeRef | null;
}

export type ChatToolPolicy = 'full' | 'light' | 'none' | string;

export interface ChatModeRef {
  id: string;
  key: string;
  name: string;
  tool_policy: ChatToolPolicy;
  use_long_term_memory: boolean;
  use_knowledge_memory?: boolean;
}

export interface ChatMode {
  id: string;
  key: string;
  name: string;
  description: string;
  system_prompt: string;
  tool_policy: ChatToolPolicy;
  use_long_term_memory: boolean;
  use_knowledge_memory: boolean;
  is_builtin: boolean;
  sort_order: number;
  created_at?: string | null;
  updated_at?: string | null;
}

export interface ChatModeCreatePayload {
  name: string;
  system_prompt: string;
  description?: string;
  use_long_term_memory?: boolean;
  use_knowledge_memory?: boolean;
}

export interface MemoryItem {
  id: string;
  field_key?: string;
  category: string;
  item_key: string;
  title: string;
  value: string;
  pinned: boolean;
}

export interface MemoryField {
  field_key: string;
  name: string;
  description: string;
  items: MemoryItem[];
}

export interface MemoryLane {
  empty: boolean;
  rendered: string;
  summary?: string;
  fields?: MemoryField[];
  items?: MemoryItem[];
  data: Record<string, unknown>;
}

export interface UserMemory {
  persona: MemoryLane;
  knowledge: MemoryLane;
}

export type ChatModeUpdatePayload = Partial<ChatModeCreatePayload>;

// ── skills ────────────────────────────────────────────────────────────────

export interface WorkflowStep {
  step?: number;
  action?: string;
  command?: string | null;
  expect?: string | null;
}

export interface SkillExample {
  question?: string;
  solution?: string;
  conversation_id?: string;
}

export interface SkillSummary {
  id: string;
  user_id: string;
  name: string;
  description: string;
  status: SkillStatus;
  source: SkillSource;
  confidence: number;
  version: number;
  usage_count: number;
  success_rate?: number | null;
  trigger_keywords: string[];
  trigger_intent?: string | null;
  created_at: string;
  updated_at: string;
  created_from_conversation_id?: string | null;
}

export interface SkillDetail extends SkillSummary {
  instruction: string;
  workflow: WorkflowStep[];
  examples: SkillExample[];
  tools: string[];
  success_count: number;
  failure_count: number;
  last_used_at?: string | null;
  embedding_hash?: string | null;
}

export interface SkillCreatePayload {
  name: string;
  description?: string;
  instruction?: string;
  trigger_keywords?: string[];
  trigger_intent?: string | null;
  workflow?: WorkflowStep[];
  examples?: SkillExample[];
  tools?: string[];
  confidence?: number;
}

export type SkillUpdatePayload = Partial<SkillCreatePayload>;

export interface GenerateSkillResponse {
  conversation_id: string;
  extraction_status: ExtractionStatus;
  skill_id?: string | null;
  merged_into?: string | null;
  skipped: boolean;
  reason?: string | null;
}

export interface SkillSearchResult {
  id: string;
  name: string;
  description: string;
  status: SkillStatus;
  score: number;
  vector_similarity: number;
  keyword_score: number;
  matched_keywords: string[];
  success_rate?: number | null;
  usage_count: number;
}

export interface SkillSearchResponse {
  query: string;
  count: number;
  embedding_provider: string;
  results: SkillSearchResult[];
}

export interface ReindexResponse {
  ok: boolean;
  vector_backend: string;
  embedding_provider: string;
  indexed_total: number;
  indexed: number;
  skipped: number;
  failed: number;
  total: number;
}

export interface HealthResponse {
  status: string;
  environment: string;
  database: boolean;
  llm_configured: boolean;
  embedding_provider: string;
  vector_backend: string;
  llm_source: LLMSource;
  llm_provider: string;
  llm_model: string;
}

// ── LLM provider config ───────────────────────────────────────────────────

export type ProviderKind = 'openai_compatible' | 'bedrock' | 'huggingface_image';

export function isChatProviderKind(kind: ProviderKind): boolean {
  return kind !== 'huggingface_image';
}

export function isImageCapableKind(kind: ProviderKind): boolean {
  return (
    kind === 'huggingface_image' ||
    kind === 'openai_compatible' ||
    kind === 'bedrock'
  );
}

/** Where the active configuration came from: the UI store, or the .env file. */
export type LLMSource = 'runtime' | 'env';

/** Credential fields arrive masked (e.g. `****1234`) and are never editable in place. */
export interface ProviderView {
  id: string;
  label: string;
  kind: ProviderKind;
  model: string;
  base_url?: string | null;
  api_key?: string | null;
  hf_provider?: string | null;
  aws_region?: string | null;
  aws_profile_name?: string | null;
  aws_access_key_id?: string | null;
  aws_secret_access_key?: string | null;
  aws_session_token?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
  created_at: string;
  updated_at: string;
  is_active: boolean;
  has_credentials: boolean;
}

export interface ActiveLLMView {
  source: LLMSource;
  kind: ProviderKind;
  label: string;
  model: string;
  provider_id?: string | null;
  base_url?: string | null;
  aws_region?: string | null;
  configured: boolean;
  temperature: number;
  max_tokens: number;
}

export interface EnvDefaultsView {
  base_url: string;
  model: string;
  has_api_key: boolean;
  temperature: number;
  max_tokens: number;
}

export interface PresetView {
  id: string;
  label: string;
  kind: ProviderKind;
  base_url?: string | null;
  hf_provider?: string | null;
  model: string;
  docs_url?: string | null;
  hint?: string | null;
  credential_env: string[];
}

export interface LLMConfigResponse {
  enabled: boolean;
  active: ActiveLLMView;
  env_defaults: EnvDefaultsView;
  providers: ProviderView[];
  presets: PresetView[];
  routes?: LLMRoutes;
  store_path: string;
}

export type LLMRoutePurpose =
  | 'chat'
  | 'skill'
  | 'notes'
  | 'memory'
  | 'knowledge'
  | 'image';

export type LLMRoutes = Record<LLMRoutePurpose, string | null>;

/** Create/update payload. Omitted keys keep their stored value on update. */
export interface ProviderPayload {
  label?: string;
  kind?: ProviderKind;
  model?: string;
  base_url?: string | null;
  api_key?: string | null;
  hf_provider?: string | null;
  aws_region?: string | null;
  aws_profile_name?: string | null;
  aws_access_key_id?: string | null;
  aws_secret_access_key?: string | null;
  aws_session_token?: string | null;
  temperature?: number | null;
  max_tokens?: number | null;
}

export interface ProviderCreatePayload extends ProviderPayload {
  label: string;
  kind: ProviderKind;
  model: string;
  activate?: boolean;
}

export interface ProviderTestResponse {
  ok: boolean;
  label: string;
  kind: ProviderKind;
  model: string;
  source: string;
  latency_ms?: number | null;
  content?: string | null;
  total_tokens?: number | null;
  error_code?: string | null;
  error_message?: string | null;
  error_details?: Record<string, unknown> | null;
}

export interface OkResponse {
  ok: boolean;
  message?: string | null;
}

export interface UsageTotals {
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  calls: number;
}

export interface UsagePurposeRow extends UsageTotals {
  purpose: string;
  label: string;
}

export interface UsageModelRow extends UsageTotals {
  model: string;
  provider_label: string;
}

export interface UsagePeriod extends UsageTotals {
  since?: string | null;
  by_purpose: UsagePurposeRow[];
  by_model: UsageModelRow[];
}

export interface UsageSummary {
  today: UsagePeriod;
  month: UsagePeriod;
  all: UsagePeriod;
}

export type SearchProvider =
  | 'auto'
  | 'brave'
  | 'tavily'
  | 'serper'
  | 'deepseek'
  | 'ddgs'
  | 'ddg_html';

export type SearchKeySource = 'runtime' | 'env' | 'llm' | 'unset';

export interface SearchKeyView {
  configured: boolean;
  source: SearchKeySource;
  masked?: string | null;
}

export interface SearchConfigResponse {
  provider: SearchProvider;
  provider_source: 'runtime' | 'env';
  env_provider: string;
  keys: Record<string, SearchKeyView>;
  deepseek_base_url: string;
  deepseek_model: string;
  deepseek_max_uses: number;
  planned_backends: string[];
  store_path: string;
  providers: SearchProvider[];
}

export interface SearchConfigUpdate {
  provider?: SearchProvider;
  brave_search_api_key?: string | null;
  tavily_api_key?: string | null;
  serper_api_key?: string | null;
  deepseek_api_key?: string | null;
  deepseek_base_url?: string | null;
  deepseek_model?: string | null;
  deepseek_max_uses?: number | null;
}

export interface SearchTestResult {
  title: string;
  url: string;
  snippet: string;
}

export interface SearchTestResponse {
  ok: boolean;
  query: string;
  provider?: string | null;
  count: number;
  results: SearchTestResult[];
  tried: string[];
  latency_ms?: number | null;
  error?: string | null;
}

export type SandboxMode = 'read-only' | 'workspace-write' | 'danger-full-access';

export interface ShellConfigResponse {
  enabled: boolean;
  enabled_source: 'runtime' | 'env';
  default_mode: SandboxMode;
  default_mode_source: 'runtime' | 'env';
  max_mode: SandboxMode;
  modes: SandboxMode[];
  workspace_path: string;
  os_sandbox: string;
  enforcement: 'strict' | 'advisory';
  backend?: string | null;
  network: boolean;
  store_path: string;
}

export interface ShellConfigUpdate {
  enabled?: boolean;
  default_mode?: SandboxMode;
}
