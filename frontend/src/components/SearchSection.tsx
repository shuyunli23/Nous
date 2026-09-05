import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import {
  getSearchConfig,
  resetSearchConfig,
  testSearch,
  updateSearchConfig,
} from '../api/searchConfig';
import type {
  SearchConfigResponse,
  SearchConfigUpdate,
  SearchKeySource,
  SearchProvider,
  SearchTestResponse,
} from '../api/types';
import { useI18n, type MessageKey } from '../i18n';

const PROVIDERS: SearchProvider[] = [
  'auto',
  'brave',
  'tavily',
  'serper',
  'deepseek',
  'ddgs',
  'ddg_html',
];

const PROVIDER_LABEL: Record<SearchProvider, MessageKey> = {
  auto: 'search.providerAuto',
  brave: 'search.providerBrave',
  tavily: 'search.providerTavily',
  serper: 'search.providerSerper',
  deepseek: 'search.providerDeepseek',
  ddgs: 'search.providerDdgs',
  ddg_html: 'search.providerDdgHtml',
};

const SOURCE_LABEL: Record<SearchKeySource, MessageKey> = {
  runtime: 'search.sourceRuntime',
  env: 'search.sourceEnv',
  llm: 'search.sourceLlm',
  unset: 'search.sourceUnset',
};

const KEY_FIELDS = [
  {
    id: 'brave_search_api_key',
    label: 'search.braveKey',
    hint: 'search.braveHint',
  },
  {
    id: 'tavily_api_key',
    label: 'search.tavilyKey',
    hint: 'search.tavilyHint',
  },
  {
    id: 'serper_api_key',
    label: 'search.serperKey',
    hint: 'search.serperHint',
  },
] as const;

const PROVIDER_HINT: Record<SearchProvider, MessageKey> = {
  auto: 'search.hintAuto',
  brave: 'search.hintBrave',
  tavily: 'search.hintTavily',
  serper: 'search.hintSerper',
  deepseek: 'search.hintDeepseek',
  ddgs: 'search.hintDdgs',
  ddg_html: 'search.hintDdgHtml',
};

function visiblePaidKeys(provider: SearchProvider) {
  if (provider === 'auto') return KEY_FIELDS;
  if (provider === 'brave') return KEY_FIELDS.filter((f) => f.id === 'brave_search_api_key');
  if (provider === 'tavily') return KEY_FIELDS.filter((f) => f.id === 'tavily_api_key');
  if (provider === 'serper') return KEY_FIELDS.filter((f) => f.id === 'serper_api_key');
  return [];
}

type SecretId =
  | 'brave_search_api_key'
  | 'tavily_api_key'
  | 'serper_api_key'
  | 'deepseek_api_key';

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

function previewBackends(
  provider: SearchProvider,
  config: SearchConfigResponse,
): string[] {
  const paid: string[] = [];
  if (config.keys.brave_search_api_key?.configured) paid.push('brave');
  if (config.keys.tavily_api_key?.configured) paid.push('tavily');
  if (config.keys.serper_api_key?.configured) paid.push('serper');
  if (provider === 'brave') return ['brave'];
  if (provider === 'tavily') return ['tavily'];
  if (provider === 'serper') return ['serper'];
  if (provider === 'deepseek') return ['deepseek'];
  if (provider === 'ddgs') return ['ddg_html', 'ddgs'];
  if (provider === 'ddg_html') return ['ddg_html'];
  return [...paid, 'ddg_html', 'ddgs'];
}

