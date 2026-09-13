import type { ProviderKind } from '../api/types';

/**
 * Historic default the backend treats as "never chosen" -- a provider still
 * carrying it shows as empty so the field falls through to the model cap.
 * Mirrors ``_LEGACY_DEFAULT`` in backend/app/llm/token_limits.py.
 */
export const LEGACY_MAX_TOKENS = 2048;

/**
 * Mirrors backend ``app.llm.token_limits.output_token_cap``, which is the
 * source of truth -- keep both tables in step. Needed here because the editor
 * caps a draft (kind/model still being typed) before the server sees it.
 */
export function outputTokenCap(kind: ProviderKind | string, model: string): number {
  const name = (model || '').toLowerCase();
  const family = (kind || '').toLowerCase();

  if (family === 'huggingface_image') return 1024;

  if (name.includes('claude') || name.includes('anthropic') || family === 'bedrock') {
    if (['opus-4', 'sonnet-4', 'haiku-4', '3-7', '3.7'].some((key) => name.includes(key))) {
      return 64000;
    }
    if (name.includes('opus') && !name.includes('3-5') && !name.includes('3.5')) {
      return 4096;
    }
    return 8192;
  }

  if (['o1', 'o3', 'o4', 'gpt-5'].some((key) => name.includes(key))) return 100000;
  if (name.includes('gpt-4.1')) return 32768;
  if (name.includes('gpt-4o')) return 16384;
  if (name.includes('gemini') || family === 'gemini') return 65536;
  if (name.includes('deepseek')) return 8192;
  if (name.includes('qwen')) return 8192;
  return 8192;
}
