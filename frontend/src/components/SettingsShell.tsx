import type { ReactNode } from 'react';

import { useI18n, type MessageKey } from '../i18n';

export type SettingsSection = 'general' | 'config' | 'memory' | 'usage';
export type SettingsConfigTab = 'models' | 'search';

const NAV: {
  id: SettingsSection;
  label: MessageKey;
  icon: ReactNode;
}[] = [
  {
    id: 'general',
    label: 'settings.navGeneral',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <circle cx="8" cy="8" r="2.2" stroke="currentColor" />
        <path
          d="M8 2.2v1.4M8 12.4v1.4M2.2 8h1.4M12.4 8h1.4M3.9 3.9l1 1M11.1 11.1l1 1M12.1 3.9l-1 1M4.9 11.1l-1 1"
          stroke="currentColor"
          strokeLinecap="round"
        />
      </svg>
    ),
  },
  {
    id: 'config',
    label: 'settings.navConfig',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <rect x="2.5" y="3" width="11" height="3" rx="1" stroke="currentColor" />
        <rect x="2.5" y="10" width="11" height="3" rx="1" stroke="currentColor" />
      </svg>
    ),
  },
  {
    id: 'memory',
    label: 'settings.navMemory',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M4 3.5h8v9.2l-4-2-4 2V3.5z" stroke="currentColor" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    id: 'usage',
    label: 'settings.navUsage',
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" aria-hidden="true">
        <path d="M3 12.5V8.5M7 12.5V4.5M11 12.5V6.5" stroke="currentColor" strokeLinecap="round" />
      </svg>
    ),
  },
];

const TITLE: Record<SettingsSection, MessageKey> = {
  general: 'settings.navGeneral',
  config: 'settings.navConfig',
  memory: 'settings.navMemory',
  usage: 'settings.navUsage',
};

const INTRO: Record<SettingsSection, MessageKey> = {
  general: 'settings.generalIntro',
  config: 'settings.configIntro',
  memory: 'settings.memoryIntro',
  usage: 'settings.usageIntro',
};

export default function SettingsShell({
  section,
  configTab,
  onSection,
  onConfigTab,
  onClose,
  headerActions,
  children,
}: {
  section: SettingsSection;
  configTab: SettingsConfigTab;
  onSection: (id: SettingsSection) => void;
  onConfigTab: (id: SettingsConfigTab) => void;
  onClose: () => void;
  headerActions?: ReactNode;
  children: ReactNode;
}) {
  const { t } = useI18n();

  return (
    <div className="settings-overlay">
      <button
        type="button"
        className="settings-overlay__mask"
        aria-label={t('settings.close')}
        onClick={onClose}
      />
      <div
        className="settings-panel"
        role="dialog"
        aria-modal="true"
        aria-labelledby="settings-dialog-title"
      >
        <nav className="settings-nav" aria-label={t('settings.title')}>
          <div className="settings-nav__title" id="settings-dialog-title">
            {t('settings.title')}
          </div>
          <div className="settings-nav__list">
            {NAV.map((item) => (
              <button
                key={item.id}
                type="button"
                className={
                  item.id === section
                    ? 'settings-nav__cell settings-nav__cell--on'
                    : 'settings-nav__cell'
                }
                aria-current={item.id === section ? 'true' : undefined}
                onClick={() => onSection(item.id)}
              >
                {item.icon}
                <span>{t(item.label)}</span>
              </button>
            ))}
          </div>
        </nav>

        <div className="settings-content">
          <div className="settings-content__head">
            <div className="settings-content__actions">{headerActions}</div>
            <button
              type="button"
              className="settings-content__close"
              onClick={onClose}
              aria-label={t('settings.close')}
            >
              <svg width="14" height="14" viewBox="0 0 14 14" aria-hidden="true">
                <path d="M3 3l8 8M11 3L3 11" stroke="currentColor" strokeLinecap="round" />
              </svg>
            </button>
          </div>

          <div className="settings-options">
            <h2 className="settings-options__title">{t(TITLE[section])}</h2>
            <p className="settings-options__intro">{t(INTRO[section])}</p>

            {section === 'config' && (
              <div className="settings-subtabs" role="tablist">
                <button
                  type="button"
                  role="tab"
                  aria-selected={configTab === 'models'}
                  className={
                    configTab === 'models'
                      ? 'settings-subtab settings-subtab--on'
                      : 'settings-subtab'
                  }
                  onClick={() => onConfigTab('models')}
                >
                  {t('settings.configTabModels')}
                </button>
                <button
                  type="button"
                  role="tab"
                  aria-selected={configTab === 'search'}
                  className={
                    configTab === 'search'
                      ? 'settings-subtab settings-subtab--on'
                      : 'settings-subtab'
                  }
                  onClick={() => onConfigTab('search')}
                >
                  {t('settings.configTabSearch')}
                </button>
              </div>
            )}

            {children}
          </div>
        </div>
      </div>
    </div>
  );
}