export default function SearchSection({
  hideHeading = false,
}: {
  hideHeading?: boolean;
}) {
  const { t } = useI18n();
  const [config, setConfig] = useState<SearchConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const [provider, setProvider] = useState<SearchProvider>('auto');
  const [drafts, setDrafts] = useState<Record<SecretId, string>>({
    brave_search_api_key: '',
    tavily_api_key: '',
    serper_api_key: '',
    deepseek_api_key: '',
  });
  const [cleared, setCleared] = useState<Record<SecretId, boolean>>({
    brave_search_api_key: false,
    tavily_api_key: false,
    serper_api_key: false,
    deepseek_api_key: false,
  });
  const [deepseekBaseUrl, setDeepseekBaseUrl] = useState('');
  const [deepseekModel, setDeepseekModel] = useState('');
  const [deepseekMaxUses, setDeepseekMaxUses] = useState(2);

  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [testResult, setTestResult] = useState<SearchTestResponse | null>(null);

  const applyConfig = useCallback((next: SearchConfigResponse) => {
    setConfig(next);
    setProvider(next.provider);
    setDeepseekBaseUrl(next.deepseek_base_url);
    setDeepseekModel(next.deepseek_model);
    setDeepseekMaxUses(next.deepseek_max_uses);
    setDrafts({
      brave_search_api_key: '',
      tavily_api_key: '',
      serper_api_key: '',
      deepseek_api_key: '',
    });
    setCleared({
      brave_search_api_key: false,
      tavily_api_key: false,
      serper_api_key: false,
      deepseek_api_key: false,
    });
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      applyConfig(await getSearchConfig());
    } catch (err: unknown) {
      setError(errorMessage(err, t('search.loadFailed')));
    } finally {
      setLoading(false);
    }
  }, [applyConfig, t]);

  useEffect(() => {
    void load();
  }, [load]);

  function applySecret(
    payload: SearchConfigUpdate,
    id: SecretId,
  ) {
    if (cleared[id]) {
      payload[id] = '';
    } else if (drafts[id].trim()) {
      payload[id] = drafts[id].trim();
    }
  }

  async function handleSave() {
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      const payload: SearchConfigUpdate = {
        provider,
        deepseek_base_url: deepseekBaseUrl.trim(),
        deepseek_model: deepseekModel.trim(),
        deepseek_max_uses: deepseekMaxUses,
      };
      applySecret(payload, 'brave_search_api_key');
      applySecret(payload, 'tavily_api_key');
      applySecret(payload, 'serper_api_key');
      applySecret(payload, 'deepseek_api_key');
      applyConfig(await updateSearchConfig(payload));
      setNotice(t('search.saved'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('search.saveFailed')));
    } finally {
      setSaving(false);
    }
  }

  async function handleReset() {
    if (!window.confirm(t('search.confirmReset'))) return;
    setSaving(true);
    setError(null);
    setNotice(null);
    try {
      applyConfig(await resetSearchConfig());
      setNotice(t('search.resetOk'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('search.resetFailed')));
    } finally {
      setSaving(false);
    }
  }

  async function handleTest() {
    setTesting(true);
    setTestResult(null);
    setError(null);
    try {
      setTestResult(await testSearch());
    } catch (err: unknown) {
      setError(errorMessage(err, t('search.testFailed')));
    } finally {
      setTesting(false);
    }
  }

  function renderSecret(id: SecretId, label: MessageKey, hint: MessageKey) {
    const key = config?.keys[id];
    const hasStored = Boolean(key?.configured);
    return (
      <div className="field" key={id}>
        <label htmlFor={`search-${id}`}>{t(label)}</label>
        <input
          id={`search-${id}`}
          type="password"
          autoComplete="off"
          value={drafts[id]}
          onChange={(event) => {
            const value = event.target.value;
            setDrafts((prev) => ({ ...prev, [id]: value }));
            if (value) setCleared((prev) => ({ ...prev, [id]: false }));
          }}
          placeholder={hasStored ? t('search.keepBlank') : t('search.keyPlaceholder')}
        />
        <p className="field__hint">
          {t(hint)}
          {hasStored ? (
            <>
              {' '}
              · {t('search.savedValue')} <code>{key?.masked}</code> (
              {t(SOURCE_LABEL[key?.source ?? 'unset'])})
            </>
          ) : (
            <>
              {' '}
              · {t('search.sourceUnset')}
            </>
          )}
          {hasStored && (
            <>
              {' '}
              ·{' '}
              {cleared[id] ? (
                <>
                  <strong>{t('search.willClear')}</strong>{' '}
                  <button
                    type="button"
                    className="link-btn"
                    onClick={() => setCleared((prev) => ({ ...prev, [id]: false }))}
                  >
                    {t('search.undo')}
                  </button>
                </>
              ) : (
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    setCleared((prev) => ({ ...prev, [id]: true }));
                    setDrafts((prev) => ({ ...prev, [id]: '' }));
                  }}
                >
                  {t('search.clear')}
                </button>
              )}
            </>
          )}
        </p>
      </div>
    );
  }

  return (
    <section id="search" className="section">
      {hideHeading ? null : (
        <h2 className="section__title">{t('search.title')}</h2>
      )}
      <div className="card">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          {t('search.lead')}
        </p>

        {loading ? (
          <p className="muted">{t('common.loading')}</p>
        ) : (
          <>
            {error && <div className="alert alert--error">{error}</div>}
            {notice && <div className="alert alert--info">{notice}</div>}

            <label className="field">
              <span>{t('search.provider')}</span>
              <select
                value={provider}
                onChange={(event) => setProvider(event.target.value as SearchProvider)}
              >
                {PROVIDERS.map((id) => (
                  <option key={id} value={id}>
                    {t(PROVIDER_LABEL[id])}
                  </option>
                ))}
              </select>
              <p className="field__hint">{t(PROVIDER_HINT[provider])}</p>
            </label>

            {config && (
              <p className="field__hint" style={{ marginTop: 4 }}>
                {t('search.planned', {
                  list: previewBackends(provider, config).join(' → '),
                  source:
                    provider !== config.provider
                      ? t('search.sourceDraft')
                      : config.provider_source === 'runtime'
                        ? t('search.sourceRuntime')
                        : t('search.sourceEnv'),
                })}
              </p>
            )}

            {visiblePaidKeys(provider).length > 0 && (
              <div className="stack" style={{ marginTop: 16 }}>
                {visiblePaidKeys(provider).map((field) =>
                  renderSecret(field.id, field.label, field.hint),
                )}
              </div>
            )}

            {provider === 'deepseek' && (
              <div className="stack" style={{ marginTop: 16 }}>
                {renderSecret(
                  'deepseek_api_key',
                  'search.deepseekKey',
                  'search.deepseekKeyHint',
                )}
                <div className="row row--split">
                  <label className="field">
                    <span>{t('search.deepseekEndpoint')}</span>
                    <input
                      value={deepseekBaseUrl}
                      onChange={(event) => setDeepseekBaseUrl(event.target.value)}
                      placeholder="https://api.deepseek.com/anthropic/v1"
                    />
                  </label>
                  <label className="field">
                    <span>{t('search.deepseekModel')}</span>
                    <input
                      value={deepseekModel}
                      onChange={(event) => setDeepseekModel(event.target.value)}
                      placeholder="deepseek-v4-flash"
                    />
                  </label>
                  <label className="field">
                    <span>{t('search.deepseekUses')}</span>
                    <input
                      type="number"
                      min={1}
                      max={5}
                      value={deepseekMaxUses}
                      onChange={(event) =>
                        setDeepseekMaxUses(
                          Math.max(1, Math.min(5, Number(event.target.value) || 1)),
                        )
                      }
                    />
                    <p className="field__hint">{t('search.deepseekUsesHint')}</p>
                  </label>
                </div>
              </div>
            )}

            <div className="row" style={{ marginTop: 16 }}>
              <button
                type="button"
                className="btn btn--sm btn--primary"
                disabled={saving}
                onClick={() => void handleSave()}
              >
                {saving ? t('common.saving') : t('common.save')}
              </button>
              <button
                type="button"
                className="btn btn--sm"
                disabled={testing || saving}
                title={t('search.testHint')}
                onClick={() => void handleTest()}
              >
                {testing ? t('search.testing') : t('search.test')}
              </button>
              <button
                type="button"
                className="btn btn--sm"
                disabled={saving}
                onClick={() => void handleReset()}
              >
                {t('search.reset')}
              </button>
            </div>

            {testResult && (
              <div
                className={`alert ${testResult.ok ? 'alert--info' : 'alert--error'}`}
                style={{ marginTop: 16, marginBottom: 0 }}
              >
                {testResult.ok
                  ? t('search.testOk', {
                      provider: testResult.provider ?? '',
                      n: testResult.count,
                      ms: testResult.latency_ms ?? 0,
                    })
                  : t('search.testFail', {
                      message: testResult.error || t('settings.unknownError'),
                    })}
                {testResult.results.length > 0 && (
                  <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
                    {testResult.results.map((row) => (
                      <li key={row.url} style={{ marginBottom: 4 }}>
                        <a href={row.url} target="_blank" rel="noreferrer">
                          {row.title || row.url}
                        </a>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}

            {config && (
              <p className="faint" style={{ fontSize: 12, marginTop: 16, marginBottom: 0 }}>
                {t('search.storeHint', { path: config.store_path })}
              </p>
            )}
          </>
        )}
      </div>
    </section>
  );
}
