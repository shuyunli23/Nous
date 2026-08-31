import { FormEvent, useState } from 'react';

import { api, ApiError } from '../api/client';
import { useI18n, type Locale } from '../i18n';

type UnlockOut = { owner: boolean };

export default function UnlockScreen({
  onUnlocked,
  backendHint,
}: {
  onUnlocked: () => void;
  backendHint?: string;
}) {
  const { t, locale, setLocale } = useI18n();
  const [password, setPassword] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(backendHint ?? '');

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError('');
    try {
      await api.post<UnlockOut>('/auth/unlock', { password });
      onUnlocked();
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setError(t('unlock.wrong'));
      } else {
        setError(t('unlock.failed'));
      }
    } finally {
      setBusy(false);
    }
  }

  function langButton(code: Locale, label: string) {
    return (
      <button
        type="button"
        className={
          locale === code
            ? 'unlock-gate__lang unlock-gate__lang--active'
            : 'unlock-gate__lang'
        }
        aria-pressed={locale === code}
        onClick={() => setLocale(code)}
      >
        {label}
      </button>
    );
  }

  return (
    <div className="unlock-gate">
      <div className="unlock-gate__card">
        <div className="unlock-gate__langs" role="group" aria-label={t('layout.langSwitchAria')}>
          {langButton('zh', t('layout.langZh'))}
          {langButton('en', t('layout.langEn'))}
        </div>
        <p className="unlock-gate__kicker">{t('unlock.kicker')}</p>
        <h1 className="unlock-gate__title">{t('unlock.title')}</h1>
        <p className="unlock-gate__lead">{t('unlock.lead')}</p>
        <form className="unlock-gate__form" onSubmit={(event) => void submit(event)}>
          <label className="unlock-gate__label" htmlFor="nous-admin-password">
            {t('unlock.password')}
          </label>
          <input
            id="nous-admin-password"
            type="password"
            name="password"
            autoComplete="current-password"
            autoFocus
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            disabled={busy}
          />
          {error ? <p className="unlock-gate__error">{error}</p> : null}
          <button type="submit" className="btn btn--primary unlock-gate__submit" disabled={busy || !password}>
            {busy ? t('unlock.checking') : t('unlock.submit')}
          </button>
        </form>
        <a className="unlock-gate__music" href="/harmony/">
          {t('unlock.harmony')}
        </a>
      </div>
    </div>
  );
}
