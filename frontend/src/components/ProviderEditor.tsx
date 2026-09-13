import { useEffect, useState } from 'react';

import type {
  PresetView,
  ProviderCreatePayload,
  ProviderKind,
  ProviderView,
} from '../api/types';
import { isChatProviderKind } from '../api/types';
import { useI18n } from '../i18n';
import { LEGACY_MAX_TOKENS, outputTokenCap } from '../lib/tokenLimits';

interface ProviderEditorProps {
  /** Existing provider to edit, or null to create a new one. */
  provider: ProviderView | null;
  presets: PresetView[];
  open: boolean;
  saving?: boolean;
  error?: string | null;
  testing?: boolean;
  testResult?: string | null;
  testOk?: boolean;
  onClose: () => void;
  onSave: (
    payload: ProviderCreatePayload,
    isEdit: boolean,
    apply: boolean,
  ) => void;
  onTest: (payload: ProviderCreatePayload, useSaved: boolean) => void;
}

const KIND_LABEL = {
  openai_compatible: 'provider.kindOpenai',
  bedrock: 'provider.kindBedrock',
  huggingface_image: 'provider.kindHfImage',
} as const;

/** Credentials come back masked, so an untouched field must mean "keep". */
type SecretField =
  | 'api_key'
  | 'aws_access_key_id'
  | 'aws_secret_access_key'
  | 'aws_session_token';

function emptyForm() {
  return {
    label: '',
    kind: 'openai_compatible' as ProviderKind,
    model: '',
    base_url: '',
    api_key: '',
    aws_region: '',
    aws_profile_name: '',
    aws_access_key_id: '',
    aws_secret_access_key: '',
    aws_session_token: '',
    temperature: '',
    max_tokens: '',
    hf_provider: 'fal-ai',
  };
}

type FormState = ReturnType<typeof emptyForm>;

