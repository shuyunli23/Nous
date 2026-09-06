import { useCallback, useEffect, useState } from 'react';

import { ApiError } from '../api/client';
import {
  getShellConfig,
  resetShellConfig,
  updateShellConfig,
} from '../api/shellConfig';
import type { SandboxMode, ShellConfigResponse } from '../api/types';
import { useI18n, type MessageKey } from '../i18n';
import OptionToggle from './OptionToggle';

const MODE_ORDER: SandboxMode[] = [
  'read-only',
  'workspace-write',
  'danger-full-access',
];

const MODE_LABEL: Record<SandboxMode, MessageKey> = {
  'read-only': 'shell.modeReadOnly',
  'workspace-write': 'shell.modeWorkspaceWrite',
  'danger-full-access': 'shell.modeDangerFull',
};

function modeRank(mode: SandboxMode): number {
  return MODE_ORDER.indexOf(mode);
}

function errorMessage(err: unknown, fallback: string): string {
  return err instanceof ApiError ? err.message : fallback;
}

export default function ToolsSection() {
  const { t } = useI18n();
  const [config, setConfig] = useState<ShellConfigResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      setConfig(await getShellConfig());
    } catch (err: unknown) {
      setError(errorMessage(err, t('shell.loadFailed')));
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    void load();
  }, [load]);

  async function handleToggle(on: boolean) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setConfig(await updateShellConfig({ enabled: on }));
      setNotice(t('shell.saved'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('shell.saveFailed')));
    } finally {
      setBusy(false);
    }
  }

  async function handleMode(mode: SandboxMode) {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setConfig(await updateShellConfig({ default_mode: mode }));
      setNotice(t('shell.saved'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('shell.saveFailed')));
    } finally {
      setBusy(false);
    }
  }

  async function handleReset() {
    if (!window.confirm(t('shell.confirmReset'))) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      setConfig(await resetShellConfig());
      setNotice(t('shell.resetOk'));
    } catch (err: unknown) {
      setError(errorMessage(err, t('shell.resetFailed')));
    } finally {
      setBusy(false);
    }
  }

  const sourceLabel = (source: 'runtime' | 'env') =>
    source === 'runtime' ? t('shell.sourceRuntime') : t('shell.sourceEnv');

  return (
    <section id="tools" className="section">
      <h2 className="section__title">{t('shell.title')}</h2>
      <div className="card">
        <p className="muted" style={{ marginTop: 0, fontSize: 13 }}>
          {t('shell.lead')}
        </p>

        {loading ? (
          <p className="muted">{t('common.loading')}</p>
        ) : !config ? (
          <>
            <div className="alert alert--error">
              {error ?? t('shell.loadFailed')}
            </div>
            <button type="button" className="btn" onClick={() => void load()}>
              {t('common.retry')}
            </button>
          </>
        ) : (
          <>
            {error && <div className="alert alert--error">{error}</div>}
            {notice && <div className="alert alert--info">{notice}</div>}

            <OptionToggle
              checked={config.enabled}
              disabled={busy}
              title={t('shell.enableLabel')}
              hint={`${t('shell.enableHint')} · ${sourceLabel(config.enabled_source)}`}
              onChange={(on) => void handleToggle(on)}
            />

            {config.enabled && (
              <>
                <label className="field" style={{ marginTop: 16 }}>
                  <span>{t('shell.modeLabel')}</span>
                  <select
                    value={config.default_mode}
                    disabled={busy}
                    onChange={(event) =>
                      void handleMode(event.target.value as SandboxMode)
                    }
                  >
                    {MODE_ORDER.filter(
                      (m) => modeRank(m) <= modeRank(config.max_mode),
                    ).map((m) => (
                      <option key={m} value={m}>
                        {t(MODE_LABEL[m])}
                      </option>
                    ))}
                  </select>
                  <p className="field__hint">
                    {t('shell.modeHint')} · {sourceLabel(config.default_mode_source)}
                  </p>
                </label>

                <div
                  className="detail-grid detail-grid--compact"
                  style={{ marginTop: 16 }}
                >
                  <div className="stat">
                    <span className="stat__label">{t('shell.ceiling')}</span>
                    <span className="stat__value mono">{config.max_mode}</span>
                  </div>
                  <div className="stat">
                    <span className="stat__label">{t('shell.enforcement')}</span>
                    <span className="stat__value">
                      {config.enforcement === 'strict'
                        ? t('shell.enforcementStrict', {
                            backend: config.backend ?? '',
                          })
                        : t('shell.enforcementAdvisory')}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat__label">{t('shell.network')}</span>
                    <span className="stat__value">
                      {config.network
                        ? t('shell.networkOn')
                        : t('shell.networkOff')}
                    </span>
                  </div>
                  <div className="stat">
                    <span className="stat__label">{t('shell.workspace')}</span>
                    <span className="stat__value mono">{config.workspace_path}</span>
                  </div>
                </div>

                <p className="field__hint" style={{ marginTop: 8 }}>
                  {t('shell.ceilingHint')}
                </p>
              </>
            )}

            <div className="row" style={{ marginTop: 16 }}>
              <button
                type="button"
                className="btn btn--sm"
                disabled={busy}
                onClick={() => void handleReset()}
              >
                {t('shell.reset')}
              </button>
            </div>

            <p
              className="faint"
              style={{ fontSize: 12, marginTop: 16, marginBottom: 0 }}
            >
              {t('shell.storeHint', { path: config.store_path })}
            </p>
          </>
        )}
      </div>
    </section>
  );
}
