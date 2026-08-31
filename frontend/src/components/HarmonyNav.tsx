import { useState } from 'react';

import { api } from '../api/client';
import { useI18n } from '../i18n';
import NavIcon from './NavIcon';

type Sso = {
  ticket: string;
  redirect: string;
};

export default function HarmonyNav() {
  const { t } = useI18n();
  const [opening, setOpening] = useState(false);

  async function openHarmony() {
    setOpening(true);
    try {
      const data = await api.post<Sso>('/harmony/sso');
      sessionStorage.setItem('harmony_sso_ticket', data.ticket);
      window.location.assign(data.redirect);
    } catch {
      window.location.assign('/harmony/');
    }
  }

  return (
    <button
      type="button"
      className="nav-link nav-link--action"
      onClick={() => void openHarmony()}
      disabled={opening}
    >
      <span className="nav-link__icon">
        <NavIcon name="harmony" />
      </span>
      <span className="nav-link__copy">
        <span className="nav-link__label">{t('nav.harmony')}</span>
        <span className="nav-link__hint">
          {opening ? t('harmony.opening') : t('nav.harmonyHint')}
        </span>
      </span>
    </button>
  );
}
