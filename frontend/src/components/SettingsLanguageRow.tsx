import { useI18n } from '../i18n';

export default function SettingsLanguageRow() {
  const { t, locale, setLocale } = useI18n();

  return (
    <div className="settings-group" id="language">
      <div className="settings-row">
        <div>
          <div className="settings-row__name">{t('settings.language')}</div>
          <p className="settings-row__hint">{t('settings.languageHint')}</p>
        </div>
        <select
          value={locale}
          aria-label={t('layout.langSwitchAria')}
          onChange={(event) => setLocale(event.target.value === 'en' ? 'en' : 'zh')}
        >
          <option value="zh">{t('layout.langZh')}</option>
          <option value="en">{t('layout.langEn')}</option>
        </select>
      </div>
    </div>
  );
}
