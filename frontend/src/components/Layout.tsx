import { useI18n } from '../i18n';
import AppShell from './AppShell';
import HarmonyNav from './HarmonyNav';

export default function Layout() {
  const { t } = useI18n();

  return (
    <AppShell
      brandName="Nous"
      brandTag="Personal Agent OS"
      navAria={t('nav.aria')}
      nav={[
        {
          to: '/',
          label: t('nav.workbench'),
          hint: t('nav.workbenchHint'),
          icon: 'workbench',
          isActive: (pathname) =>
            pathname === '/' || pathname.startsWith('/chat/'),
        },
        {
          to: '/conversations',
          label: t('nav.conversations'),
          hint: t('nav.conversationsHint'),
          icon: 'history',
        },
        {
          to: '/skills',
          label: t('nav.skills'),
          hint: t('nav.skillsHint'),
          icon: 'skills',
        },
        {
          to: '/knowledge',
          label: t('nav.nexusmind'),
          hint: t('nav.nexusmindHint'),
          icon: 'knowledge',
        },
        {
          to: '/settings',
          label: t('nav.settings'),
          hint: t('nav.settingsHint'),
          icon: 'settings',
        },
      ]}
      afterNav={<HarmonyNav />}
    />
  );
}
