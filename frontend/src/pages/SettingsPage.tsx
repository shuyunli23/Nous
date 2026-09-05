import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import {
  activateProvider,
  checkBedrockSdk,
  createProvider,
  deactivateProvider,
  deleteProvider,
  getLLMConfig,
  testActiveProvider,
  testProvider,
  updateProvider,
  updateRoutes,
} from '../api/llmConfig';
import type {
  LLMConfigResponse,
  LLMRoutePurpose,
  ProviderCreatePayload,
  ProviderKind,
  ProviderTestResponse,
  ProviderView,
} from '../api/types';
import { isChatProviderKind, isImageCapableKind } from '../api/types';
import AppearanceSection from '../components/AppearanceSection';
import ProviderEditor from '../components/ProviderEditor';
import ModesSection from '../components/ModesSection';
import MemorySection from '../components/MemorySection';
import SearchSection from '../components/SearchSection';
import UsageSection from '../components/UsageSection';
import { useI18n, type MessageKey, type Vars } from '../i18n';

const KIND_KEY: Record<ProviderKind, MessageKey> = {
  openai_compatible: 'settings.kindOpenai',
  bedrock: 'settings.kindBedrock',
  huggingface_image: 'settings.kindHfImage',
};

const ROUTE_ROWS: {
  purpose: LLMRoutePurpose;
  label: MessageKey;
  hint: MessageKey;
}[] = [
  { purpose: 'chat', label: 'settings.routeChat', hint: 'settings.routeChatHint' },
  { purpose: 'skill', label: 'settings.routeSkill', hint: 'settings.routeSkillHint' },
  { purpose: 'notes', label: 'settings.routeNotes', hint: 'settings.routeNotesHint' },
  { purpose: 'memory', label: 'settings.routeMemory', hint: 'settings.routeMemoryHint' },
  {
    purpose: 'knowledge',
    label: 'settings.routeKnowledge',
    hint: 'settings.routeKnowledgeHint',
  },
  {
    purpose: 'image',
    label: 'settings.routeImage',
    hint: 'settings.routeImageHint',
  },
];