export default function ProviderEditor({
  provider,
  presets,
  open,
  saving,
  error,
  testing,
  testResult,
  testOk,
  onClose,
  onSave,
  onTest,
}: ProviderEditorProps) {
  const { t } = useI18n();
  const [form, setForm] = useState<FormState>(emptyForm);
  const [cleared, setCleared] = useState<Record<string, boolean>>({});

  const isEdit = provider !== null;

  useEffect(() => {
    if (!open) return;
    setCleared({});
    if (!provider) {
      setForm(emptyForm());
      return;
    }
    setForm({
      label: provider.label,
      kind: provider.kind,
      model: provider.model,
      base_url: provider.base_url ?? '',
      // Secrets are intentionally left blank: the stored value is kept unless
      // the user types a replacement or clears it explicitly.
      api_key: '',
      aws_region: provider.aws_region ?? '',
      aws_profile_name: provider.aws_profile_name ?? '',
      aws_access_key_id: '',
      aws_secret_access_key: '',
      aws_session_token: '',
      temperature:
        provider.temperature === null || provider.temperature === undefined
          ? ''
          : String(provider.temperature),
      max_tokens:
        provider.max_tokens === null ||
        provider.max_tokens === undefined ||
        provider.max_tokens === LEGACY_MAX_TOKENS
          ? ''
          : String(provider.max_tokens),
      hf_provider: provider.hf_provider ?? 'fal-ai',
    });
  }, [open, provider]);

  if (!open) return null;

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function applyPreset(preset: PresetView) {
    setForm((prev) => ({
      ...prev,
      kind: preset.kind,
      model: preset.model,
      base_url: preset.base_url ?? '',
      hf_provider: preset.hf_provider ?? prev.hf_provider,
      label: prev.label.trim() || preset.label,
    }));
  }

  function buildPayload(): ProviderCreatePayload {
    const payload: ProviderCreatePayload = {
      label: form.label.trim(),
      kind: form.kind,
      model: form.model.trim(),
    };

    // Only send the fields that belong to the selected kind, so switching kind
    // never silently clears the other protocol's settings.
    const secrets: SecretField[] =
      form.kind === 'bedrock'
        ? ['aws_access_key_id', 'aws_secret_access_key', 'aws_session_token']
        : ['api_key'];

    if (form.kind === 'openai_compatible') {
      payload.base_url = form.base_url.trim();
    } else if (form.kind === 'bedrock') {
      payload.aws_region = form.aws_region.trim();
      payload.aws_profile_name = form.aws_profile_name.trim();
    } else {
      payload.hf_provider = form.hf_provider.trim() || 'fal-ai';
    }

    // On create, send everything typed. On edit, send a secret only when the
    // user replaced it ('' clears it server-side).
    for (const field of secrets) {
      const typed = form[field].trim();
      if (typed) {
        payload[field] = typed;
      } else if (!isEdit || cleared[field]) {
        payload[field] = '';
      }
    }

    payload.temperature =
      form.kind === 'huggingface_image'
        ? null
        : form.temperature.trim() === ''
          ? null
          : Number(form.temperature);
    payload.max_tokens =
      form.kind === 'huggingface_image'
        ? null
        : form.max_tokens.trim() === ''
          ? null
          : Number(form.max_tokens);

    payload.activate = false;
    return payload;
  }

  const isBedrock = form.kind === 'bedrock';
  const isHfImage = form.kind === 'huggingface_image';
  const requiredFilled =
    form.label.trim() !== '' &&
    form.model.trim() !== '' &&
    (isBedrock
      ? form.aws_region.trim() !== ''
      : isHfImage
        ? true
        : form.base_url.trim() !== '');

  const replacingSecret =
    form.api_key.trim() !== '' ||
    form.aws_access_key_id.trim() !== '' ||
    form.aws_secret_access_key.trim() !== '' ||
    Boolean(cleared.api_key) ||
    Boolean(cleared.aws_access_key_id) ||
    Boolean(cleared.aws_secret_access_key);
  const hasSavedCreds = Boolean(provider?.has_credentials);
  // Create: local models may have no key. Edit: reuse stored creds unless
  // the user cleared them. Bedrock can use the ambient AWS chain.
  const canTest =
    requiredFilled &&
    (isBedrock ||
      form.api_key.trim() !== '' ||
      !isEdit ||
      (hasSavedCreds && !cleared.api_key));
  const canApply = requiredFilled && isChatProviderKind(form.kind);
  const alreadyApplied = isEdit && Boolean(provider?.is_active) && canApply;

  function handleSubmit(event: React.FormEvent) {
    event.preventDefault();
    if (!requiredFilled) return;
    onSave(buildPayload(), isEdit, false);
  }

  function handleApply() {
    if (!canApply || alreadyApplied || saving) return;
    onSave(buildPayload(), isEdit, true);
  }

  function handleTest() {
    if (!canTest || testing || saving) return;
    onTest(buildPayload(), isEdit && !replacingSecret);
  }

  function renderSecret(
    field: SecretField,
    id: string,
    label: string,
    storedMask: string | null | undefined,
    placeholder: string,
  ) {
    const hasStored = Boolean(storedMask);
    return (
      <div className="field">
        <label htmlFor={id}>{label}</label>
        <input
          id={id}
          type="password"
          autoComplete="off"
          value={form[field]}
          onChange={(e) => {
            set(field, e.target.value);
            if (e.target.value) setCleared((p) => ({ ...p, [field]: false }));
          }}
          placeholder={
            hasStored && isEdit ? t('provider.keepBlank') : placeholder
          }
        />
        {isEdit && hasStored && (
          <p className="field__hint">
                {t('provider.savedValue')} <code>{storedMask}</code>
            {cleared[field] ? (
              <>
                {' '}
                · <strong>{t('provider.willClear')}</strong>{' '}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => setCleared((p) => ({ ...p, [field]: false }))}
                >
                  {t('provider.undo')}
                </button>
              </>
            ) : (
              <>
                {' '}
                ·{' '}
                <button
                  type="button"
                  className="link-btn"
                  onClick={() => {
                    set(field, '');
                    setCleared((p) => ({ ...p, [field]: true }));
                  }}
                >
                  {t('provider.clear')}
                </button>
              </>
            )}
          </p>
        )}
      </div>
    );
  }

  return (
    <div
      className="modal__backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="provider-editor-title"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <form className="modal" onSubmit={handleSubmit}>
        <div className="modal__header">
          <h2 className="modal__title" id="provider-editor-title">
            {isEdit
              ? t('provider.editTitle', { label: provider?.label ?? '' })
              : t('provider.createTitle')}
          </h2>
          <button
            type="button"
            className="close-btn"
            onClick={onClose}
            aria-label={t('common.close')}
          >
            ×
          </button>
        </div>

        <div className="modal__body stack">
          {error && <div className="alert alert--error">{error}</div>}

          {!isEdit && (
            <div className="field">
              <label>{t('provider.presets')}</label>
              <div className="preset-chips">
                {presets.map((preset) => (
                  <button
                    key={preset.id}
                    type="button"
                    className="chip"
                    onClick={() => applyPreset(preset)}
                  >
                    {preset.label}
                  </button>
                ))}
              </div>
              <p className="field__hint">
                {t('provider.presetsHint')}
              </p>
            </div>
          )}

          <div className="row row--split">
            <div className="field">
              <label htmlFor="provider-label">{t('provider.name')}</label>
              <input
                id="provider-label"
                value={form.label}
                onChange={(e) => set('label', e.target.value)}
                placeholder={t('provider.namePlaceholder')}
                required
                maxLength={80}
              />
              <p className="field__hint">{t('provider.nameHint')}</p>
            </div>

            <div className="field">
              <label htmlFor="provider-kind">{t('provider.kind')}</label>
              <select
                id="provider-kind"
                value={form.kind}
                onChange={(e) => set('kind', e.target.value as ProviderKind)}
              >
                {Object.entries(KIND_LABEL).map(([value, key]) => (
                  <option key={value} value={value}>
                    {t(key)}
                  </option>
                ))}
              </select>
              <p className="field__hint">
                {isBedrock
                  ? t('provider.kindBedrockHint')
                  : isHfImage
                    ? t('provider.kindHfImageHint')
                    : t('provider.kindOpenaiHint')}
              </p>
            </div>
          </div>

          <div className="field">
            <label htmlFor="provider-model">{t('provider.model')}</label>
            <input
              id="provider-model"
              value={form.model}
              onChange={(e) => set('model', e.target.value)}
              placeholder={
                isBedrock
                  ? 'anthropic.claude-3-5-sonnet-20241022-v2:0'
                  : isHfImage
                    ? 'black-forest-labs/FLUX.1-dev'
                    : 'qwen-plus'
              }
              required
              style={{ fontFamily: 'var(--mono)', fontSize: 12.5 }}
            />
          </div>

          {isBedrock ? (
            <>
              <div className="row row--split">
                <div className="field">
                  <label htmlFor="provider-region">{t('provider.region')}</label>
                  <input
                    id="provider-region"
                    value={form.aws_region}
                    onChange={(e) => set('aws_region', e.target.value)}
                    placeholder="us-west-2"
                    required
                  />
                </div>
                <div className="field">
                  <label htmlFor="provider-profile">{t('provider.profile')}</label>
                  <input
                    id="provider-profile"
                    value={form.aws_profile_name}
                    onChange={(e) => set('aws_profile_name', e.target.value)}
                    placeholder="default"
                  />
                  <p className="field__hint">{t('provider.profileHint')}</p>
                </div>
              </div>

              {renderSecret(
                'aws_access_key_id',
                'provider-aws-id',
                'Access Key ID',
                provider?.aws_access_key_id,
                'AKIA…',
              )}
              {renderSecret(
                'aws_secret_access_key',
                'provider-aws-secret',
                'Secret Access Key',
                provider?.aws_secret_access_key,
                '****',
              )}
              {renderSecret(
                'aws_session_token',
                'provider-aws-token',
                t('provider.sessionToken'),
                provider?.aws_session_token,
                t('provider.optionalBlank'),
              )}
              <div className="alert alert--info">
                {t('provider.bedrockCreds')}
              </div>
            </>
          ) : isHfImage ? (
            <>
              <div className="field">
                <label htmlFor="provider-hf-route">{t('provider.hfRoute')}</label>
                <select
                  id="provider-hf-route"
                  value={form.hf_provider}
                  onChange={(e) => set('hf_provider', e.target.value)}
                >
                  <option value="fal-ai">fal-ai</option>
                  <option value="replicate">replicate</option>
                  <option value="hf-inference">hf-inference</option>
                </select>
                <p className="field__hint">{t('provider.hfRouteHint')}</p>
              </div>
              {renderSecret(
                'api_key',
                'provider-api-key',
                'HF Token',
                provider?.api_key,
                t('provider.hfTokenPlaceholder'),
              )}
              <div className="alert alert--info">{t('provider.hfImageHint')}</div>
            </>
          ) : (
            <>
              <div className="field">
                <label htmlFor="provider-base-url">Base URL *</label>
                <input
                  id="provider-base-url"
                  value={form.base_url}
                  onChange={(e) => set('base_url', e.target.value)}
                  placeholder="https://dashscope.aliyuncs.com/compatible-mode/v1"
                  required
                  style={{ fontFamily: 'var(--mono)', fontSize: 12.5 }}
                />
                <p className="field__hint">
                  {t('provider.baseUrlHint')}
                </p>
              </div>

              {renderSecret(
                'api_key',
                'provider-api-key',
                'API Key',
                provider?.api_key,
                t('provider.apiKeyPlaceholder'),
              )}
            </>
          )}

          {!isHfImage && (
          <div className="row row--split">
            <div className="field">
              <label htmlFor="provider-temperature">
                {t('provider.temperature')}
              </label>
              <input
                id="provider-temperature"
                type="number"
                min={0}
                max={2}
                step={0.1}
                value={form.temperature}
                onChange={(e) => set('temperature', e.target.value)}
                placeholder={t('provider.inheritEnv')}
              />
            </div>
            <div className="field">
              <label htmlFor="provider-max-tokens">
                {t('provider.maxTokens')}
              </label>
              <div className="row" style={{ gap: 8, alignItems: 'center' }}>
                <input
                  id="provider-max-tokens"
                  type="number"
                  min={256}
                  max={outputTokenCap(form.kind, form.model)}
                  step={256}
                  value={form.max_tokens}
                  onChange={(e) => set('max_tokens', e.target.value)}
                  placeholder={String(outputTokenCap(form.kind, form.model))}
                />
                <button
                  type="button"
                  className="chat-btn chat-btn--ghost"
                  onClick={() =>
                    set('max_tokens', String(outputTokenCap(form.kind, form.model)))
                  }
                >
                  {t('provider.maxTokensUseMax')}
                </button>
              </div>
              <p className="field__hint">
                {t('provider.maxTokensHint', {
                  n: outputTokenCap(form.kind, form.model),
                })}
              </p>
            </div>
          </div>
          )}

          {testResult && (
            <div
              className={`alert ${testOk ? 'alert--info' : 'alert--error'}`}
            >
              {testResult}
            </div>
          )}
        </div>

        <div className="modal__footer">
          <button type="button" className="btn" onClick={onClose}>
            {t('common.cancel')}
          </button>
          <button
            type="button"
            className="btn"
            disabled={!canTest || testing || saving}
            onClick={handleTest}
            title={
              canTest ? t('provider.testTitle') : t('provider.testNeedKey')
            }
          >
            {testing ? t('settings.testing') : t('provider.test')}
          </button>
          <button
            type="submit"
            className={canApply && !alreadyApplied ? 'btn' : 'btn btn--primary'}
            disabled={saving || !requiredFilled}
          >
            {saving ? t('common.saving') : t('common.save')}
          </button>
          {canApply ? (
            <button
              type="button"
              className="btn btn--primary"
              disabled={saving || !requiredFilled || alreadyApplied}
              onClick={handleApply}
              title={
                alreadyApplied
                  ? t('provider.applied')
                  : t('provider.applyHint')
              }
            >
              {alreadyApplied ? t('provider.applied') : t('provider.apply')}
            </button>
          ) : null}
        </div>
      </form>
    </div>
  );
}