function describeTest(
  result: ProviderTestResponse,
  t: (path: MessageKey, vars?: Vars) => string,
): string {
  if (result.ok) {
    const tokens = result.total_tokens
      ? t('settings.testTokens', { n: result.total_tokens })
      : '';
    return t('settings.testOk', {
      label: result.label,
      model: result.model,
      ms: result.latency_ms,
      content: result.content ?? '',
      tokens,
    });
  }
  const hint =
    result.error_details && typeof result.error_details.hint === 'string'
      ? t('settings.testHint', { hint: result.error_details.hint })
      : '';
  return (
    t('settings.testFail', {
      label: result.label,
      code: result.error_code ?? '',
      message: result.error_message ?? t('settings.unknownError'),
    }) + hint
  );
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export default function SettingsPage() {
  const { t } = useI18n();
  const [config, setConfig] = useState<LLMConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);

  const [editorOpen, setEditorOpen] = useState(false);
  const [editing, setEditing] = useState<ProviderView | null>(null);
  const [saving, setSaving] = useState(false);
  const [editorError, setEditorError] = useState<string | null>(null);

  const [testing, setTesting] = useState(false);
  // Three separate slots so a result always renders next to what was tested.
  const [editorTest, setEditorTest] = useState<ProviderTestResponse | null>(
    null,
  );
  const [activeTest, setActiveTest] = useState<ProviderTestResponse | null>(
    null,
  );
  const [rowTest, setRowTest] = useState<ProviderTestResponse | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setConfig(await getLLMConfig());
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.loadFailed')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  useEffect(() => {
    const hash = window.location.hash;
    if (
      hash !== '#modes' &&
      hash !== '#memory' &&
      hash !== '#usage' &&
      hash !== '#appearance' &&
      hash !== '#search'
    ) {
      return;
    }
    window.requestAnimationFrame(() => {
      document.getElementById(hash.slice(1))?.scrollIntoView({ behavior: 'smooth' });
    });
  }, [loading]);

  function openEditor(provider: ProviderView | null) {
    setEditing(provider);
    setEditorError(null);
    setEditorTest(null);
    setEditorOpen(true);
  }

  async function handleSave(payload: ProviderCreatePayload, isEdit: boolean) {
    setSaving(true);
    setEditorError(null);
    try {
      const next =
        isEdit && editing
          ? await updateProvider(editing.id, payload)
          : await createProvider({
              ...payload,
              activate: isChatProviderKind(payload.kind) && payload.activate !== false,
            });
      setConfig(next);
      setNotice(
        isEdit
          ? t('settings.saved', { label: payload.label })
          : isChatProviderKind(payload.kind)
            ? t('settings.created', { label: payload.label })
            : t('settings.createdImage', { label: payload.label }),
      );
      setEditorOpen(false);
      setEditing(null);
    } catch (err: unknown) {
      setEditorError(errorMessage(err, t('settings.saveFailed')));
    } finally {
      setSaving(false);
    }
  }

  async function handleEditorTest(payload: ProviderCreatePayload) {
    setTesting(true);
    setEditorTest(null);
    try {
      setEditorTest(await testProvider({ draft: payload }));
    } catch (err: unknown) {
      setEditorError(errorMessage(err, t('settings.testFailed')));
    } finally {
      setTesting(false);
    }
  }

  async function handleRowTest(provider: ProviderView) {
    setBusyId(provider.id);
    setRowTest(null);
    setError(null);
    try {
      setRowTest(await testProvider({ providerId: provider.id }));
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.testFailed')));
    } finally {
      setBusyId(null);
    }
  }

  async function handleActivate(provider: ProviderView) {
    setBusyId(provider.id);
    setError(null);
    try {
      setConfig(await activateProvider(provider.id));
      setNotice(t('settings.activated', { label: provider.label }));
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.switchFailed')));
    } finally {
      setBusyId(null);
    }
  }

  async function handleRouteChange(purpose: LLMRoutePurpose, providerId: string) {
    setBusyId(`route-${purpose}`);
    setError(null);
    try {
      setConfig(await updateRoutes({ [purpose]: providerId || null }));
      setNotice(t('settings.routesSaved'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.routesFailed')));
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(provider: ProviderView) {
    if (!window.confirm(t('settings.confirmDelete', { label: provider.label }))) {
      return;
    }
    setBusyId(provider.id);
    setError(null);
    try {
      setConfig(await deleteProvider(provider.id));
      setNotice(t('settings.deleted', { label: provider.label }));
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.deleteFailed')));
    } finally {
      setBusyId(null);
    }
  }

  async function handleUseEnv() {
    setError(null);
    try {
      setConfig(await deactivateProvider());
      setNotice(t('settings.usingEnv'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.switchFailed')));
    }
  }

  async function handleTestActive() {
    setTesting(true);
    setActiveTest(null);
    setError(null);
    try {
      setActiveTest(await testActiveProvider());
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.testFailed')));
    } finally {
      setTesting(false);
    }
  }

  async function handleBedrockCheck() {
    setError(null);
    try {
      const result = await checkBedrockSdk();
      setNotice(
        result.message ??
          (result.ok ? t('settings.botoOk') : t('settings.botoMissing')),
      );
    } catch (err: unknown) {
      setError(errorMessage(err, t('settings.checkFailed')));
    }
  }

  if (loading) {
    return (
      <div className="page">
        <div className="empty row" style={{ justifyContent: 'center' }}>
          <span className="spinner" aria-hidden="true" />
          <span>{t('common.loading')}</span>
        </div>
      </div>
    );
  }

  if (!config) {
    return (
      <div className="page">
        <div className="page__header">
          <div>
            <h1 className="page__title">{t('settings.title')}</h1>
            <p className="page__subtitle">{t('settings.subtitle')}</p>
          </div>
        </div>
        <div className="alert alert--error">
          {error ?? t('settings.cannotLoad')}
        </div>
        <button type="button" className="btn" onClick={() => void load()}>
          {t('common.retry')}
        </button>
        <AppearanceSection />
        <SearchSection />
        <ModesSection />
        <MemorySection />
      </div>
    );
  }

  const { active, env_defaults: env, providers, presets } = config;
  const usingEnv = active.source === 'env';

  return (
    <div className="page">
      <div className="page__header">
        <div>
          <h1 className="page__title">{t('settings.title')}</h1>
          <p className="page__subtitle">{t('settings.subtitle')}</p>
        </div>
        <div className="row">
          <button type="button" className="btn btn--sm" onClick={handleBedrockCheck}>
            {t('settings.checkBedrock')}
          </button>
          <button
            type="button"
            className="btn btn--sm btn--primary"
            onClick={() => openEditor(null)}
            disabled={!config.enabled}
          >
            {t('settings.addProvider')}
          </button>
        </div>
      </div>

      {!config.enabled && (
        <div className="alert alert--warning">
          {t('settings.runtimeDisabled')}
        </div>
      )}
      {error && <div className="alert alert--error">{error}</div>}
      {notice && <div className="alert alert--info">{notice}</div>}

      <AppearanceSection />
      <SearchSection />

      <div className="card active-llm">
        <div className="active-llm__head">
          <div>
            <span className="active-llm__eyebrow">{t('settings.activeEyebrow')}</span>
            <h2 className="active-llm__title">
              {usingEnv ? t('settings.envDefault') : active.label}
              <span className={`badge ${usingEnv ? 'badge--draft' : 'badge--active'}`}>
                {usingEnv ? t('settings.fromEnv') : t('settings.runtime')}
              </span>
              {!active.configured && (
                <span className="badge badge--failed">{t('settings.missingCreds')}</span>
              )}
            </h2>
          </div>
          <div className="row">
            <button
              type="button"
              className="btn btn--sm"
              onClick={handleTestActive}
              disabled={testing}
            >
              {testing ? t('settings.testing') : t('settings.testActive')}
            </button>
            {!usingEnv && (
              <button type="button" className="btn btn--sm" onClick={handleUseEnv}>
                {t('settings.useEnv')}
              </button>
            )}
          </div>
        </div>

        <div className="detail-grid detail-grid--compact">
          <div className="stat">
            <span className="stat__label">{t('settings.kind')}</span>
            <span className="stat__value">{t(KIND_KEY[active.kind])}</span>
          </div>
          <div className="stat">
            <span className="stat__label">{t('settings.model')}</span>
            <span className="stat__value mono">{active.model}</span>
          </div>
          <div className="stat">
            <span className="stat__label">
              {active.kind === 'bedrock'
                ? t('settings.region')
                : t('settings.baseUrl')}
            </span>
            <span className="stat__value mono">
              {active.kind === 'bedrock'
                ? (active.aws_region ?? '—')
                : (active.base_url ?? '—')}
            </span>
          </div>
          <div className="stat">
            <span className="stat__label">{t('settings.tempTokens')}</span>
            <span className="stat__value mono">
              {active.temperature} / {active.max_tokens}
            </span>
          </div>
        </div>

        {activeTest && (
          <div
            className={`alert ${activeTest.ok ? 'alert--info' : 'alert--error'}`}
            style={{ marginTop: 16, marginBottom: 0 }}
          >
            {describeTest(activeTest, t)}
          </div>
        )}
      </div>

      <h2 className="section__title section__title--spaced">
        {t('settings.routesTitle')}
      </h2>
      <div className="card">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          {t('settings.routesLead')}
        </p>
        <div className="llm-routes">
          {ROUTE_ROWS.map((row) => (
            <label key={row.purpose} className="llm-route">
              <span>
                <span className="llm-route__label">{t(row.label)}</span>
                <span className="llm-route__hint">{t(row.hint)}</span>
              </span>
              <select
                value={config.routes?.[row.purpose] ?? ''}
                disabled={!config.enabled || busyId === `route-${row.purpose}`}
                onChange={(event) =>
                  void handleRouteChange(row.purpose, event.target.value)
                }
              >
                <option value="">
                  {row.purpose === 'image'
                    ? t('settings.routesFollowImage')
                    : t('settings.routesFollow')}
                </option>
                {(row.purpose === 'image'
                  ? providers.filter((p) => isImageCapableKind(p.kind))
                  : providers.filter((p) => isChatProviderKind(p.kind))
                ).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.label} · {p.model}
                  </option>
                ))}
              </select>
            </label>
          ))}
        </div>
      </div>

      <h2 className="section__title section__title--spaced">
        {t('settings.savedProviders')}
      </h2>

      {rowTest && (
        <div className={`alert ${rowTest.ok ? 'alert--info' : 'alert--error'}`}>
          {describeTest(rowTest, t)}
        </div>
      )}

      {providers.length === 0 ? (
        <div className="empty">
          {t('settings.empty')}
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>{t('settings.colName')}</th>
                <th>{t('settings.colKind')}</th>
                <th>{t('settings.colModel')}</th>
                <th>{t('settings.colEndpoint')}</th>
                <th>{t('settings.colCreds')}</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {providers.map((p) => (
                <tr key={p.id}>
                  <td>
                    {p.label}
                    {p.is_active && (
                      <span className="badge badge--active" style={{ marginLeft: 8 }}>
                        {t('settings.inUse')}
                      </span>
                    )}
                  </td>
                  <td className="faint">{t(KIND_KEY[p.kind])}</td>
                  <td className="mono">{p.model}</td>
                  <td className="mono faint">
                    {p.kind === 'bedrock'
                      ? (p.aws_region ?? '—')
                      : p.kind === 'huggingface_image'
                        ? (p.hf_provider ?? 'fal-ai')
                        : (p.base_url ?? '—')}
                  </td>
                  <td className="mono faint">
                    {p.kind === 'bedrock'
                      ? (p.aws_secret_access_key ??
                        (p.aws_profile_name
                          ? t('settings.profile', { name: p.aws_profile_name })
                          : t('settings.defaultChain')))
                      : (p.api_key ?? t('common.none'))}
                  </td>
                  <td>
                    <div className="table__actions">
                      {isChatProviderKind(p.kind) ? (
                      <button
                        type="button"
                        className="btn btn--sm"
                        disabled={busyId === p.id || p.is_active}
                        onClick={() => void handleActivate(p)}
                      >
                        {p.is_active ? t('common.enabled') : t('common.enable')}
                      </button>
                      ) : null}
                      <button
                        type="button"
                        className="btn btn--sm"
                        disabled={busyId === p.id}
                        onClick={() => void handleRowTest(p)}
                      >
                        {t('skills.probe')}
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm"
                        disabled={busyId === p.id}
                        onClick={() => openEditor(p)}
                      >
                        {t('common.edit')}
                      </button>
                      <button
                        type="button"
                        className="btn btn--sm btn--danger"
                        disabled={busyId === p.id}
                        onClick={() => void handleDelete(p)}
                      >
                        {t('common.delete')}
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      <h2 className="section__title section__title--spaced">
        {t('settings.envFallback')}
      </h2>
      <div className="card">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          {t('settings.envFallbackLead')}
        </p>
        <div className="detail-grid detail-grid--compact">
          <div className="stat">
            <span className="stat__label">{t('settings.baseUrl')}</span>
            <span className="stat__value mono">{env.base_url}</span>
          </div>
          <div className="stat">
            <span className="stat__label">{t('settings.model')}</span>
            <span className="stat__value mono">{env.model}</span>
          </div>
          <div className="stat">
            <span className="stat__label">{t('settings.apiKey')}</span>
            <span className="stat__value">
              {env.has_api_key
                ? t('settings.configured')
                : t('settings.unconfigured')}
            </span>
          </div>
          <div className="stat">
            <span className="stat__label">{t('settings.tempTokens')}</span>
            <span className="stat__value mono">
              {env.temperature} / {env.max_tokens}
            </span>
          </div>
        </div>
      </div>

      <p className="faint" style={{ fontSize: 12, marginTop: 16 }}>
        {t('settings.storeHint', { path: config.store_path })}
      </p>

      <UsageSection />
      <ModesSection />
      <MemorySection />

      <ProviderEditor
        provider={editing}
        presets={presets}
        open={editorOpen}
        saving={saving}
        error={editorError}
        testing={testing}
        testResult={editorTest ? describeTest(editorTest, t) : null}
        testOk={editorTest?.ok}
        onClose={() => {
          setEditorOpen(false);
          setEditing(null);
        }}
        onSave={handleSave}
        onTest={handleEditorTest}
      />
    </div>
  );
}
